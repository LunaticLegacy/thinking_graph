"""Dataclass models for Thinking Graph domain and API payloads."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Mapping, TypeAlias
import uuid


JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ConnectionType(str, Enum):
    SUPPORTS = "supports"
    OPPOSES = "opposes"
    RELATES = "relates"
    LEADS_TO = "leads_to"
    DERIVES_FROM = "derives_from"

    @classmethod
    def values(cls) -> set[str]:
        return {item.value for item in cls}


class EntityType(str, Enum):
    NODE = "node"
    CONNECTION = "connection"


class AuditAction(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


@dataclass(slots=True)
class Position:
    x: float = 0.0
    y: float = 0.0

    @classmethod
    def from_mapping(cls, data: Mapping[str, object] | None) -> "Position":
        if not data:
            return cls()
        return cls(
            x=_to_float(data.get("x"), 0.0),
            y=_to_float(data.get("y"), 0.0),
        )


@dataclass(slots=True)
class Node:
    content: str
    summary: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    position: Position = field(default_factory=Position)
    color: str = "#157f83"
    size: float = 1.0
    tags: list[str] = field(default_factory=list)
    confidence: float = 1.0
    evidence: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    version: int = 1
    is_deleted: bool = False

    def to_state(self) -> JsonObject:
        return {
            "id": self.id,
            "content": self.content,
            "summary": self.summary,
            "position": {"x": self.position.x, "y": self.position.y},
            "color": self.color,
            "size": self.size,
            "tags": list(self.tags),
            "confidence": self.confidence,
            "evidence": list(self.evidence),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
            "is_deleted": self.is_deleted,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, JsonValue]) -> "Node":
        position_raw = state.get("position")
        position_data = position_raw if isinstance(position_raw, Mapping) else {}

        return cls(
            id=_to_str(state.get("id"), str(uuid.uuid4())),
            content=_to_str(state.get("content"), ""),
            summary=_to_str(state.get("summary"), ""),
            position=Position(
                x=_to_float(position_data.get("x"), 0.0),
                y=_to_float(position_data.get("y"), 0.0),
            ),
            color=_to_str(state.get("color"), "#157f83"),
            size=_to_float(state.get("size"), 1.0),
            tags=_to_str_list(state.get("tags")),
            confidence=_to_float(state.get("confidence"), 1.0),
            evidence=_to_str_list(state.get("evidence")),
            created_at=_to_str(state.get("created_at"), utc_now()),
            updated_at=_to_str(state.get("updated_at"), utc_now()),
            version=_to_int(state.get("version"), 1),
            is_deleted=_to_bool(state.get("is_deleted"), False),
        )


@dataclass(slots=True)
class Connection:
    source_id: str
    target_id: str
    conn_type: str = ConnectionType.RELATES.value
    description: str = ""
    strength: float = 1.0
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    version: int = 1
    is_deleted: bool = False

    def to_state(self) -> JsonObject:
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "conn_type": self.conn_type,
            "description": self.description,
            "strength": self.strength,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
            "is_deleted": self.is_deleted,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, JsonValue]) -> "Connection":
        conn_type = _to_str(state.get("conn_type"), ConnectionType.RELATES.value)
        if conn_type not in ConnectionType.values():
            conn_type = ConnectionType.RELATES.value

        return cls(
            id=_to_str(state.get("id"), str(uuid.uuid4())),
            source_id=_to_str(state.get("source_id"), ""),
            target_id=_to_str(state.get("target_id"), ""),
            conn_type=conn_type,
            description=_to_str(state.get("description"), ""),
            strength=_to_float(state.get("strength"), 1.0),
            created_at=_to_str(state.get("created_at"), utc_now()),
            updated_at=_to_str(state.get("updated_at"), utc_now()),
            version=_to_int(state.get("version"), 1),
            is_deleted=_to_bool(state.get("is_deleted"), False),
        )


@dataclass(slots=True)
class AuditLog:
    entity_type: str
    entity_id: str
    action: str
    actor: str
    timestamp: str = field(default_factory=utc_now)
    reason: str | None = None
    before_state: JsonObject | None = None
    after_state: JsonObject | None = None


@dataclass(slots=True)
class VisualNode:
    id: str
    label: str
    title: str
    x: float
    y: float
    color: str
    value: float
    confidence: float


@dataclass(slots=True)
class VisualEdge:
    id: str
    source: str
    target: str
    label: str
    title: str
    color: str
    width: float


@dataclass(slots=True)
class VisualizationPayload:
    nodes: list[VisualNode]
    edges: list[VisualEdge]


@dataclass(slots=True)
class GraphSnapshot:
    nodes: list[Node]
    connections: list[Connection]
    visualization: VisualizationPayload


@dataclass(slots=True)
class GraphSaveResult:
    name: str
    node_count: int
    connection_count: int
    actor: str
    saved_at: str
    message: str


@dataclass(slots=True)
class GraphLoadResult:
    name: str
    loaded_at: str
    message: str
    snapshot: GraphSnapshot


@dataclass(slots=True)
class GraphClearPayload:
    reason: str | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> "GraphClearPayload":
        return cls(reason=_to_optional_str(data.get("reason")))


@dataclass(slots=True)
class GraphClearResult:
    cleared_nodes: int
    cleared_connections: int
    cleared_at: str
    message: str


@dataclass(slots=True)
class AuditRecord:
    id: int
    entity_type: str
    entity_id: str
    action: str
    actor: str
    reason: str | None
    before_state: JsonObject | None
    after_state: JsonObject | None
    created_at: str


@dataclass(slots=True)
class AuditIntegrityReport:
    ok: bool
    issues: list[str]
    checked_at: str


@dataclass(slots=True)
class SavedGraphSummary:
    name: str
    node_count: int
    connection_count: int
    actor: str
    saved_at: str


@dataclass(slots=True)
class GraphSavePayload:
    name: str
    reason: str | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> "GraphSavePayload":
        return cls(
            name=_to_str(data.get("name"), "").strip(),
            reason=_to_optional_str(data.get("reason")),
        )


@dataclass(slots=True)
class GraphLoadPayload:
    name: str
    reason: str | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> "GraphLoadPayload":
        return cls(
            name=_to_str(data.get("name"), "").strip(),
            reason=_to_optional_str(data.get("reason")),
        )


@dataclass(slots=True)
class GraphDeletePayload:
    name: str
    reason: str | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> "GraphDeletePayload":
        return cls(
            name=_to_str(data.get("name"), "").strip(),
            reason=_to_optional_str(data.get("reason")),
        )


@dataclass(slots=True)
class GraphDeleteResult:
    name: str
    deleted_at: str
    message: str


@dataclass(slots=True)
class NodeCreatePayload:
    content: str
    summary: str = ""
    position: Position = field(default_factory=Position)
    color: str = "#157f83"
    size: float = 1.0
    tags: list[str] = field(default_factory=list)
    confidence: float = 1.0
    evidence: list[str] = field(default_factory=list)
    reason: str | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> "NodeCreatePayload":
        return cls(
            content=_to_str(data.get("content"), "").strip(),
            summary=_to_str(data.get("summary"), "").strip(),
            position=Position.from_mapping(_to_mapping(data.get("position"))),
            color=_to_str(data.get("color"), "#157f83").strip() or "#157f83",
            size=max(_to_float(data.get("size"), 1.0), 0.2),
            tags=_to_str_list(data.get("tags")),
            confidence=_to_float(data.get("confidence"), 1.0),
            evidence=_to_str_list(data.get("evidence")),
            reason=_to_optional_str(data.get("reason")),
        )


@dataclass(slots=True)
class NodeUpdatePayload:
    content: str | None = None
    summary: str | None = None
    position: Position | None = None
    color: str | None = None
    size: float | None = None
    tags: list[str] | None = None
    confidence: float | None = None
    evidence: list[str] | None = None
    reason: str | None = None
    provided_fields: set[str] = field(default_factory=set)

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> "NodeUpdatePayload":
        provided = set(data.keys())
        position_data = _to_mapping(data.get("position")) if "position" in data else None

        return cls(
            content=_to_str(data.get("content"), "").strip() if "content" in data else None,
            summary=_to_str(data.get("summary"), "").strip() if "summary" in data else None,
            position=Position.from_mapping(position_data) if position_data is not None else None,
            color=_to_str(data.get("color"), "#157f83") if "color" in data else None,
            size=max(_to_float(data.get("size"), 1.0), 0.2) if "size" in data else None,
            tags=_to_str_list(data.get("tags")) if "tags" in data else None,
            confidence=_to_float(data.get("confidence"), 1.0) if "confidence" in data else None,
            evidence=_to_str_list(data.get("evidence")) if "evidence" in data else None,
            reason=_to_optional_str(data.get("reason")),
            provided_fields=provided,
        )

    def has(self, field_name: str) -> bool:
        return field_name in self.provided_fields


@dataclass(slots=True)
class ConnectionCreatePayload:
    source_id: str
    target_id: str
    conn_type: str = ConnectionType.RELATES.value
    description: str = ""
    strength: float = 1.0
    reason: str | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> "ConnectionCreatePayload":
        return cls(
            source_id=_to_str(data.get("source_id"), "").strip(),
            target_id=_to_str(data.get("target_id"), "").strip(),
            conn_type=_to_str(data.get("conn_type"), ConnectionType.RELATES.value),
            description=_to_str(data.get("description"), "").strip(),
            strength=max(_to_float(data.get("strength"), 1.0), 0.1),
            reason=_to_optional_str(data.get("reason")),
        )


@dataclass(slots=True)
class ConnectionUpdatePayload:
    conn_type: str | None = None
    description: str | None = None
    strength: float | None = None
    reason: str | None = None
    provided_fields: set[str] = field(default_factory=set)

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> "ConnectionUpdatePayload":
        provided = set(data.keys())
        return cls(
            conn_type=_to_str(data.get("conn_type"), ConnectionType.RELATES.value) if "conn_type" in data else None,
            description=_to_str(data.get("description"), "") if "description" in data else None,
            strength=max(_to_float(data.get("strength"), 1.0), 0.1) if "strength" in data else None,
            reason=_to_optional_str(data.get("reason")),
            provided_fields=provided,
        )

    def has(self, field_name: str) -> bool:
        return field_name in self.provided_fields


@dataclass(slots=True)
class DeletePayload:
    reason: str | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, object]) -> "DeletePayload":
        return cls(reason=_to_optional_str(data.get("reason")))


@dataclass(slots=True)
class AuditQuery:
    entity_type: str | None = None
    entity_id: str | None = None
    limit: int = 200


@dataclass(slots=True)
class HealthResponse:
    ok: bool = True


@dataclass(slots=True)
class OkResponse:
    ok: bool = True


@dataclass(slots=True)
class ErrorResponse:
    error: str


@dataclass(slots=True)
class NodesResponse:
    nodes: list[Node]


@dataclass(slots=True)
class ConnectionsResponse:
    connections: list[Connection]


@dataclass(slots=True)
class AuditsResponse:
    audits: list[AuditRecord]


@dataclass(slots=True)
class SavedGraphsResponse:
    graphs: list[SavedGraphSummary]


@dataclass(slots=True)
class MessageResponse:
    message: str


def _to_mapping(value: object) -> Mapping[str, object] | None:
    return value if isinstance(value, Mapping) else None


def _to_str(value: object, default: str) -> str:
    if isinstance(value, str):
        return value
    return default if value is None else str(value)


def _to_optional_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text if text else None
    text = str(value).strip()
    return text if text else None


def _to_float(value: object, default: float) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
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


def _to_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    return default


def _to_str_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return []
