"""识别历史：JSONL 追加存储（新条目在文件尾，读取时倒序）。"""

from __future__ import annotations

import json
import time
from pathlib import Path

from app.settings import DATA_DIR

HISTORY_PATH = DATA_DIR / "history.jsonl"


class HistoryManager:
    """线程模型：只在 GUI 主线程调用。"""

    def __init__(self, path=HISTORY_PATH, max_items: int = 100):
        self._path = Path(path)
        self._max = max(10, int(max_items))

    # ---------- 写入 ----------
    def add(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        record = {"ts": time.time(), "text": text[:2000]}
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            self._prune()
        except OSError:
            pass  # 历史写失败不影响主流程

    # ---------- 读取 ----------
    def items(self) -> list[dict]:
        """最近条目在前。"""
        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        out = []
        for line in reversed(lines):
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if isinstance(rec, dict) and rec.get("text"):
                out.append(rec)
        return out

    def clear(self) -> None:
        try:
            self._path.unlink(missing_ok=True)
        except OSError:
            pass

    # ---------- 内部 ----------
    def _prune(self) -> None:
        """超过 2 倍上限时整体重写裁剪（摊销写放大）。"""
        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        if len(lines) < self._max * 2:
            return
        keep = [line for line in lines[-self._max :] if line.strip()]
        try:
            self._path.write_text(
                ("\n".join(keep) + "\n") if keep else "", encoding="utf-8"
            )
        except OSError:
            pass
