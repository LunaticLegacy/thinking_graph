"""Authentication and request identity runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
import os


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


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return _to_bool(raw, default)


def _to_str(value: object, default: str) -> str:
    if isinstance(value, str):
        text = value.strip()
        if text:
            return text
    return default


def _to_optional_str(value: object) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        if text:
            return text
    return None


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


def _normalize_samesite(value: object, default: str) -> str:
    raw = _to_str(value, default)
    lowered = raw.lower()
    if lowered == "strict":
        return "Strict"
    if lowered == "none":
        return "None"
    return "Lax"


@dataclass(slots=True)
class AuthConfig:
    secret_key: str = "dev-insecure-change-me"
    trusted_identity_header: str | None = None
    session_cookie_name: str = "thinking_graph_session"
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "Lax"
    session_cookie_domain: str | None = None
    permanent_session_days: int = 30

    @classmethod
    def from_sources(cls, data: Mapping[str, object] | None = None) -> "AuthConfig":
        section = data or {}

        secret_key_default = _to_str(section.get("secret_key"), "dev-insecure-change-me")
        trusted_header_default = _to_optional_str(section.get("trusted_identity_header"))
        cookie_name_default = _to_str(section.get("session_cookie_name"), "thinking_graph_session")
        cookie_secure_default = _to_bool(section.get("session_cookie_secure"), False)
        samesite_default = _normalize_samesite(section.get("session_cookie_samesite"), "Lax")
        cookie_domain_default = _to_optional_str(section.get("session_cookie_domain"))
        permanent_days_default = _to_int(section.get("permanent_session_days"), 30)

        return cls(
            secret_key=os.getenv("THINKING_GRAPH_SECRET_KEY", secret_key_default),
            trusted_identity_header=_to_optional_str(
                os.getenv("THINKING_GRAPH_TRUSTED_IDENTITY_HEADER", trusted_header_default or "")
            ),
            session_cookie_name=os.getenv("THINKING_GRAPH_SESSION_COOKIE", cookie_name_default),
            session_cookie_secure=_env_bool(
                "THINKING_GRAPH_SESSION_COOKIE_SECURE",
                cookie_secure_default,
            ),
            session_cookie_samesite=_normalize_samesite(
                os.getenv("THINKING_GRAPH_SESSION_COOKIE_SAMESITE"),
                samesite_default,
            ),
            session_cookie_domain=_to_optional_str(
                os.getenv("THINKING_GRAPH_SESSION_COOKIE_DOMAIN", cookie_domain_default or "")
            ),
            permanent_session_days=max(
                _to_int(os.getenv("THINKING_GRAPH_PERMANENT_SESSION_DAYS"), permanent_days_default),
                1,
            ),
        )

    @classmethod
    def from_env(cls) -> "AuthConfig":
        return cls.from_sources(data=None)
