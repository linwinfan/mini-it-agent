"""基础代理类。参见 https://mini-swe-agent.com/latest/advanced/control_flow/ 获取可视化解释。"""

import re
import subprocess
from collections.abc import Callable
from dataclasses import asdict, dataclass

from jinja2 import StrictUndefined, Template

from minisweagent import Environment, Model
from minisweagent.utils.i18n import _
import chardet


@dataclass
class AgentConfig:
    # 默认设置是运行代理的最低要求。查看配置文件以获取改进的设置。
    system_template: str = "你是一个可以完成任何任务的助手。"
    instance_template: str = (
        "你的任务：{{task}}。请用三反引号回复一个shell命令。 "
        "要完成任务，shell命令输出的第一行必须是'COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT'。"
    )
    timeout_template: str = (
        "上一个命令 <command>{{action['action']}}</command> 已超时并被终止。\n"
        "命令的输出为：\n <output>\n{{output}}\n</output>\n"
        "请尝试另一个命令，并确保避免需要交互式输入的命令。"
    )
    format_error_template: str = "请始终在三反引号中提供恰好一个操作。"
    action_observation_template: str = "观察：{{output}}"
    step_limit: int = 0
    cost_limit: float = 3.0


class NonTerminatingException(Exception):
    """由代理可以处理的条件引发。"""


class FormatError(NonTerminatingException):
    """当语言模型的输出不符合预期格式时引发。"""


class ExecutionTimeoutError(NonTerminatingException):
    """当操作执行超时时引发。"""


class TerminatingException(Exception):
    """由终止代理的条件引发。"""


class Submitted(TerminatingException):
    """当语言模型声明代理已完成其任务时引发。"""


class LimitsExceeded(TerminatingException):
    """当代理达到其成本或步骤限制时引发。"""


class DefaultAgent:
    def __init__(self, model: Model, env: Environment, *, config_class: Callable = AgentConfig, **kwargs):
        self.config = config_class(**kwargs)
        self.messages: list[dict] = []
        self.model = model
        self.env = env
        self.extra_template_vars = {}

    def render_template(self, template: str, **kwargs) -> str:
        template_vars = asdict(self.config) | self.env.get_template_vars() | self.model.get_template_vars()
        return Template(template, undefined=StrictUndefined).render(
            **kwargs, **template_vars, **self.extra_template_vars
        )

    def add_message(self, role: str, content: str, **kwargs):
        self.messages.append({"role": role, "content": content, **kwargs})

    def run(self, task: str, **kwargs) -> tuple[str, str]:
        """运行 step() 直到代理完成。返回退出状态和消息"""
        self.extra_template_vars |= {"task": task, **kwargs}
        self.messages = []
        self.add_message("system", self.render_template(self.config.system_template))
        self.add_message("user", self.render_template(self.config.instance_template))
        while True:
            try:
                self.step()
            except NonTerminatingException as e:
                self.add_message("user", str(e))
            except TerminatingException as e:
                self.add_message("user", str(e))
                return type(e).__name__, str(e)

    def step(self) -> dict:
        """查询语言模型，执行操作，返回观察结果。"""
        return self.get_observation(self.query())

    def query(self) -> dict:
        """查询模型并返回响应。"""
        if 0 < self.config.step_limit <= self.model.n_calls or 0 < self.config.cost_limit <= self.model.cost:
            raise LimitsExceeded()
        response = self.model.query(self.messages)
        self.add_message("assistant", **response)
        return response

    def get_observation(self, response: dict) -> dict:
        """执行操作并返回观察结果。"""
        output = self.execute_action(self.parse_action(response))
        observation = self.render_template(self.config.action_observation_template, output=output)
        self.add_message("user", observation)
        return output

    def parse_action(self, response: dict) -> dict:
        """从消息中解析操作。返回操作。"""
        actions = re.findall(r"```bash\s*\n(.*?)\n```", response["content"], re.DOTALL)
        if len(actions) == 1:
            return {"action": actions[0].strip(), **response}
        raise FormatError(self.render_template(self.config.format_error_template, actions=actions))

    def execute_action(self, action: dict) -> dict:
        """执行操作并返回观察结果。"""
        try:
            output = self.env.execute(action["action"])
            if isinstance(output['output'], bytes):
                print('输出的内容是二进制')
                detected = chardet.detect(output['output'])
                print(f"探测编码结果：{detected}")
                encoding = detected['encoding'] or 'utf-8'
                output['output'] = output['output'].decode(encoding, errors="replace")
        except subprocess.TimeoutExpired as e:
            # Handle output decoding with proper encoding detection
            if e.output:
                if isinstance(e.output, bytes):
                    # Try UTF-8 first, then fall back to system encoding
                    try:
                        
                        #print(e.output)
                        detected = chardet.detect(e.output)
                        #print(detected)
                        encoding = detected['encoding'] or 'utf-8'
                        output = e.output.decode(encoding, errors="replace")
                    except UnicodeDecodeError:
                        import sys
                        output = e.output.decode(sys.getfilesystemencoding(), errors="replace")
                else:
                    output = str(e.output)
            else:
                output = ""
            raise ExecutionTimeoutError(
                self.render_template(self.config.timeout_template, action=action, output=output)
            )
        except TimeoutError:
            raise ExecutionTimeoutError(self.render_template(self.config.timeout_template, action=action, output=""))
        self.has_finished(output)
        return output

    def has_finished(self, output: dict[str, str]):
        """如果代理已完成其任务，则引发 Submitted 异常并附带最终输出。"""
        lines = output.get("output", "").lstrip().splitlines(keepends=True)
        if lines and lines[0].strip() in ["MINI_SWE_AGENT_FINAL_OUTPUT", "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"]:
            raise Submitted("".join(lines[1:]))
