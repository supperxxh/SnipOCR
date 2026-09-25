"""关于对话框：应用名 / 版本 / 简介 / 版权。"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from app.constants import APP_NAME, APP_VERSION

_QSS = """
QDialog { background: #15171d; }
#name { color: #f0f2f7; font: 700 22px "Microsoft YaHei"; }
#version { color: #6ea1ff; background: #22314f; border: 1px solid #2f4470;
           border-radius: 9px; padding: 3px 14px; font: 600 12px "Microsoft YaHei"; }
#desc { color: #8a93a3; font: 13px "Microsoft YaHei"; }
#sep { color: #5f6875; font: 11px "Microsoft YaHei"; background: #1e222b;
       border: 1px solid #2c323d; border-radius: 8px; padding: 8px 12px; }
#copyright { color: #5f6875; font: 11px "Microsoft YaHei"; }
QPushButton {
    background: #262b36; color: #c6ccd8; border: 1px solid #333a48;
    border-radius: 8px; padding: 7px 22px; font: 13px "Microsoft YaHei";
}
QPushButton:hover { background: #2e3441; color: #e7eaf0; }
"""

_APP_DESC = "框选屏幕，文字到手 — 本地离线 OCR 工具"
_COPYRIGHT = f"© 2026 {APP_NAME}（SnipOCR）· 识别全程在本机完成，数据不上传"


class AboutDialog(QDialog):
    """关于对话框（模态，从托盘菜单或主窗打开）。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"关于 {APP_NAME}")
        self.setFixedSize(360, 320)
        self.setStyleSheet(_QSS)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 26, 28, 22)
        lay.setSpacing(10)

        # ---- 图标 ----
        icon_row = QHBoxLayout()
        icon_row.addStretch(1)
        icon_label = QLabel()
        icon = self.windowIcon()
        if icon.isNull() and parent is not None:
            icon = parent.windowIcon()
        icon_label.setPixmap(icon.pixmap(64, 64))
        icon_row.addWidget(icon_label)
        icon_row.addStretch(1)
        lay.addLayout(icon_row)
        lay.addSpacing(4)

        # ---- 应用名 + 版本 ----
        name_row = QHBoxLayout()
        name_row.setSpacing(10)
        name = QLabel(APP_NAME)
        name.setObjectName("name")
        version = QLabel(f"v{APP_VERSION}")
        version.setObjectName("version")
        name_row.addStretch(1)
        name_row.addWidget(name)
        name_row.addWidget(version)
        name_row.addStretch(1)
        lay.addLayout(name_row)

        # ---- 简介 ----
        desc = QLabel(_APP_DESC)
        desc.setObjectName("desc")
        desc.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(desc)
        lay.addSpacing(6)

        # ---- 版权 / 隐私 ----
        sep = QLabel(_COPYRIGHT)
        sep.setObjectName("sep")
        sep.setWordWrap(True)
        sep.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(sep)
        lay.addStretch(1)

        # ---- 关闭 ----
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        lay.addLayout(btn_row)
