"""Internationalization utilities for mini-swe-agent."""

import gettext
import locale
import os
import sys
from pathlib import Path

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent
LOCALE_DIR = PROJECT_ROOT / "locale"
if(not Path.exists(LOCALE_DIR)):
    LOCALE_DIR = Path(__file__).parent.parent.parent.parent / "locale"

# Fix Windows terminal encoding issues
if sys.platform == "win32":
    # Set Windows console to UTF-8 encoding
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
    # Also set environment variables for subprocesses
    os.environ['PYTHONIOENCODING'] = 'utf-8'

def _is_chinese_locale():
    """Check if the system locale is Chinese."""
    # Check environment variables first
    if os.getenv('LANG', '').startswith('zh') or os.getenv('LC_ALL', '').startswith('zh'):
        return True

    # Check Windows locale settings
    if sys.platform == "win32":
        try:
            # Get system locale
            current_locale = locale.getlocale()
            if current_locale and current_locale[0] and current_locale[0].startswith('zh'):
                return True

            # Also check default locale
            default_locale = locale.getdefaultlocale()
            if default_locale and default_locale[0] and default_locale[0].startswith('zh'):
                return True
        except Exception:
            pass

    # Check for zh-CN in Windows language settings
    if sys.platform == "win32":
        import ctypes
        try:
            # Get system default UI language
            user32 = ctypes.windll.user32
            user32.GetUserDefaultUILanguage()
            # Simplified Chinese locale ID is 2052 (0x0804)
            if user32.GetUserDefaultUILanguage() == 2052:
                return True
        except Exception:
            pass

    return False

# Set up gettext translation
try:
    # Try to load Chinese translation only if system is Chinese
    if _is_chinese_locale():
        zh_translation = gettext.translation('messages', localedir=LOCALE_DIR, languages=['zh_CN'])
        zh_translation.install()
        _ = zh_translation.gettext
        print("Chinese translation loaded successfully")
    else:
        _ = gettext.gettext
        print("System locale is not Chinese, using English")
except FileNotFoundError:
    # Fallback to English if Chinese translation not found
    _ = gettext.gettext
    print(LOCALE_DIR)
    print("Chinese translation not found, using English")

def gettext_install():
    """Install the gettext translation function globally."""
    import builtins
    builtins.__dict__['_'] = _

def setup_i18n(language='auto'):
    """Setup internationalization for the application."""
    # Check if Chinese locale is requested
    if language == 'zh_CN' or (language == 'auto' and _is_chinese_locale()):
        try:
            zh_translation = gettext.translation('messages', localedir=LOCALE_DIR, languages=['zh_CN'])
            zh_translation.install()
            return zh_translation.gettext
        except FileNotFoundError:
            pass

    # Default to English
    return gettext.gettext

def get_current_language():
    """Get the current language setting."""
    if _is_chinese_locale():
        return 'zh_CN'
    return 'en'

# Install the translation function globally
_ = setup_i18n()