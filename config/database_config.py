"""Database runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
import os

from config.paths_config import PathsConfig


@dataclass(slots=True)
class DatabaseConfig:
    db_path: str

    @classmethod
    def from_sources(
        cls,
        paths: PathsConfig,
        data: Mapping[str, object] | None = None,
    ) -> "DatabaseConfig":
        section = data or {}
        # Prefer project database by default. `default_db_path` should not
        # become the primary database unless explicitly wired elsewhere.
        default_path_raw = _to_str(section.get("db_path"), paths.project_db_path)

        db_path_raw = os.getenv("THINKING_GRAPH_DB", default_path_raw)
        db_path = _resolve_path(db_path_raw, paths.project_root)

        return cls(db_path=db_path)

    @classmethod
    def from_env(cls, paths: PathsConfig) -> "DatabaseConfig":
        return cls.from_sources(paths=paths, data=None)


def _to_str(value: object, default: str) -> str:
    if isinstance(value, str):
        text = value.strip()
        if text:
            return text
    return default


def _resolve_path(value: str, root: Path) -> str:
    raw = Path(value)
    resolved = raw if raw.is_absolute() else (root / raw)
    return str(resolved)
