from __future__ import annotations

import json
import re
from pathlib import Path

from core.constants import MAX_CODE_SNIPPET_CHARS, MAX_SUMMARIZER_READ_CHARS
from models.project_model import FileInfo, ProjectSnapshot

try:
    import tomllib
except Exception:
    import tomli as tomllib


class ProjectSummarizer:
    def generate(
        self,
        snapshot: ProjectSnapshot,
        mode: str = "summary",
        project_name: str | None = None,
        objective: str = "",
    ) -> str:
        selected_name = (project_name or snapshot.project_name or Path(snapshot.root_path).name).strip()
        included_files = sorted(snapshot.included_files(), key=lambda file: file.relative_path)
        included_text_files = [file for file in included_files if file.is_text]
        important_files = set(self.important_files(snapshot))

        lines: list[str] = []
        lines.append(f"# Proyecto: {selected_name}")
        lines.append("")
        lines.append("## Contexto general")
        lines.append(f"- Ruta raíz: `{snapshot.root_path}`")
        lines.append(f"- Archivos incluidos: **{len(included_files)}**")
        lines.append(f"- Archivos de texto incluidos: **{len(included_text_files)}**")
        lines.append(f"- Archivos excluidos manualmente: **{len(snapshot.excluded_files())}**")
        if objective.strip():
            lines.append(f"- Objetivo indicado por el usuario: {objective.strip()}")

        lines.append("")
        lines.append("## Tecnologías detectadas")
        if snapshot.detected_technologies:
            for tech in snapshot.detected_technologies:
                lines.append(f"- {tech}")
        else:
            lines.append("- No se detectaron tecnologías con alta confianza.")

        if snapshot.dependencies:
            lines.append("")
            lines.append("## Dependencias y contexto técnico")
            for source, deps in snapshot.dependencies.items():
                lines.append(f"### {source}")
                if deps:
                    preview = deps[:30]
                    for dep in preview:
                        lines.append(f"- {dep}")
                    if len(deps) > len(preview):
                        lines.append(f"- ... y {len(deps) - len(preview)} más")
                else:
                    lines.append("- Sin datos")

        if snapshot.notes:
            lines.append("")
            lines.append("## Observaciones de escaneo")
            for note in snapshot.notes:
                lines.append(f"- {note}")

        lines.append("")
        lines.append("## Estructura incluida")
        lines.append("```text")
        tree_lines = self.build_tree_lines(snapshot)
        if tree_lines:
            lines.extend(tree_lines)
        else:
            lines.append("(sin archivos incluidos)")
        lines.append("```")

        if important_files:
            lines.append("")
            lines.append("## Archivos clave detectados")
            for rel_path in sorted(important_files):
                if rel_path in snapshot.files and snapshot.files[rel_path].included:
                    lines.append(f"- `{rel_path}`")

        lines.append("")
        lines.append("## Resumen funcional por archivo")
        if not included_text_files:
            lines.append("- No hay archivos de texto incluidos para resumir.")
            return "\n".join(lines)

        for file_info in included_text_files:
            lines.append("")
            lines.append(f"### {file_info.relative_path}")
            lines.append(self.describe_file(file_info))

            if mode == "hybrid" and file_info.relative_path in important_files:
                code = self.read_text(file_info, limit=MAX_CODE_SNIPPET_CHARS)
                if code.strip():
                    lines.append("")
                    lines.append(f"```{self.language_for(file_info.extension)}")
                    lines.append(code)
                    if self.was_truncated(file_info, MAX_CODE_SNIPPET_CHARS):
                        lines.append("")
                        lines.append("# [contenido truncado por Picaflor]")
                    lines.append("```")

            if mode == "full":
                code = self.read_text(file_info, limit=MAX_CODE_SNIPPET_CHARS)
                if code.strip():
                    lines.append("")
                    lines.append(f"```{self.language_for(file_info.extension)}")
                    lines.append(code)
                    if self.was_truncated(file_info, MAX_CODE_SNIPPET_CHARS):
                        lines.append("")
                        lines.append("# [contenido truncado por Picaflor]")
                    lines.append("```")

        return "\n".join(lines)

    def build_tree_lines(self, snapshot: ProjectSnapshot) -> list[str]:
        paths = [file.relative_path for file in snapshot.included_files()]
        if not paths:
            return []

        tree: dict[str, dict] = {}
        for rel_path in sorted(paths):
            node = tree
            for part in rel_path.split("/"):
                node = node.setdefault(part, {})

        lines: list[str] = []

        def walk(branch: dict[str, dict], prefix: str = "") -> None:
            items = sorted(branch.items(), key=lambda item: (len(item[1]) == 0, item[0].lower()))
            for index, (name, child) in enumerate(items):
                is_last = index == len(items) - 1
                connector = "└── " if is_last else "├── "
                lines.append(prefix + connector + name)
                next_prefix = prefix + ("    " if is_last else "│   ")
                walk(child, next_prefix)

        walk(tree)
        return lines

    def important_files(self, snapshot: ProjectSnapshot) -> list[str]:
        important: list[str] = []
        patterns = (
            "package.json",
            "requirements.txt",
            "pyproject.toml",
            "README.md",
            "tsconfig.json",
            "vite.config.ts",
            "vite.config.js",
            "vite.config.mjs",
            "vite.config.cjs",
        )

        for rel_path in sorted(snapshot.files):
            lower = rel_path.lower()
            name = Path(rel_path).name.lower()

            if name in {pattern.lower() for pattern in patterns}:
                important.append(rel_path)
                continue

            if any(token in lower for token in ("/app.", "/main.", "/index.", "/store/", "/routes/", "/router/", "/electron/")):
                important.append(rel_path)
                continue

            if "/components/" in lower and Path(rel_path).stem[:1].isupper():
                important.append(rel_path)

        return important[:40]

    def describe_file(self, file_info: FileInfo) -> str:
        rel = file_info.relative_path
        name = Path(rel).name
        stem = Path(rel).stem
        parts = [part.lower() for part in Path(rel).parts]
        content = self.read_text(file_info, limit=MAX_SUMMARIZER_READ_CHARS)
        line_count = content.count("\n") + 1 if content else 0
        imports = self.extract_imports(content)
        symbols = self.extract_symbols(content)

        purpose = self.infer_purpose(rel, content)

        fragments = [f"Propósito estimado: {purpose}"]
        fragments.append(f"Tamaño aproximado: {line_count} líneas visibles analizadas.")

        if imports:
            fragments.append(f"Dependencias o módulos referenciados: {', '.join(imports[:8])}.")
        if symbols:
            fragments.append(f"Elementos principales detectados: {', '.join(symbols[:10])}.")

        if name == "package.json":
            package_detail = self.describe_package_json(content)
            if package_detail:
                fragments.append(package_detail)

        if name == "requirements.txt":
            reqs = [line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("#")]
            if reqs:
                fragments.append(f"Lista dependencias Python del proyecto. Paquetes detectados: {', '.join(reqs[:12])}.")
                if len(reqs) > 12:
                    fragments.append(f"Hay {len(reqs) - 12} dependencias adicionales no listadas aquí.")

        if name == "pyproject.toml":
            pyproject_detail = self.describe_pyproject(content)
            if pyproject_detail:
                fragments.append(pyproject_detail)

        return " ".join(fragments)

    def infer_purpose(self, rel_path: str, content: str) -> str:
        lower = rel_path.lower()
        name = Path(rel_path).name.lower()
        stem = Path(rel_path).stem.lower()
        suffix = Path(rel_path).suffix.lower()
        parts = [part.lower() for part in Path(rel_path).parts]

        if name == "package.json":
            return "archivo de configuración principal para ecosistema Node.js que declara scripts, dependencias y metadatos del proyecto."
        if name == "requirements.txt":
            return "archivo de dependencias Python usado para instalar librerías necesarias del proyecto."
        if name == "pyproject.toml":
            return "archivo moderno de configuración Python con metadatos, build system y posibles dependencias."
        if name.startswith("readme"):
            return "documentación principal del proyecto, útil para entender objetivos, uso y decisiones técnicas."
        if stem == "main":
            return "punto de entrada principal desde donde suele arrancar la aplicación."
        if stem == "app":
            return "componente o módulo raíz que normalmente organiza la estructura general de la aplicación."
        if "electron" in parts and stem == "main":
            return "proceso principal de Electron, encargado de crear ventanas y manejar la integración nativa."
        if "electron" in parts and stem == "preload":
            return "puente seguro entre Electron y el frontend para exponer APIs controladas."
        if "store" in parts:
            return "módulo de estado global o compartido que centraliza datos y acciones del proyecto."
        if "components" in parts:
            return "componente reutilizable de interfaz que encapsula parte de la UI."
        if "pages" in parts or "views" in parts:
            return "pantalla o vista de alto nivel que representa una sección funcional de la aplicación."
        if "routes" in parts or "router" in parts:
            return "configuración de navegación o enrutamiento entre pantallas o endpoints."
        if suffix in {".css", ".scss", ".sass", ".less"}:
            return "archivo de estilos que define apariencia visual, layout o tema de la interfaz."
        if suffix in {".json"}:
            return "archivo estructurado de configuración o datos consumidos por la aplicación."
        if suffix in {".md"}:
            return "archivo de documentación o notas del proyecto."
        if suffix in {".html"}:
            return "documento base o plantilla HTML usada por la aplicación."
        if suffix in {".py"}:
            if "tk" in content.lower() or "customtkinter" in content.lower():
                return "módulo Python relacionado con interfaz gráfica o comportamiento visual de la app."
            return "módulo Python que aporta lógica, utilidades o flujo funcional al proyecto."
        if suffix in {".ts", ".tsx", ".js", ".jsx", ".cjs", ".mjs"}:
            if "return (" in content or "jsx" in content.lower() or "<div" in content.lower():
                return "módulo de interfaz o componente con lógica de presentación y comportamiento."
            return "módulo de lógica, configuración o integración del proyecto."
        return "archivo de soporte que forma parte del funcionamiento general del proyecto."

    def extract_imports(self, content: str) -> list[str]:
        if not content:
            return []

        patterns = [
            r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]',
            r'import\s+[\'"]([^\'"]+)[\'"]',
            r'require\([\'"]([^\'"]+)[\'"]\)',
            r'from\s+([a-zA-Z0-9_\.]+)\s+import\s+',
            r'import\s+([a-zA-Z0-9_\.]+)',
        ]

        found: list[str] = []
        for pattern in patterns:
            for match in re.findall(pattern, content):
                if match not in found:
                    found.append(match)
        return found[:20]

    def extract_symbols(self, content: str) -> list[str]:
        if not content:
            return []

        patterns = [
            r'function\s+([A-Za-z_][A-Za-z0-9_]*)',
            r'class\s+([A-Za-z_][A-Za-z0-9_]*)',
            r'const\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:\(|async|\{)?',
            r'export\s+default\s+function\s+([A-Za-z_][A-Za-z0-9_]*)',
            r'def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(',
        ]

        found: list[str] = []
        for pattern in patterns:
            for match in re.findall(pattern, content):
                if match not in found:
                    found.append(match)
        return found[:20]

    def describe_package_json(self, content: str) -> str:
        try:
            data = json.loads(content)
        except Exception:
            return ""

        scripts = sorted((data.get("scripts") or {}).keys())
        deps = sorted((data.get("dependencies") or {}).keys())
        dev_deps = sorted((data.get("devDependencies") or {}).keys())

        fragments = []
        if scripts:
            fragments.append(f"Scripts detectados: {', '.join(scripts[:12])}.")
        if deps:
            fragments.append(f"Dependencias runtime detectadas: {', '.join(deps[:12])}.")
            if len(deps) > 12:
                fragments.append(f"Hay {len(deps) - 12} dependencias runtime adicionales.")
        if dev_deps:
            fragments.append(f"Dependencias de desarrollo detectadas: {', '.join(dev_deps[:12])}.")
            if len(dev_deps) > 12:
                fragments.append(f"Hay {len(dev_deps) - 12} dependencias de desarrollo adicionales.")

        return " ".join(fragments)

    def describe_pyproject(self, content: str) -> str:
        try:
            data = tomllib.loads(content)
        except Exception:
            return ""

        fragments = []
        project_data = data.get("project", {})
        if project_data.get("name"):
            fragments.append(f"Nombre detectado en pyproject: {project_data.get('name')}.")
        if project_data.get("dependencies"):
            deps = project_data.get("dependencies", [])
            fragments.append(f"Dependencias declaradas: {', '.join(deps[:10])}.")
        return " ".join(fragments)

    def read_text(self, file_info: FileInfo, limit: int = MAX_SUMMARIZER_READ_CHARS) -> str:
        try:
            text = Path(file_info.absolute_path).read_text(encoding="utf-8", errors="ignore")
            return text[:limit]
        except Exception:
            return ""

    def was_truncated(self, file_info: FileInfo, limit: int) -> bool:
        try:
            text = Path(file_info.absolute_path).read_text(encoding="utf-8", errors="ignore")
            return len(text) > limit
        except Exception:
            return False

    def language_for(self, extension: str) -> str:
        mapping = {
            ".py": "py",
            ".ts": "ts",
            ".tsx": "tsx",
            ".js": "js",
            ".jsx": "jsx",
            ".json": "json",
            ".md": "md",
            ".html": "html",
            ".css": "css",
            ".scss": "scss",
            ".toml": "toml",
            ".yml": "yaml",
            ".yaml": "yaml",
            ".cjs": "js",
            ".mjs": "js",
        }
        return mapping.get(extension.lower(), "txt")