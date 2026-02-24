"""Database runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass
import os

from config.paths_config import PathsConfig


@dataclass(slots=True)
class DatabaseConfig:
    db_path: str

    @classmethod
    def from_env(cls, paths: PathsConfig) -> "DatabaseConfig":
        return cls(db_path=os.getenv("THINKING_GRAPH_DB", paths.default_db_path))
