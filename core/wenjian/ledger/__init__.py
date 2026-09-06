"""文鉴 Ledger — JSON 持久化引擎。跟踪章节分析状态。"""

import json
from pathlib import Path
from typing import Any, Optional


class GateStatusLedger:
    """门禁状态账本 — 跟踪每章节的审计结果。"""

    def __init__(self, directory: str = "./wenjian_ledger"):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _chapter_path(self, chapter_id: str) -> Path:
        return self.directory / f"{chapter_id}.json"

    def save_chapter(self, chapter_id: str, data: dict):
        self._chapter_path(chapter_id).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_chapter(self, chapter_id: str) -> Optional[dict]:
        p = self._chapter_path(chapter_id)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        return None

    def list_chapters(self) -> list[str]:
        return sorted([f.stem for f in self.directory.glob("*.json")])