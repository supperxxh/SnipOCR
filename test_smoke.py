"""冒烟测试：合成一张带文字的图片，走「QPixmap -> ndarray -> RapidOCR -> 合并」全链路。

不依赖截图交互，可在 offscreen 平台下自动运行：
    python test_smoke.py
"""

import os

if os.environ.get("FORCE_OFFSCREEN"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys  # noqa: E402

from PyQt6.QtCore import QRect, Qt  # noqa: E402
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QPainter, QPixmap  # noqa: E402

from app.ocr_engine import get_engine, merge_result, pixmap_to_ndarray  # noqa: E402
from app.qrcode import detect_qr  # noqa: E402


def make_text_pixmap() -> QPixmap:
    """合成一张白底黑字的测试图（两行英文数字，模拟屏幕文字）。"""
    pixmap = QPixmap(640, 200)
    pixmap.fill(Qt.GlobalColor.white)
    painter = QPainter(pixmap)
    painter.setPen(QColor(0, 0, 0))

    font_big = QFont("Arial", 40)
    font_big.setBold(True)
    painter.setFont(font_big)
    painter.drawText(
        QRect(20, 30, 600, 80),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        "Hello OCR 12345",
    )

    painter.setFont(QFont("Arial", 28))
    painter.drawText(QRect(20, 120, 600, 60), 0, "Second line 678")

    painter.end()
    return pixmap


def main() -> int:
    app = QGuiApplication(sys.argv)

    pixmap = make_text_pixmap()
    arr = pixmap_to_ndarray(pixmap)
    assert arr.shape == (200, 640, 3), f"ndarray 形状异常: {arr.shape}"
    assert arr.dtype == "uint8"
    dark = int((arr < 128).any(axis=2).sum())
    print(f"[1/3] QPixmap -> ndarray 转换正常: shape={arr.shape}, 暗像素={dark}")
    assert dark > 500, "合成图上几乎没有文字像素，疑似字体渲染失败"

    # 二维码检测：无码图应返回空字符串且不抛异常
    assert detect_qr(arr) == "", "无二维码图像应返回空字符串"
    print("[1.5/3] 二维码检测（无码路径）正常")

    result, _elapse = get_engine()(arr)
    text = merge_result(result)
    print("[2/3] RapidOCR 识别结果:")
    print("-" * 40)
    print(text)
    print("-" * 40)

    assert text, "识别结果为空"
    digits = "".join(ch for ch in text if ch.isdigit())
    assert "12345" in digits, f"未识别出 12345: {text!r}"
    print("[3/4] 同步推理路径正常")

    # QThread worker 路径：实例化 -> 后台线程推理 -> 信号排队回主线程
    from PyQt6.QtCore import QEventLoop, QTimer

    from app.ocr_engine import OcrWorker

    loop = QEventLoop()
    got: dict = {}
    worker = OcrWorker(arr)
    worker.ok.connect(lambda t, q: (got.__setitem__("text", t), got.__setitem__("qr", q), loop.quit()))
    worker.failed.connect(lambda m: (got.__setitem__("error", m), loop.quit()))
    worker.start()
    QTimer.singleShot(180_000, loop.quit)  # 保险超时
    loop.exec()
    assert "text" in got, f"OcrWorker 未返回: {got.get('error', '超时')}"
    digits2 = "".join(ch for ch in got["text"] if ch.isdigit())
    assert "12345" in digits2, f"worker 路径未识别出 12345: {got['text']!r}"
    print("[4/4] 冒烟测试通过 ✓（转换 / 同步推理 / worker 线程路径）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
