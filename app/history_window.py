"""识别历史窗口：列表回查、双击/按钮复制、清空。"""

from __future__ import annotations

import time

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.history import HistoryManager

_QSS = """
QDialog { background: #15171d; }
QListWidget {
    background: #14171d;
    border: 1px solid #2c323d;
    border-radius: 10px;
    color: #dfe3ea;
    font: 12px "Microsoft YaHei";
    outline: none;
}
QListWidget::item { padding: 9px 8px; border-radius: 6px; }
QListWidget::item:hover { background: #1e222b; }
QListWidget::item:selected { background: #22314f; color: #f0f2f7; }
QLabel#count { color: #5f6875; font: 11px "Microsoft YaHei"; }
QPushButton {
    background: #262b36; color: #c6ccd8; border: 1px solid #333a48;
    border-radius: 8px; padding: 6px 16px; font: 12px "Microsoft YaHei";
}
QPushButton:hover { background: #2e3441; color: #e7eaf0; }
QPushButton#danger { color: #ff8a86; border-color: #4a2b2e; }
QPushButton#danger:hover { background: #32202a; }
"""


class HistoryWindow(QDialog):
    def __init__(self, manager: HistoryManager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("识别历史 — 截图识字")
        self.resize(580, 480)
        self.setStyleSheet(_QSS)
        self._manager = manager

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(10)

        self.listw = QListWidget()
        self.listw.itemDoubleClicked.connect(self._copy_selected)
        lay.addWidget(self.listw, 1)

        self.count_label = QLabel("")
        self.count_label.setObjectName("count")
        lay.addWidget(self.count_label)

        buttons = QHBoxLayout()
        btn_copy = QPushButton("复制选中项")
        btn_copy.clicked.connect(self._copy_selected)
        btn_refresh = QPushButton("刷新")
        btn_refresh.clicked.connect(self.reload)
        btn_clear = QPushButton("清空历史")
        btn_clear.setObjectName("danger")
        btn_clear.clicked.connect(self._clear)
        btn_close = QPushButton("关闭")
        btn_close.clicked.connect(self.reject)
        buttons.addWidget(btn_copy)
        buttons.addWidget(btn_refresh)
        buttons.addStretch(1)
        buttons.addWidget(btn_clear)
        buttons.addWidget(btn_close)
        lay.addLayout(buttons)

        self.reload()

    # ---------- 数据 ----------
    def reload(self) -> None:
        self.listw.clear()
        records = self._manager.items()
        for rec in records:
            ts = time.strftime(
                "%Y-%m-%d %H:%M", time.localtime(rec.get("ts", 0))
            )
            text = str(rec.get("text", ""))
            oneline = text.replace("\n", " ⏎ ")
            item = QListWidgetItem(f"[{ts}]  {oneline[:110]}")
            item.setToolTip(text)
            item.setData(Qt.ItemDataRole.UserRole, text)
            self.listw.addItem(item)
        self.count_label.setText(f"共 {len(records)} 条（双击条目即可复制）")

    # ---------- 交互 ----------
    def _copy_selected(self) -> None:
        item = self.listw.currentItem()
        if item is None:
            return
        text = item.data(Qt.ItemDataRole.UserRole)
        if text:
            QApplication.clipboard().setText(text)

    def _clear(self) -> None:
        answer = QMessageBox.question(
            self,
            "清空历史",
            "确定要清空全部识别历史吗？此操作不可恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._manager.clear()
            self.reload()
