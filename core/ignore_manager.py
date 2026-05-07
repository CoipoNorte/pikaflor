from __future__ import annotations

from pathlib import Path, PurePosixPath

from core.constants import (
    DEFAULT_IGNORED_DIRS,
    DEFAULT_IGNORED_EXTENSIONS,
    DEFAULT_IGNORED_FILES,
)

try:
    import pathspec
except Exception:
    pathspec = None


class IgnoreManager:
    def __init__(self, root_path: str) -> None:
        self.root_path = Path(root_path)
        self.gitignore_spec = self._load_gitignore()

    def _load_gitignore(self):
        gitignore_path = self.root_path / ".gitignore"
        if not gitignore_path.exists() or pathspec is None:
            return None

        try:
            lines = gitignore_path.read_text(encoding="utf-8", errors="ignore").splitlines()
            return pathspec.PathSpec.from_lines("gitwildmatch", lines)
        except Exception:
            return None

    def normalize(self, relative_path: str) -> str:
        return str(PurePosixPath(relative_path.replace("\\", "/")))

    def should_ignore(self, relative_path: str, is_dir: bool = False) -> bool:
        rel = self.normalize(relative_path).strip("/")
        if not rel:
            return False

        path = PurePosixPath(rel)
        parts = path.parts
        name = path.name
        suffix = path.suffix.lower()

        if any(part in DEFAULT_IGNORED_DIRS for part in parts if part):
            return True

        if name in DEFAULT_IGNORED_FILES:
            return True

        if not is_dir and suffix in DEFAULT_IGNORED_EXTENSIONS:
            return True

        if self.gitignore_spec is not None:
            probe = rel + ("/" if is_dir else "")
            try:
                if self.gitignore_spec.match_file(probe):
                    return True
            except Exception:
                pass

        return False

    def filter_dirs(self, current_relative_dir: str, dirs: list[str]) -> list[str]:
        kept = []
        for directory in dirs:
            rel = f"{current_relative_dir}/{directory}".strip("/")
            if not self.should_ignore(rel, is_dir=True):
                kept.append(directory)
        return kept