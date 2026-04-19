"""Per-request user identity resolution."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
import uuid

from flask import Request, session

from config.auth_config import AuthConfig


_SESSION_OWNER_KEY = "thinking_graph_owner_id"
_SESSION_PRINCIPAL_KEY = "thinking_graph_principal"
_ACTOR_HEADER = "X-Actor"


@dataclass(slots=True)
class RequestIdentity:
    owner_id: str
    principal: str
    actor: str
    source: str


def resolve_request_identity(auth_config: AuthConfig, request: Request) -> RequestIdentity:
    trusted_header_name = _normalize_header_name(auth_config.trusted_identity_header)
    if trusted_header_name:
        principal = _normalize_principal(request.headers.get(trusted_header_name))
        if not principal:
            raise PermissionError(
                f"missing trusted identity header: {trusted_header_name}"
            )
        owner_id = _stable_owner_id(principal)
        _persist_identity(owner_id, principal)
        return RequestIdentity(
            owner_id=owner_id,
            principal=principal,
            actor=_build_actor(principal, request),
            source="trusted-header",
        )

    owner_id = _normalize_owner_id(session.get(_SESSION_OWNER_KEY))
    principal = _normalize_principal(session.get(_SESSION_PRINCIPAL_KEY))
    if not owner_id:
        owner_id = f"anon_{uuid.uuid4().hex}"
        principal = principal or f"anonymous-{owner_id[-8:]}"
        _persist_identity(owner_id, principal)
    elif not principal:
        principal = f"anonymous-{owner_id[-8:]}"
        _persist_identity(owner_id, principal)

    return RequestIdentity(
        owner_id=owner_id,
        principal=principal,
        actor=_build_actor(principal, request),
        source="session",
    )


def _persist_identity(owner_id: str, principal: str) -> None:
    session.permanent = True
    session[_SESSION_OWNER_KEY] = owner_id
    session[_SESSION_PRINCIPAL_KEY] = principal


def _normalize_header_name(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if not re.fullmatch(r"[A-Za-z0-9-]+", text):
        return None
    return text


def _normalize_owner_id(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if len(text) > 80:
        text = text[:80]
    return re.sub(r"[^a-zA-Z0-9_-]", "_", text)


def _normalize_principal(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    return re.sub(r"\s+", " ", text)[:120]


def _stable_owner_id(principal: str) -> str:
    digest = hashlib.sha256(principal.lower().encode("utf-8")).hexdigest()[:32]
    return f"user_{digest}"


def _build_actor(principal: str, request: Request) -> str:
    client_actor = _normalize_principal(request.headers.get(_ACTOR_HEADER))
    if not client_actor or client_actor == principal:
        return principal
    return f"{principal} [{client_actor[:48]}]"
