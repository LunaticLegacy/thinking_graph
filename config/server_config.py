"""Server runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass
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


@dataclass(slots=True)
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 5000
    debug: bool = True
    enable_cors: bool = True

    @classmethod
    def from_env(cls) -> "ServerConfig":
        host = os.getenv("APP_HOST", "0.0.0.0")

        port_raw = os.getenv("APP_PORT", "5000")
        try:
            port = int(port_raw)
        except ValueError:
            port = 5000

        debug = _env_bool("APP_DEBUG", True)
        enable_cors = _env_bool("APP_ENABLE_CORS", True)

        return cls(host=host, port=port, debug=debug, enable_cors=enable_cors)
