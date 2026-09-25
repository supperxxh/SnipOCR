"""全屏截图 + 橡皮筋框选遮罩窗。

原理：先抓取整个虚拟桌面（多屏拼接）作为窗口背景（“冻结屏幕”），
再用一个无边框置顶窗盖满全屏；拖动鼠标绘制选区，
松开后裁剪选区图像并发出 captured 信号。

坐标约定：窗口/画布使用“虚拟桌面逻辑坐标”（与 QScreen.virtualGeometry 对齐），
画布像素 = 逻辑坐标 × 主屏 DPR（物理像素，OCR 用完整分辨率）。
"""

from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QGuiApplication,
    QImage,
    QPainter,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import QWidget

from app.constants import MIN_SELECTION_PX

_MASK_COLOR = QColor(0, 0, 0, 120)
_BORDER_COLOR = QColor(70, 160, 255)
_TEXT_COLOR = QColor(230, 235, 245)
_HINT_FONT = ("Microsoft YaHei", 12)
_LABEL_FONT = ("Microsoft YaHei", 10)


class CaptureOverlay(QWidget):
    """全屏框选遮罩窗。用完即销毁（one-shot）。"""

    captured = pyqtSignal(QPixmap, QRect)  # 选区图像(物理像素) + 全局逻辑坐标矩形
    cancelled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._origin: QPoint | None = None  # 拖拽起点（窗口局部坐标）
        self._current: QPoint | None = None
        self._canvas = self._grab_desktop()
        self._vg = QGuiApplication.primaryScreen().virtualGeometry()
        self._dpr = self._canvas.width() / max(1, self._vg.width())
        self.setGeometry(self._vg)

    # ---------- 桌面截图（多屏拼接） ----------
    @staticmethod
    def _grab_desktop() -> QPixmap:
        """整桌面截图。优先 mss（纯 GDI，PyInstaller 打包后稳定），
        失败时回退 Qt 的 QScreen.grabWindow（部分打包环境会原生崩溃）。"""
        try:
            return CaptureOverlay._grab_desktop_mss()
        except Exception:
            return CaptureOverlay._grab_desktop_qt()

    @staticmethod
    def _grab_desktop_mss() -> QPixmap:
        import mss  # 延迟导入

        with mss.mss() as sct:
            shot = sct.grab(sct.monitors[0])  # 整个虚拟桌面，物理像素
            raw = shot.bgra  # 注意：是 4 字节/像素的 bgra，不是 3 字节的 rgb
        h, w = shot.height, shot.width
        if len(raw) != w * h * 4:
            raise ValueError(
                f"mss 返回数据长度异常: {len(raw)} != {w * h * 4}"
            )
        # BGRA 字节序列与 Qt ARGB32(little-endian) 内存布局一致
        image = QImage(raw, w, h, w * 4, QImage.Format.Format_ARGB32)
        # copy() 脱离外部缓冲，避免悬空指针
        return QPixmap.fromImage(image.copy())

    @staticmethod
    def _grab_desktop_qt() -> QPixmap:
        primary = QGuiApplication.primaryScreen()
        vg = primary.virtualGeometry()
        dpr = primary.devicePixelRatio() or 1.0
        canvas = QPixmap(round(vg.width() * dpr), round(vg.height() * dpr))
        canvas.fill(Qt.GlobalColor.black)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        for screen in QGuiApplication.screens():
            shot = screen.grabWindow(0)  # 该屏物理像素截图
            shot.setDevicePixelRatio(1.0)
            dst = QRect(screen.geometry().topLeft() - vg.topLeft(), screen.size())
            painter.drawPixmap(dst, shot)
        painter.end()
        return canvas

    # ---------- 生命周期 ----------
    def start(self) -> None:
        self.show()
        self.activateWindow()

    # ---------- 鼠标 / 键盘 ----------
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._origin = event.position().toPoint()
            self._current = QPoint(self._origin)
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            self._cancel()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._origin is not None:
            self._current = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton or self._origin is None:
            return
        rect = QRect(self._origin, event.position().toPoint()).normalized()
        self._origin = self._current = None
        if rect.width() < MIN_SELECTION_PX or rect.height() < MIN_SELECTION_PX:
            self._cancel()  # 误触：过小的选区视为取消
            return
        physical = QRect(
            round(rect.x() * self._dpr),
            round(rect.y() * self._dpr),
            round(rect.width() * self._dpr),
            round(rect.height() * self._dpr),
        )
        selection = self._canvas.copy(physical)
        self.close()
        self.captured.emit(selection, rect.translated(self._vg.topLeft()))

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self._cancel()

    def _cancel(self) -> None:
        self.close()
        self.cancelled.emit()

    # ---------- 绘制 ----------
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(self.rect(), self._canvas)  # 冻结的桌面
        if self._origin is None or self._current is None:
            self._paint_hint(painter)
            return
        rect = QRect(self._origin, self._current).normalized()
        self._paint_mask(painter, rect)
        self._paint_cross(painter)
        self._paint_border(painter, rect)
        self._paint_size_label(painter, rect)

    def _paint_cross(self, painter: QPainter) -> None:
        """跟随光标的贯穿虚线准星，辅助对齐。"""
        pen = QPen(QColor(255, 255, 255, 70), 1)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        pos = self._current
        painter.drawLine(0, pos.y(), self.width(), pos.y())
        painter.drawLine(pos.x(), 0, pos.x(), self.height())

    def _paint_mask(self, painter: QPainter, rect: QRect) -> None:
        """选区外的四条半透明黑带（避免使用合成模式挖洞）。"""
        w, h = self.width(), self.height()
        bands = (
            QRect(0, 0, w, rect.top()),
            QRect(0, rect.bottom() + 1, w, h - rect.bottom() - 1),
            QRect(0, rect.top(), rect.left(), rect.height()),
            QRect(rect.right() + 1, rect.top(), w - rect.right() - 1, rect.height()),
        )
        for band in bands:
            if band.width() > 0 and band.height() > 0:
                painter.fillRect(band, _MASK_COLOR)

    def _paint_border(self, painter: QPainter, rect: QRect) -> None:
        # 外圈白色细描边
        painter.setPen(QPen(QColor(255, 255, 255, 150), 1))
        painter.drawRect(rect.adjusted(-3, -3, 3, 3))
        # 主边框
        painter.setPen(QPen(_BORDER_COLOR, 2))
        painter.drawRect(rect)
        # 四角 L 形手柄
        handle = QPen(QColor(255, 255, 255, 235), 3)
        handle.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(handle)
        length = 14
        corners = (
            (rect.left(), rect.top(), 1, 1),
            (rect.right(), rect.top(), -1, 1),
            (rect.left(), rect.bottom(), 1, -1),
            (rect.right(), rect.bottom(), -1, -1),
        )
        for x, y, dx, dy in corners:
            painter.drawLine(x, y, x + dx * length, y)
            painter.drawLine(x, y, x, y + dy * length)

    def _paint_size_label(self, painter: QPainter, rect: QRect) -> None:
        label = f"{rect.width()} × {rect.height()}"
        painter.setFont(QFont(*_LABEL_FONT))
        metrics = painter.fontMetrics()
        tw = metrics.horizontalAdvance(label) + 20
        th = metrics.height() + 10
        lx = max(0, min(rect.right() - tw + 1, self.width() - tw))
        ly = rect.bottom() + 8
        if ly + th > self.height():
            ly = max(0, rect.top() - th - 8)
        painter.setBrush(QColor(18, 20, 28, 225))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRect(lx, ly, tw, th), th / 2, th / 2)
        painter.setPen(QColor(255, 255, 255, 235))
        painter.drawText(
            QRect(lx, ly, tw, th), Qt.AlignmentFlag.AlignCenter, label
        )

    def _paint_hint(self, painter: QPainter) -> None:
        text = "按住鼠标左键框选识别区域    右键 / Esc 取消"
        painter.setFont(QFont(*_HINT_FONT))
        metrics = painter.fontMetrics()
        rect = QRect(
            0, 0, metrics.horizontalAdvance(text) + 40, metrics.height() + 24
        )
        rect.moveCenter(self.rect().center())
        painter.setBrush(QColor(15, 17, 25, 205))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 10, 10)
        painter.setPen(_TEXT_COLOR)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
