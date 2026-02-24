"""Aggregate runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config.database_config import DatabaseConfig
from config.llm_config import LLMConfig
from config.paths_config import PathsConfig
from config.server_config import ServerConfig


@dataclass(slots=True)
class RuntimeConfig:
    paths: PathsConfig
    database: DatabaseConfig
    llm: LLMConfig
    server: ServerConfig

    @classmethod
    def load(cls, project_root: Path | None = None) -> "RuntimeConfig":
        paths = PathsConfig.build(project_root=project_root)
        return cls(
            paths=paths,
            database=DatabaseConfig.from_env(paths),
            llm=LLMConfig.from_env(),
            server=ServerConfig.from_env(),
        )
