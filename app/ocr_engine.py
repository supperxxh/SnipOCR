"""RapidOCR 封装：模型懒加载、后台线程推理、阅读顺序合并。

识别引擎来自 rapidocr_onnxruntime（PaddleOCR 模型 + onnxruntime 推理），
完全离线运行，首次加载模型约 1~2 秒，之后单次识别一般在几百毫秒内。
"""

from __future__ import annotations

import sys
import threading

import numpy as np
from PyQt6.QtCore import (
    QBuffer,
    QByteArray,
    QIODevice,
    QObject,
    QThread,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import QImage, QPixmap

_LOCK = threading.Lock()
_ENGINE = None


def get_engine():
    """懒加载 RapidOCR 单例（线程安全；只在后台线程调用）。"""
    global _ENGINE
    with _LOCK:
        if _ENGINE is None:
            from rapidocr_onnxruntime import RapidOCR  # 延迟导入，加快启动

            _ENGINE = RapidOCR()
    return _ENGINE


def pixmap_to_ndarray(pixmap: QPixmap) -> np.ndarray:
    """QPixmap -> BGR ndarray（物理像素）。必须在 GUI 主线程调用。"""
    image = pixmap.toImage().convertToFormat(QImage.Format.Format_BGR888)
    h, w = image.height(), image.width()
    bpl = image.bytesPerLine()
    ptr = image.constBits()
    if hasattr(ptr, "setsize"):  # sip.voidptr 需要显式暴露长度
        ptr.setsize(image.sizeInBytes())
    try:
        flat = np.frombuffer(ptr, dtype=np.uint8)
    except Exception:
        return _qimage_via_png(image)
    if bpl == w * 3:
        arr = flat.reshape(h, w, 3)
    else:  # 行存在 4 字节对齐 padding
        arr = flat.reshape(h, bpl)[:, : w * 3].reshape(h, w, 3)
    # 关键：frombuffer 只是视图，不持有底层内存；QImage 离开作用域后
    # 内存即被回收，必须 copy 出独立副本，否则得到悬空数据。
    return arr.copy()


def _qimage_via_png(image: QImage) -> np.ndarray:
    """兜底路径：PNG 编码 -> OpenCV 解码为 BGR ndarray。"""
    import cv2  # rapidocr_onnxruntime 自带依赖

    raw = QByteArray()
    buffer = QBuffer(raw)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()
    return cv2.imdecode(np.frombuffer(bytes(raw), dtype=np.uint8), cv2.IMREAD_COLOR)


def _is_cjk(text: str) -> bool:
    return bool(text) and any(
        "\u2e80" <= ch <= "\u9fff" or "\uff00" <= ch <= "\uffef" for ch in text
    )


def merge_result(result) -> str:
    """把 RapidOCR 的检测框列表整理成接近阅读顺序的纯文本。

    规则：按文本框 y 中心聚类成行（容差为行高的 0.6 倍），
    行内按 x 排序；相邻两个中文片段之间不加空格，其余加空格。
    """
    if not result:
        return ""
    items = []
    for box, text, _score in result:
        text = str(text).strip()
        if not text:
            continue
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        items.append(
            {
                "x": sum(xs) / 4.0,
                "yc": sum(ys) / 4.0,
                "h": (max(ys) - min(ys)) or 1.0,
                "text": text,
            }
        )
    if not items:
        return ""

    items.sort(key=lambda it: it["yc"])
    lines: list[dict] = []
    for it in items:
        for line in lines:
            if abs(line["yc"] - it["yc"]) <= max(line["h"], it["h"]) * 0.6:
                n = len(line["items"])
                line["yc"] = (line["yc"] * n + it["yc"]) / (n + 1)
                line["items"].append(it)
                break
        else:
            lines.append({"yc": it["yc"], "h": it["h"], "items": [it]})

    out = []
    for line in lines:
        line["items"].sort(key=lambda i: i["x"])
        text = ""
        for seg in line["items"]:
            if not text:
                text = seg["text"]
            elif _is_cjk(text[-1]) and _is_cjk(seg["text"][0]):
                text += seg["text"]  # 中文之间不加空格
            else:
                text += " " + seg["text"]
        out.append(text)
    return "\n".join(out)


class _WarmupThread(QThread):
    """后台预热：提前加载模型，避免首次识别时等待。"""

    def run(self):  # noqa: D102
        try:
            get_engine()
        except Exception as exc:  # 预热失败不致命
            print(f"[截图识字] OCR 引擎预热失败: {exc}", file=sys.stderr)


class OcrWorker(QThread):
    """单次识别任务（接收 BGR ndarray，线程安全）。

    顺带做二维码检测（OpenCV 内置，毫秒级），失败不影响 OCR。
    """

    ok = pyqtSignal(str, str)  # (ocr_text, qr_text)
    failed = pyqtSignal(str)

    def __init__(self, image_bgr: np.ndarray, parent=None):
        super().__init__(parent)
        self._image = image_bgr

    def run(self):  # noqa: D102
        try:
            from app.qrcode import detect_qr  # 延迟导入，cv2 开销大

            qr_text = detect_qr(self._image)
        except Exception:
            qr_text = ""
        try:
            result, _elapse = get_engine()(self._image)
            self.ok.emit(merge_result(result), qr_text)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")

class OcrEngine(QObject):
    """识别调度器：串行调度 OcrWorker，跨线程信号自动排队回主线程。"""

    result_ready = pyqtSignal(str, str)  # (ocr_text, qr_text)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: OcrWorker | None = None
        self._warmed = False

    def warm_up(self) -> None:
        """启动后预热模型（后台线程，只做一次）。"""
        if self._warmed:
            return
        self._warmed = True
        thread = _WarmupThread(self)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def recognize(self, image_bgr: np.ndarray) -> bool:
        """提交识别。返回 False 表示上一个任务尚未完成。"""
        if self._worker is not None and self._worker.isRunning():
            return False
        worker = OcrWorker(image_bgr)
        worker.ok.connect(self.result_ready)
        worker.failed.connect(self.error_occurred)
        worker.finished.connect(self._on_worker_finished)
        self._worker = worker
        worker.start()
        return True

    @pyqtSlot()
    def _on_worker_finished(self):
        worker = self.sender()
        if isinstance(worker, OcrWorker) and self._worker is worker:
            self._worker = None
            worker.deleteLater()
