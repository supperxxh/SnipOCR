"""设置对话框：全局热键录制 + 功能开关。"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.autostart import is_frozen, set_autostart
from app.settings import Settings, pretty_hotkey

_QSS = """
QDialog { background: #15171d; }
QLabel#rowTitle { color: #e7eaf0; font: 600 13px "Microsoft YaHei"; }
QLabel#rowDesc  { color: #5f6875; font: 11px "Microsoft YaHei"; }
QPushButton {
    background: #262b36; color: #c6ccd8; border: 1px solid #333a48;
    border-radius: 8px; padding: 7px 18px; font: 13px "Microsoft YaHei";
}
QPushButton:hover { background: #2e3441; color: #e7eaf0; }
QPushButton#rec {
    background: #22314f; color: #6ea1ff; border: 1px solid #2f4470;
    font: 600 13px "Microsoft YaHei";
}
QPushButton#rec:hover { background: #2a3c60; }
QCheckBox { color: #dfe3ea; font: 13px "Microsoft YaHei"; spacing: 8px; }
QCheckBox::indicator { width: 16px; height: 16px; }
QDialogButtonBox QPushButton { min-width: 72px; }
"""

_MODIFIER_KEYS = {
    Qt.Key.Key_Control,
    Qt.Key.Key_Shift,
    Qt.Key.Key_Alt,
    Qt.Key.Key_AltGr,
    Qt.Key.Key_Meta,
    Qt.Key.Key_unknown,
}


class HotkeyEdit(QWidget):
    """点击“录制”后捕获组合键（必须带 Ctrl/Shift/Alt 修饰键）。"""

    changed = pyqtSignal(str)

    def __init__(self, hotkey: str, parent=None):
        super().__init__(parent)
        self._value = hotkey
        self._recording = False
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(pretty_hotkey(hotkey))
        self.label.setStyleSheet(
            "color:#6ea1ff; font:700 16px 'Microsoft YaHei';"
        )
        self.btn = QPushButton("点击修改")
        self.btn.setObjectName("rec")
        self.btn.clicked.connect(self._toggle_recording)
        layout.addWidget(self.label)
        layout.addSpacing(12)
        layout.addWidget(self.btn)
        layout.addStretch(1)
        self.setRecording(False)

    @property
    def value(self) -> str:
        return self._value

    def setRecording(self, on: bool) -> None:
        self._recording = on
        if on:
            self.btn.setText("请按下组合键（Esc 取消）…")
            self.grabKeyboard()
        else:
            self.btn.setText("点击修改")
            self.releaseKeyboard()

    def _toggle_recording(self) -> None:
        self.setRecording(not self._recording)

    # ---------- 键盘捕获 ----------
    def keyPressEvent(self, event) -> None:  # noqa: N802
        if not self._recording:
            super().keyPressEvent(event)
            return
        key = event.key()
        if key in _MODIFIER_KEYS:
            return  # 等待非修饰键
        if key == Qt.Key.Key_Escape:
            self.setRecording(False)
            return
        mods = event.modifiers()
        parts = []
        if mods & Qt.KeyboardModifier.ControlModifier:
            parts.append("ctrl")
        if mods & Qt.KeyboardModifier.AltModifier:
            parts.append("alt")
        if mods & Qt.KeyboardModifier.ShiftModifier:
            parts.append("shift")
        if not parts:
            QMessageBox.information(
                self, "无效热键", "热键必须包含 Ctrl / Alt / Shift 修饰键，请重试。"
            )
            return
        key_name = QKeySequence(key).toString().lower()
        if not key_name or key_name.startswith("unknown"):
            return
        self._value = "+".join(parts + [key_name])
        self.label.setText(pretty_hotkey(self._value))
        self.setRecording(False)
        self.changed.emit(self._value)

    def hideEvent(self, event) -> None:  # noqa: N802
        if self._recording:
            self.setRecording(False)
        super().hideEvent(event)


class SettingsDialog(QDialog):
    """设置项在“确定”时一次性写入 Settings。"""

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置 — 截图识字")
        self.resize(440, 320)
        self.setStyleSheet(_QSS)
        self._settings = settings

        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(16)

        # 全局热键
        hot_col = QVBoxLayout()
        hot_col.setSpacing(6)
        hot_title = QLabel("全局截图热键")
        hot_title.setObjectName("rowTitle")
        hot_desc = QLabel("触发后框选屏幕区域进行识别；必须带 Ctrl / Alt / Shift")
        hot_desc.setObjectName("rowDesc")
        self.hotkey_edit = HotkeyEdit(settings.get("hotkey"))
        hot_col.addWidget(hot_title)
        hot_col.addWidget(self.hotkey_edit)
        hot_col.addWidget(hot_desc)
        lay.addLayout(hot_col)

        # 功能开关
        self.chk_auto_copy = QCheckBox("识别完成后自动复制到剪贴板")
        self.chk_auto_copy.setChecked(bool(settings.get("auto_copy")))
        lay.addWidget(self.chk_auto_copy)

        self.chk_history = QCheckBox("保存识别历史（最近 100 条）")
        self.chk_history.setChecked(bool(settings.get("history_enabled")))
        lay.addWidget(self.chk_history)

        self.chk_autostart = QCheckBox("开机自动启动")
        self.chk_autostart.setChecked(bool(settings.get("autostart")))
        if not is_frozen():
            self.chk_autostart.setEnabled(False)
            self.chk_autostart.setToolTip(
                "仅在打包为 exe 后可用（开发模式运行时无效）"
            )
        lay.addWidget(self.chk_autostart)

        lay.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    def accept(self) -> None:  # noqa: D102
        hotkey = self.hotkey_edit.value
        if hotkey != self._settings.get("hotkey") and "+" not in hotkey:
            QMessageBox.warning(self, "无效热键", "热键必须包含修饰键。")
            return
        self._settings.set("hotkey", hotkey)
        self._settings.set("auto_copy", self.chk_auto_copy.isChecked())
        self._settings.set("history_enabled", self.chk_history.isChecked())
        if self.chk_autostart.isEnabled():
            want = self.chk_autostart.isChecked()
            if want != bool(self._settings.get("autostart")):
                if not set_autostart(want):
                    QMessageBox.warning(
                        self, "设置失败", "写入注册表失败，开机自启未更改。"
                    )
                self._settings.set("autostart", want)
        super().accept()
