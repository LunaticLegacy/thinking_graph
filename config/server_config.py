"""Server runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
import os


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return default


def _to_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return default


def _to_int(value: object, default: int) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _to_str(value: object, default: str) -> str:
    if isinstance(value, str):
        text = value.strip()
        if text:
            return text
    return default


@dataclass(slots=True)
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 5000
    debug: bool = True
    enable_cors: bool = True

    @classmethod
    def from_sources(cls, data: Mapping[str, object] | None = None) -> "ServerConfig":
        section = data or {}

        host_default = _to_str(section.get("host"), "0.0.0.0")
        port_default = _to_int(section.get("port"), 5000)
        debug_default = _to_bool(section.get("debug"), True)
        cors_default = _to_bool(section.get("enable_cors"), True)

        host = os.getenv("APP_HOST", host_default)
        port = _to_int(os.getenv("APP_PORT"), port_default)
        debug = _env_bool("APP_DEBUG", debug_default)
        enable_cors = _env_bool("APP_ENABLE_CORS", cors_default)

        return cls(host=host, port=port, debug=debug, enable_cors=enable_cors)

    @classmethod
    def from_env(cls) -> "ServerConfig":
        return cls.from_sources(data=None)
