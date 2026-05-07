from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FileInfo:
    absolute_path: str
    relative_path: str
    size: int
    extension: str
    is_text: bool
    included: bool = True


@dataclass
class ProjectSnapshot:
    root_path: str
    project_name: str
    files: dict[str, FileInfo] = field(default_factory=dict)
    directories: set[str] = field(default_factory=set)
    detected_technologies: list[str] = field(default_factory=list)
    dependencies: dict[str, list[str]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def included_files(self) -> list[FileInfo]:
        return [file for file in self.files.values() if file.included]

    def included_text_files(self) -> list[FileInfo]:
        return [file for file in self.files.values() if file.included and file.is_text]

    def excluded_files(self) -> list[FileInfo]:
        return [file for file in self.files.values() if not file.included]

    def file_count(self) -> int:
        return len(self.files)

    def included_count(self) -> int:
        return len(self.included_files())