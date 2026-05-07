from __future__ import annotations

from pathlib import Path


class Exporter:
    def save_text(self, file_path: str, content: str) -> None:
        Path(file_path).write_text(content, encoding="utf-8")