"""开机自启：写 HKCU Run 注册表项（仅对 PyInstaller 打包后的 exe 生效）。"""

from __future__ import annotations

import sys
import winreg

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "SnipOCR"


def is_frozen() -> bool:
    """是否运行在 PyInstaller 打包环境。"""
    return bool(getattr(sys, "frozen", False))


def set_autostart(enable: bool) -> bool:
    """设置/取消开机自启，返回是否成功（开发模式一律返回 False）。"""
    if not is_frozen():
        return False
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            if enable:
                winreg.SetValueEx(
                    key, VALUE_NAME, 0, winreg.REG_SZ, f'"{sys.executable}"'
                )
            else:
                try:
                    winreg.DeleteValue(key, VALUE_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False


def is_autostart() -> bool:
    """当前是否已注册自启（开发模式恒为 False）。"""
    if not is_frozen():
        return False
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ
        ) as key:
            winreg.QueryValueEx(key, VALUE_NAME)
            return True
    except OSError:
        return False
