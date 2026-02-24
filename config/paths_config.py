"""Path-related runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
import tempfile


@dataclass(slots=True)
class PathsConfig:
    project_root: Path
    template_dir: str
    static_dir: str
    data_dir: str
    project_db_path: str
    default_db_path: str

    @classmethod
    def build(
        cls,
        project_root: Path | None = None,
        data: Mapping[str, object] | None = None,
    ) -> "PathsConfig":
        root = project_root or Path(__file__).resolve().parent.parent
        section = data or {}

        data_dir = _resolve_path(section.get("data_dir"), root, root / "data")
        template_dir = _resolve_path(section.get("template_dir"), root, root / "templates")
        static_dir = _resolve_path(section.get("static_dir"), root, root / "static")

        project_db_default = data_dir / "thinking_graph.db"
        project_db_path = _resolve_path(
            section.get("project_db_path"),
            root,
            project_db_default,
        )

        default_db_path = _resolve_path(
            section.get("default_db_path"),
            root,
            Path(tempfile.gettempdir()) / "thinking_graph.db",
        )

        data_dir.mkdir(parents=True, exist_ok=True)

        return cls(
            project_root=root,
            template_dir=str(template_dir),
            static_dir=str(static_dir),
            data_dir=str(data_dir),
            project_db_path=str(project_db_path),
            default_db_path=str(default_db_path),
        )


def _resolve_path(value: object, root: Path, fallback: Path) -> Path:
    if isinstance(value, str):
        text = value.strip()
        if text:
            raw_path = Path(text)
            return raw_path if raw_path.is_absolute() else (root / raw_path)
    return fallback
