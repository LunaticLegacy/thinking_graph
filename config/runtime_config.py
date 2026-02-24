"""Aggregate runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
import os

from config.database_config import DatabaseConfig
from config.llm_config import LLMConfig
from config.paths_config import PathsConfig
from config.server_config import ServerConfig

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]


@dataclass(slots=True)
class RuntimeConfig:
    paths: PathsConfig
    database: DatabaseConfig
    llm: LLMConfig
    server: ServerConfig

    @classmethod
    def load(cls, project_root: Path | None = None) -> "RuntimeConfig":
        root = project_root or Path(__file__).resolve().parent.parent
        raw_config = _load_root_config(root)

        paths_section = _section(raw_config, "paths")
        database_section = _section(raw_config, "database")
        llm_section = _section(raw_config, "llm")
        server_section = _section(raw_config, "server")

        paths = PathsConfig.build(project_root=root, data=paths_section)

        return cls(
            paths=paths,
            database=DatabaseConfig.from_sources(paths=paths, data=database_section),
            llm=LLMConfig.from_sources(data=llm_section, project_root=paths.project_root),
            server=ServerConfig.from_sources(data=server_section),
        )


def _load_root_config(project_root: Path) -> dict[str, Any]:
    config_name = os.getenv("APP_CONFIG_FILE", "app_config.toml").strip() or "app_config.toml"
    config_path = Path(config_name)
    if not config_path.is_absolute():
        config_path = project_root / config_path

    if not config_path.exists():
        return {}

    raw_text = config_path.read_text(encoding="utf-8-sig")

    if tomllib is not None:
        parsed: Any = tomllib.loads(raw_text)
    else:  # pragma: no cover
        import toml

        parsed = toml.loads(raw_text)

    if isinstance(parsed, dict):
        return parsed

    raise ValueError(f"Invalid config format in {config_path}")


def _section(data: Mapping[str, Any], key: str) -> Mapping[str, object]:
    value = data.get(key)
    if isinstance(value, Mapping):
        return value
    return {}
