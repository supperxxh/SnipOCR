"""二维码检测：复用 OpenCV 内置 QRCodeDetector，零额外依赖。

注意：本模块 import cv2 有约数百毫秒开销，请在后台线程中
首次导入（OcrWorker.run 内），避免拖慢启动。
"""

from __future__ import annotations

import cv2
import numpy as np

_detector = None


def detect_qr(image_bgr: np.ndarray) -> str:
    """返回二维码解码内容；未检出或出错返回空字符串（永不抛异常）。"""
    global _detector
    if image_bgr is None or image_bgr.size == 0:
        return ""
    try:
        if _detector is None:
            _detector = cv2.QRCodeDetector()
        data, _points, _straight = _detector.detectAndDecode(image_bgr)
        return (data or "").strip()
    except cv2.error:
        return ""
