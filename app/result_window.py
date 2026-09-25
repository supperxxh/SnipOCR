"""识别结果浮窗：无边框置顶、深色圆角、可编辑、一键复制。"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QRect, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QGuiApplication, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.constants import RESULT_WINDOW_MAX_HEIGHT, RESULT_WINDOW_WIDTH

_QSS = """
#root {
    background: #1e222b;
    border-radius: 12px;
    border: 1px solid #2c323d;
}
QLabel#title { color: #f0f2f7; font: 600 13px "Microsoft YaHei"; }
QLabel#hint  { color: #5f6875; font: 11px "Microsoft YaHei"; }
QPlainTextEdit {
    background: #14171d;
    color: #e7eaf0;
    border: 1px solid #2c323d;
    border-radius: 8px;
    font: 13px "Microsoft YaHei";
    selection-background-color: #3d7bfd;
}
QPushButton {
    background: #262b36;
    color: #c6ccd8;
    border: 1px solid #333a48;
    border-radius: 8px;
    padding: 6px 16px;
    font: 12px "Microsoft YaHei";
}
QPushButton:hover { background: #2e3441; color: #e7eaf0; }
QPushButton:disabled { color: #5b6270; }
QPushButton#primary {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 #4d88ff, stop:1 #3d7bfd);
    border: 1px solid #3d7bfd;
    color: white;
}
QPushButton#primary:hover { background: #5590ff; }
QPushButton#primary:disabled { background: #2a4a80; border-color: #2a4a80; color: #9db4d8; }
QLabel#qrbar {
    background: #16241c;
    color: #7fd4a8;
    border: 1px solid #2b5b41;
    border-radius: 8px;
    padding: 7px 10px;
    font: 12px "Microsoft YaHei";
}
"""

_ICON_CACHE = None


class ResultWindow(QWidget):
    """在选区附近弹出的识别结果窗。"""

    retake_requested = pyqtSignal()

    def __init__(self, anchor: QRect, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._anchor = QRect(anchor)
        self._build_ui()
        self._place()
        self.show()

    # ---------- UI ----------
    @classmethod
    def _mini_icon(cls) -> QPixmap:
        """18px 蓝色圆角小图标（缓存）。"""
        global _ICON_CACHE
        if _ICON_CACHE is None:
            pm = QPixmap(18, 18)
            pm.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pm)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setBrush(QColor("#3d7bfd"))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(1, 1, 16, 16, 5, 5)
            painter.end()
            _ICON_CACHE = pm
        return _ICON_CACHE

    def _build_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("root")
        root.setStyleSheet(_QSS)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(root)

        lay = QVBoxLayout(root)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(10)

        head = QHBoxLayout()
        head.setSpacing(8)
        icon_label = QLabel()
        icon_label.setPixmap(self._mini_icon())
        title = QLabel("识别结果")
        title.setObjectName("title")
        hint = QLabel("可直接编辑 · Esc 关闭")
        hint.setObjectName("hint")
        head.addWidget(icon_label)
        head.addWidget(title)
        head.addStretch(1)
        head.addWidget(hint)
        lay.addLayout(head)

        self.qr_bar = QLabel()
        self.qr_bar.setObjectName("qrbar")
        self.qr_bar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.qr_bar.setToolTip("点击复制二维码内容")
        self.qr_bar.installEventFilter(self)
        self.qr_bar.hide()
        lay.addWidget(self.qr_bar)

        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText("（未识别到文字）")
        lay.addWidget(self.editor, 1)

        buttons = QHBoxLayout()
        self.btn_copy = QPushButton("复制")
        self.btn_copy.setObjectName("primary")
        self.btn_copy.clicked.connect(self._copy)
        self.btn_retake = QPushButton("重新截取")
        self.btn_retake.clicked.connect(self._retake)
        self.btn_close = QPushButton("关闭")
        self.btn_close.clicked.connect(self.close)
        buttons.addWidget(self.btn_copy)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_retake)
        buttons.addWidget(self.btn_close)
        lay.addLayout(buttons)

    def _place(self) -> None:
        """弹出位置：优先选区下方，放不下则放上方，并夹回屏幕内。"""
        vg = QGuiApplication.primaryScreen().virtualGeometry()
        w = min(RESULT_WINDOW_WIDTH, vg.width() - 16)
        h = min(RESULT_WINDOW_MAX_HEIGHT, vg.height() - 16)
        x = self._anchor.left()
        y = self._anchor.bottom() + 12
        if y + h > vg.bottom():
            y = self._anchor.top() - h - 12
        x = max(vg.left() + 8, min(x, vg.right() - w + 1))
        y = max(vg.top() + 8, min(y, vg.bottom() - h + 1))
        self.setGeometry(x, y, w, h)

    # ---------- 状态 ----------
    def show_loading(self) -> None:
        self.editor.setPlainText("正在识别，请稍候…")
        self.btn_copy.setEnabled(False)
        self.qr_bar.hide()

    def set_result(self, text: str, qr: str = "") -> None:
        text = (text or "").strip()
        qr = (qr or "").strip()
        if qr:
            self.qr_bar.setProperty("full", qr)
            shown = qr if len(qr) <= 90 else qr[:90] + "…"
            self.qr_bar.setText(f"二维码：{shown}")
            self.qr_bar.setToolTip(f"点击复制：{qr}")
            self.qr_bar.show()
        else:
            self.qr_bar.hide()
        self.editor.setPlainText(text if text else "（未识别到文字）")
        self.btn_copy.setEnabled(bool(text))
        if text:
            self.editor.setFocus()

    # ---------- 交互 ----------
    def _copy(self) -> None:
        text = self.editor.toPlainText()
        if not text:
            return
        QApplication.clipboard().setText(text)
        self.btn_copy.setText("已复制 ✓")
        QTimer.singleShot(1200, self._restore_copy_text)

    def _restore_copy_text(self) -> None:
        try:
            self.btn_copy.setText("复制")
        except RuntimeError:  # 窗口已销毁
            pass

    def _retake(self) -> None:
        self.close()
        self.retake_requested.emit()

    def eventFilter(self, obj, event) -> None:  # noqa: N802
        if obj is self.qr_bar and event.type() == QEvent.Type.MouseButtonPress:
            full = self.qr_bar.property("full")
            if full:
                QApplication.clipboard().setText(str(full))
            return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)
