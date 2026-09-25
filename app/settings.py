"""用户设置：JSON 文件持久化 + 变更信号。

存储位置：%APPDATA%/SnipOCR/config.json
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from PyQt6.QtCore import QObject, pyqtSignal

from app.constants import HOTKEY

DATA_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "SnipOCR"
CONFIG_PATH = DATA_DIR / "config.json"


def pretty_hotkey(hotkey: str) -> str:
    """keyboard 库语法 -> 界面显示语法：'alt+q' -> 'Alt + Q'。"""
    parts = []
    for part in hotkey.split("+"):
        part = part.strip().lower()
        if not part:
            continue
        if part in ("ctrl", "control", "shift", "alt", "win", "windows"):
            parts.append(part.capitalize())
        else:
            parts.append(part.upper())
    return " + ".join(parts)


class Settings(QObject):
    """线程模型：只在 GUI 主线程读写。"""

    changed = pyqtSignal(str, object)  # (key, value)

    DEFAULTS = {
        "auto_copy": True,        # 识别后自动复制到剪贴板
        "first_run": True,        # 首次运行显示引导主窗（显示一次后自动置否）
        "hotkey": HOTKEY,          # 全局热键（keyboard 库语法）
        "history_enabled": True,  # 保存识别历史
        "history_max": 100,       # 历史上限条数
        "autostart": False,       # 开机自启（仅打包 exe 后生效）
    }

    def __init__(self, path=CONFIG_PATH):
        super().__init__()
        self._path = Path(path)
        self._data = dict(self.DEFAULTS)
        self._load()

    # ---------- 读写 ----------
    def get(self, key: str):
        return self._data.get(key, self.DEFAULTS.get(key))

    def set(self, key: str, value) -> None:
        if self._data.get(key) == value:
            return
        self._data[key] = value
        self._save()
        self.changed.emit(key, value)

    # ---------- 持久化 ----------
    def _load(self) -> None:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return  # 首次运行或文件损坏，使用默认值
        if isinstance(raw, dict):
            self._data.update(
                {k: v for k, v in raw.items() if k in self.DEFAULTS}
            )

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError:
            pass  # 磁盘异常时静默，不影响使用
