from __future__ import annotations

import os
from pathlib import Path

from core.constants import DEFAULT_IGNORED_EXTENSIONS, MAX_BINARY_SNIFF_BYTES, TEXT_EXTENSIONS
from core.ignore_manager import IgnoreManager
from models.project_model import FileInfo, ProjectSnapshot


class ProjectScanner:
    def scan(self, root_path: str, project_name: str | None = None) -> ProjectSnapshot:
        root = Path(root_path).resolve()
        snapshot = ProjectSnapshot(
            root_path=str(root),
            project_name=project_name or root.name,
        )
        ignore_manager = IgnoreManager(str(root))

        for current_root, dirs, files in os.walk(root):
            current_path = Path(current_root)
            rel_dir = self._to_relative(root, current_path)

            dirs[:] = ignore_manager.filter_dirs(rel_dir, dirs)

            for file_name in files:
                absolute_file = current_path / file_name
                rel_file = self._to_relative(root, absolute_file)
                if ignore_manager.should_ignore(rel_file, is_dir=False):
                    continue

                extension = absolute_file.suffix.lower()
                size = self._safe_size(absolute_file)
                is_text = self._is_probably_text(absolute_file, extension)

                snapshot.files[rel_file] = FileInfo(
                    absolute_path=str(absolute_file),
                    relative_path=rel_file,
                    size=size,
                    extension=extension,
                    is_text=is_text,
                    included=True,
                )

                parent = str(Path(rel_file).parent).replace("\\", "/")
                if parent != ".":
                    parts = parent.split("/")
                    for i in range(len(parts)):
                        snapshot.directories.add("/".join(parts[: i + 1]))

        return snapshot

    def _to_relative(self, root: Path, path: Path) -> str:
        try:
            return path.relative_to(root).as_posix()
        except Exception:
            return ""

    def _safe_size(self, path: Path) -> int:
        try:
            return path.stat().st_size
        except Exception:
            return 0

    def _is_probably_text(self, path: Path, extension: str) -> bool:
        if extension in TEXT_EXTENSIONS:
            return True

        if extension in DEFAULT_IGNORED_EXTENSIONS:
            return False

        try:
            chunk = path.read_bytes()[:MAX_BINARY_SNIFF_BYTES]
            return b"\x00" not in chunk
        except Exception:
            return False