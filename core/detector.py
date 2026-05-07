from __future__ import annotations

import json
from pathlib import Path

from models.project_model import ProjectSnapshot

try:
    import tomllib
except Exception:
    import tomli as tomllib


class ProjectDetector:
    JS_TECH_MAP = {
        "react": "React",
        "vite": "Vite",
        "typescript": "TypeScript",
        "electron": "Electron",
        "zustand": "Zustand",
        "redux": "Redux",
        "@reduxjs/toolkit": "Redux Toolkit",
        "tailwindcss": "Tailwind CSS",
        "next": "Next.js",
        "vue": "Vue",
        "svelte": "Svelte",
        "express": "Express",
        "axios": "Axios",
    }

    PY_TECH_MAP = {
        "fastapi": "FastAPI",
        "flask": "Flask",
        "django": "Django",
        "customtkinter": "CustomTkinter",
        "pyside6": "PySide6",
        "pyqt5": "PyQt5",
        "pillow": "Pillow",
        "streamlit": "Streamlit",
        "requests": "Requests",
        "sqlalchemy": "SQLAlchemy",
    }

    def analyze(self, snapshot: ProjectSnapshot) -> ProjectSnapshot:
        root = Path(snapshot.root_path)
        technologies: set[str] = set()
        dependencies: dict[str, list[str]] = {}
        notes: list[str] = []

        if any(file.relative_path.endswith(".py") for file in snapshot.files.values()):
            technologies.add("Python")

        if any(file.relative_path.endswith((".ts", ".tsx")) for file in snapshot.files.values()):
            technologies.add("TypeScript")

        if any(file.relative_path.endswith((".js", ".jsx", ".cjs", ".mjs")) for file in snapshot.files.values()):
            technologies.add("JavaScript")

        package_json = root / "package.json"
        if package_json.exists():
            technologies.add("Node.js")
            package_data = self._read_json(package_json)
            deps = {}
            deps.update(package_data.get("dependencies", {}) or {})
            deps.update(package_data.get("devDependencies", {}) or {})
            scripts = package_data.get("scripts", {}) or {}
            dependencies["npm"] = sorted(deps.keys())
            if scripts:
                dependencies["npm:scripts"] = sorted(scripts.keys())

            for dep_name in deps:
                tech = self.JS_TECH_MAP.get(dep_name.lower())
                if tech:
                    technologies.add(tech)

        requirements_txt = root / "requirements.txt"
        if requirements_txt.exists():
            technologies.add("Python")
            reqs = self._read_requirements(requirements_txt)
            dependencies["pip"] = reqs
            for req in reqs:
                name = req.split("==")[0].split(">=")[0].split("<=")[0].strip().lower()
                tech = self.PY_TECH_MAP.get(name)
                if tech:
                    technologies.add(tech)

        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            technologies.add("Python")
            pyproject_deps = self._read_pyproject_dependencies(pyproject)
            if pyproject_deps:
                dependencies["pyproject"] = pyproject_deps
                for dep in pyproject_deps:
                    key = dep.split("==")[0].split(">=")[0].split("<=")[0].strip().lower()
                    tech = self.PY_TECH_MAP.get(key)
                    if tech:
                        technologies.add(tech)

        if (root / "tsconfig.json").exists():
            technologies.add("TypeScript")

        if any((root / name).exists() for name in ("vite.config.ts", "vite.config.js", "vite.config.mjs", "vite.config.cjs")):
            technologies.add("Vite")

        if (root / "electron").exists() or any(
            file.relative_path.startswith("electron/") for file in snapshot.files.values()
        ):
            technologies.add("Electron")

        if (root / "README.md").exists():
            notes.append("Se detectó documentación principal en README.md.")

        notes.append(f"Archivos visibles detectados: {snapshot.file_count()}.")
        notes.append(f"Archivos de texto potencialmente resumibles: {sum(1 for f in snapshot.files.values() if f.is_text)}.")

        snapshot.detected_technologies = sorted(technologies)
        snapshot.dependencies = dependencies
        snapshot.notes = notes
        return snapshot

    def _read_json(self, path: Path) -> dict:
        try:
            return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            return {}

    def _read_requirements(self, path: Path) -> list[str]:
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            clean = []
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    clean.append(stripped)
            return clean
        except Exception:
            return []

    def _read_pyproject_dependencies(self, path: Path) -> list[str]:
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            return []

        deps: list[str] = []

        project_section = data.get("project", {})
        project_deps = project_section.get("dependencies", []) or []
        deps.extend(project_deps)

        poetry_section = data.get("tool", {}).get("poetry", {})
        poetry_deps = poetry_section.get("dependencies", {}) or {}
        deps.extend(
            [f"{key}{value if isinstance(value, str) else ''}" for key, value in poetry_deps.items() if key != "python"]
        )

        return sorted({dep for dep in deps if dep})