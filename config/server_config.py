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
    debug: bool = False
    enable_cors: bool = False
    allow_runtime_settings_write: bool = False
    allow_db_fallback: bool = False
    trusted_proxy_hops: int = 0

    @classmethod
    def from_sources(cls, data: Mapping[str, object] | None = None) -> "ServerConfig":
        section = data or {}

        host_default = _to_str(section.get("host"), "0.0.0.0")
        port_default = _to_int(section.get("port"), 5000)
        debug_default = _to_bool(section.get("debug"), False)
        cors_default = _to_bool(section.get("enable_cors"), False)
        runtime_settings_default = _to_bool(
            section.get("allow_runtime_settings_write"),
            False,
        )
        db_fallback_default = _to_bool(section.get("allow_db_fallback"), False)
        trusted_proxy_hops_default = max(_to_int(section.get("trusted_proxy_hops"), 0), 0)

        host = os.getenv("APP_HOST", host_default)
        port = _to_int(os.getenv("APP_PORT"), port_default)
        debug = _env_bool("APP_DEBUG", debug_default)
        enable_cors = _env_bool("APP_ENABLE_CORS", cors_default)
        allow_runtime_settings_write = _env_bool(
            "APP_ALLOW_RUNTIME_SETTINGS_WRITE",
            runtime_settings_default,
        )
        allow_db_fallback = _env_bool("APP_ALLOW_DB_FALLBACK", db_fallback_default)
        trusted_proxy_hops = max(
            _to_int(os.getenv("APP_TRUSTED_PROXY_HOPS"), trusted_proxy_hops_default),
            0,
        )

        return cls(
            host=host,
            port=port,
            debug=debug,
            enable_cors=enable_cors,
            allow_runtime_settings_write=allow_runtime_settings_write,
            allow_db_fallback=allow_db_fallback,
            trusted_proxy_hops=trusted_proxy_hops,
        )

    @classmethod
    def from_env(cls) -> "ServerConfig":
        return cls.from_sources(data=None)
