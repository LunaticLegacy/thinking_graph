"""Tests for database path resolution behavior."""

from __future__ import annotations

import tempfile
from pathlib import Path

from config.database_config import DatabaseConfig
from config.paths_config import PathsConfig


def _make_project_root() -> Path:
    base = Path.cwd() / ".tmp"
    base.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix="db_cfg_", dir=str(base)))


def _build_paths(project_root: Path) -> PathsConfig:
    data_dir = project_root / "data"
    return PathsConfig(
        project_root=project_root,
        template_dir=str(project_root / "templates"),
        static_dir=str(project_root / "static"),
        data_dir=str(data_dir),
        project_db_path=str(data_dir / "thinking_graph.db"),
        default_db_path=str(project_root / "fallback.db"),
    )


def test_database_config_defaults_to_project_db_path(monkeypatch):
    monkeypatch.delenv("THINKING_GRAPH_DB", raising=False)
    project_root = _make_project_root()
    paths = _build_paths(project_root)

    config = DatabaseConfig.from_sources(paths=paths, data={"db_path": ""})

    assert config.db_path == str(project_root / "data" / "thinking_graph.db")


def test_database_config_respects_configured_relative_path(monkeypatch):
    monkeypatch.delenv("THINKING_GRAPH_DB", raising=False)
    project_root = _make_project_root()
    paths = _build_paths(project_root)

    config = DatabaseConfig.from_sources(paths=paths, data={"db_path": "data/custom.db"})

    assert config.db_path == str(project_root / "data" / "custom.db")


def test_database_config_env_override_has_highest_priority(monkeypatch):
    monkeypatch.setenv("THINKING_GRAPH_DB", "data/env_override.db")
    project_root = _make_project_root()
    paths = _build_paths(project_root)

    config = DatabaseConfig.from_sources(paths=paths, data={"db_path": "data/custom.db"})

    assert config.db_path == str(project_root / "data" / "env_override.db")
