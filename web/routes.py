"""Flask routes for Thinking Graph frontend + APIs."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any
import os
import re
from typing import Mapping

from flask import Blueprint, current_app, jsonify, render_template, request

from backend.services import LLMService
from config import LLMConfig
from config.llm_config import LLMAPIProfile, LLMLocalRuntimeProfile
from datamodels.ai_llm_models import LLMChatRequest
from datamodels.graph_models import (
    AuditQuery,
    AuditsResponse,
    ConnectionCreatePayload,
    ConnectionsResponse,
    ConnectionUpdatePayload,
    DeletePayload,
    ErrorResponse,
    GraphClearPayload,
    GraphDeletePayload,
    GraphImportPayload,
    GraphLoadPayload,
    GraphSavePayload,
    HealthResponse,
    NodeCreatePayload,
    NodeUpdatePayload,
    NodesResponse,
    OkResponse,
    SavedGraphsResponse,
)

web_bp = Blueprint("web", __name__)

DEFAULT_NODE_COLOR = "#157f83"
SUPPORTED_LLM_BACKENDS: set[str] = {"remote_api", "local_api", "onnxruntime", "openvino"}
DEFAULT_LLM_SETTINGS: dict[str, Any] = {
    "backend": "remote_api",
    "remote_api": {
        "api_key": "",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
    "local_api": {
        "api_key": "",
        "base_url": "http://127.0.0.1:11434/v1",
        "model": "qwen2.5:7b",
    },
    "local_runtime": {
        "model": "qwen2.5-7b-instruct",
        "model_dir": "models",
        "npu_device": "NPU",
        "require_npu": True,
        "onnx_provider": "",
    },
}

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]

import toml

LLM_NODE_COLOR_PALETTE: tuple[str, ...] = (
    DEFAULT_NODE_COLOR,
    "#2d936c",
    "#3f88c5",
    "#f4a259",
    "#d1495b",
    "#6c757d",
)


def normalize_hex_color(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    color = value.strip().lower()
    if re.fullmatch(r"#(?:[0-9a-f]{6})", color):
        return color
    return None


def pick_llm_node_color(index: int, provided_color: object, used_colors: set[str]) -> str:
    normalized = normalize_hex_color(provided_color)
    if normalized and normalized not in used_colors:
        return normalized

    palette_size = len(LLM_NODE_COLOR_PALETTE)
    for offset in range(palette_size):
        candidate = LLM_NODE_COLOR_PALETTE[(index + offset) % palette_size]
        if candidate not in used_colors:
            return candidate
    return LLM_NODE_COLOR_PALETTE[index % palette_size]


def runtime_config():
    return current_app.extensions.get("runtime_config")


def app_config_path() -> Path:
    config_name = os.getenv("APP_CONFIG_FILE", "app_config.toml").strip() or "app_config.toml"
    config_path = Path(config_name)
    if config_path.is_absolute():
        return config_path

    runtime = runtime_config()
    root = (
        Path(runtime.paths.project_root)
        if runtime is not None and hasattr(runtime, "paths")
        else Path(__file__).resolve().parent.parent
    )
    return root / config_path


def _as_mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    return {}


def _as_str(value: object, default: str = "") -> str:
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return default
    return str(value).strip()


def _as_bool(value: object, default: bool) -> bool:
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


def _normalize_llm_settings(raw: Mapping[str, object] | None) -> dict[str, Any]:
    section = raw or {}
    remote_api_raw = _as_mapping(section.get("remote_api"))
    local_api_raw = _as_mapping(section.get("local_api"))
    local_runtime_raw = _as_mapping(section.get("local_runtime"))

    backend = _as_str(section.get("backend"), DEFAULT_LLM_SETTINGS["backend"]).lower()
    if backend not in SUPPORTED_LLM_BACKENDS:
        backend = str(DEFAULT_LLM_SETTINGS["backend"])

    remote_defaults = _as_mapping(DEFAULT_LLM_SETTINGS["remote_api"])
    local_defaults = _as_mapping(DEFAULT_LLM_SETTINGS["local_api"])
    runtime_defaults = _as_mapping(DEFAULT_LLM_SETTINGS["local_runtime"])

    normalized = {
        "backend": backend,
        "remote_api": {
            "api_key": _as_str(
                remote_api_raw.get("api_key"),
                _as_str(remote_defaults.get("api_key"), ""),
            ),
            "base_url": _as_str(
                remote_api_raw.get("base_url"),
                _as_str(remote_defaults.get("base_url"), ""),
            ),
            "model": _as_str(
                remote_api_raw.get("model"),
                _as_str(remote_defaults.get("model"), ""),
            ),
        },
        "local_api": {
            "api_key": _as_str(
                local_api_raw.get("api_key"),
                _as_str(local_defaults.get("api_key"), ""),
            ),
            "base_url": _as_str(
                local_api_raw.get("base_url"),
                _as_str(local_defaults.get("base_url"), ""),
            ),
            "model": _as_str(
                local_api_raw.get("model"),
                _as_str(local_defaults.get("model"), ""),
            ),
        },
        "local_runtime": {
            "model": _as_str(
                local_runtime_raw.get("model"),
                _as_str(runtime_defaults.get("model"), ""),
            ),
            "model_dir": _as_str(
                local_runtime_raw.get("model_dir"),
                _as_str(runtime_defaults.get("model_dir"), ""),
            ),
            "npu_device": _as_str(
                local_runtime_raw.get("npu_device"),
                _as_str(runtime_defaults.get("npu_device"), ""),
            ),
            "require_npu": _as_bool(
                local_runtime_raw.get("require_npu"),
                _as_bool(runtime_defaults.get("require_npu"), True),
            ),
            "onnx_provider": _as_str(
                local_runtime_raw.get("onnx_provider"),
                _as_str(runtime_defaults.get("onnx_provider"), ""),
            ),
        },
    }
    return normalized


def _resolve_path_to_project_root(value: str, project_root: Path) -> str:
    raw = Path(value)
    if raw.is_absolute():
        return str(raw)
    return str(project_root / raw)


def _build_llm_config_from_settings(
    llm_settings: Mapping[str, object],
    *,
    project_root: Path,
) -> LLMConfig:
    normalized = _normalize_llm_settings(llm_settings)

    remote_settings = _as_mapping(normalized.get("remote_api"))
    local_settings = _as_mapping(normalized.get("local_api"))
    runtime_settings = _as_mapping(normalized.get("local_runtime"))

    remote_api = LLMAPIProfile(
        api_key=_as_str(remote_settings.get("api_key"), "") or None,
        base_url=_as_str(remote_settings.get("base_url"), "https://api.openai.com/v1"),
        model=_as_str(remote_settings.get("model"), "gpt-4o-mini"),
    )
    local_api = LLMAPIProfile(
        api_key=_as_str(local_settings.get("api_key"), "") or None,
        base_url=_as_str(local_settings.get("base_url"), "http://127.0.0.1:11434/v1"),
        model=_as_str(local_settings.get("model"), "qwen2.5:7b"),
    )
    local_runtime = LLMLocalRuntimeProfile(
        model=_as_str(runtime_settings.get("model"), "qwen2.5-7b-instruct"),
        model_dir=_resolve_path_to_project_root(
            _as_str(runtime_settings.get("model_dir"), "models"),
            project_root,
        ),
        npu_device=_as_str(runtime_settings.get("npu_device"), "NPU"),
        require_npu=_as_bool(runtime_settings.get("require_npu"), True),
        onnx_provider=_as_str(runtime_settings.get("onnx_provider"), "") or None,
    )

    backend = _as_str(normalized.get("backend"), "remote_api").lower()
    if backend not in SUPPORTED_LLM_BACKENDS:
        backend = "remote_api"

    selected_api = local_api if backend == "local_api" else remote_api
    selected_model = local_runtime.model if backend in {"onnxruntime", "openvino"} else selected_api.model

    return LLMConfig(
        backend=backend,
        remote_api=remote_api,
        local_api=local_api,
        local_runtime=local_runtime,
        api_key=selected_api.api_key,
        base_url=selected_api.base_url,
        model=selected_model,
        model_dir=local_runtime.model_dir,
        npu_device=local_runtime.npu_device,
        require_npu=local_runtime.require_npu,
        onnx_provider=local_runtime.onnx_provider,
    )


def _load_app_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}

    raw_text = config_path.read_text(encoding="utf-8-sig")
    if not raw_text.strip():
        return {}

    if tomllib is not None:
        parsed: Any = tomllib.loads(raw_text)
    else:  # pragma: no cover
        parsed = toml.loads(raw_text)

    if not isinstance(parsed, dict):
        raise ValueError(f"invalid config format: {config_path}")
    return parsed


def _write_app_config(config_path: Path, document: Mapping[str, Any]) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    rendered = toml.dumps(dict(document))
    if not rendered.endswith("\n"):
        rendered += "\n"
    config_path.write_text(rendered, encoding="utf-8")


def graph_service():
    return current_app.extensions["graph_service"]


def llm_service():
    return current_app.extensions["llm_service"]


def actor_name() -> str:
    return request.headers.get("X-Actor", "frontend-user")


def payload_mapping() -> Mapping[str, object]:
    payload = request.get_json(silent=True)
    if isinstance(payload, Mapping):
        return payload
    return {}


def to_json_ready(value: object) -> object:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, list):
        return [to_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [to_json_ready(item) for item in value]
    return value


@web_bp.get("/")
def index():
    return render_template("index.html")


@web_bp.get("/health")
def health_check():
    return jsonify(to_json_ready(HealthResponse()))


@web_bp.get("/api/graph")
def get_graph():
    return jsonify(to_json_ready(graph_service().graph_snapshot()))


@web_bp.get("/api/settings")
def get_settings():
    config_path = app_config_path()
    try:
        config_doc = _load_app_config(config_path)
    except Exception as exc:
        return jsonify(to_json_ready(ErrorResponse(error=f"failed to read app_config: {exc}"))), 500

    llm_settings = _normalize_llm_settings(_as_mapping(config_doc.get("llm")))
    return jsonify(
        {
            "config_path": str(config_path),
            "llm": llm_settings,
        }
    )


@web_bp.put("/api/settings")
def update_settings():
    incoming = payload_mapping()
    llm_block = _as_mapping(incoming.get("llm")) if "llm" in incoming else incoming
    llm_settings = _normalize_llm_settings(llm_block)

    config_path = app_config_path()
    try:
        config_doc = _load_app_config(config_path)
    except Exception as exc:
        return jsonify(to_json_ready(ErrorResponse(error=f"failed to read app_config: {exc}"))), 500

    config_doc["llm"] = llm_settings

    try:
        _write_app_config(config_path, config_doc)
    except OSError as exc:
        return jsonify(to_json_ready(ErrorResponse(error=f"failed to write app_config: {exc}"))), 500

    runtime = runtime_config()
    project_root = (
        Path(runtime.paths.project_root)
        if runtime is not None and hasattr(runtime, "paths")
        else Path(__file__).resolve().parent.parent
    )
    applied_llm = _build_llm_config_from_settings(llm_settings, project_root=project_root)

    if runtime is not None and hasattr(runtime, "llm"):
        runtime.llm = applied_llm
    current_app.extensions["llm_service"] = LLMService(applied_llm)

    return jsonify(
        {
            "ok": True,
            "config_path": str(config_path),
            "llm": llm_settings,
        }
    )


@web_bp.route("/api/nodes", methods=["GET", "POST"])
def nodes():
    if request.method == "GET":
        include_deleted = request.args.get("include_deleted", "false").lower() == "true"
        response = NodesResponse(nodes=graph_service().list_nodes(include_deleted=include_deleted))
        return jsonify(to_json_ready(response))

    payload = NodeCreatePayload.from_mapping(payload_mapping())
    try:
        node = graph_service().create_node(payload, actor=actor_name(), reason=payload.reason)
    except ValueError as exc:
        return jsonify(to_json_ready(ErrorResponse(error=str(exc)))), 400
    return jsonify(to_json_ready(node)), 201


@web_bp.route("/api/nodes/<node_id>", methods=["GET", "PATCH", "DELETE"])
def node_detail(node_id: str):
    if request.method == "GET":
        node = graph_service().get_node(node_id)
        if not node:
            return jsonify(to_json_ready(ErrorResponse(error="node not found"))), 404
        return jsonify(to_json_ready(node))

    if request.method == "PATCH":
        payload = NodeUpdatePayload.from_mapping(payload_mapping())
        try:
            updated = graph_service().update_node(
                node_id=node_id,
                payload=payload,
                actor=actor_name(),
                reason=payload.reason,
            )
        except ValueError as exc:
            return jsonify(to_json_ready(ErrorResponse(error=str(exc)))), 400

        if not updated:
            return jsonify(to_json_ready(ErrorResponse(error="node not found"))), 404
        return jsonify(to_json_ready(updated))

    payload = DeletePayload.from_mapping(payload_mapping())
    ok = graph_service().delete_node(node_id=node_id, actor=actor_name(), payload=payload)
    if not ok:
        return jsonify(to_json_ready(ErrorResponse(error="node not found"))), 404
    return jsonify(to_json_ready(OkResponse()))


@web_bp.route("/api/connections", methods=["GET", "POST"])
def connections():
    if request.method == "GET":
        include_deleted = request.args.get("include_deleted", "false").lower() == "true"
        response = ConnectionsResponse(
            connections=graph_service().list_connections(include_deleted=include_deleted)
        )
        return jsonify(to_json_ready(response))

    payload = ConnectionCreatePayload.from_mapping(payload_mapping())
    try:
        connection = graph_service().create_connection(
            payload=payload,
            actor=actor_name(),
            reason=payload.reason,
        )
    except ValueError as exc:
        return jsonify(to_json_ready(ErrorResponse(error=str(exc)))), 400
    return jsonify(to_json_ready(connection)), 201


@web_bp.route("/api/connections/<connection_id>", methods=["PATCH", "DELETE"])
def connection_detail(connection_id: str):
    if request.method == "PATCH":
        payload = ConnectionUpdatePayload.from_mapping(payload_mapping())
        try:
            updated = graph_service().update_connection(
                conn_id=connection_id,
                payload=payload,
                actor=actor_name(),
                reason=payload.reason,
            )
        except ValueError as exc:
            return jsonify(to_json_ready(ErrorResponse(error=str(exc)))), 400

        if not updated:
            return jsonify(to_json_ready(ErrorResponse(error="connection not found"))), 404
        return jsonify(to_json_ready(updated))

    payload = DeletePayload.from_mapping(payload_mapping())
    ok = graph_service().delete_connection(
        conn_id=connection_id,
        actor=actor_name(),
        payload=payload,
    )
    if not ok:
        return jsonify(to_json_ready(ErrorResponse(error="connection not found"))), 404
    return jsonify(to_json_ready(OkResponse()))


@web_bp.get("/api/audits")
def list_audits():
    query = AuditQuery(
        entity_type=request.args.get("entity_type"),
        entity_id=request.args.get("entity_id"),
        limit=request.args.get("limit", default=200, type=int),
    )
    audits = graph_service().list_audits(query)
    return jsonify(to_json_ready(AuditsResponse(audits=audits)))


@web_bp.get("/api/audits/export")
def export_audits():
    query = AuditQuery(
        entity_type=request.args.get("entity_type"),
        entity_id=request.args.get("entity_id"),
        limit=request.args.get("limit", default=2000, type=int),
    )
    result = graph_service().export_audits(query)
    return jsonify(to_json_ready(result))


@web_bp.get("/api/audits/verify")
def verify_audit_integrity():
    return jsonify(to_json_ready(graph_service().verify_audit_integrity()))


@web_bp.get("/api/graphs/saved")
def list_saved_graphs():
    graphs = graph_service().list_saved_graphs()
    return jsonify(to_json_ready(SavedGraphsResponse(graphs=graphs)))


@web_bp.post("/api/graphs/save")
def save_graph():
    payload = GraphSavePayload.from_mapping(payload_mapping())
    try:
        result = graph_service().save_graph(payload, actor=actor_name(), reason=payload.reason)
    except ValueError as exc:
        return jsonify(to_json_ready(ErrorResponse(error=str(exc)))), 400
    return jsonify(to_json_ready(result))


@web_bp.get("/api/graphs/export")
def export_graph():
    result = graph_service().export_graph()
    return jsonify(to_json_ready(result))


@web_bp.post("/api/graphs/load")
def load_graph():
    payload = GraphLoadPayload.from_mapping(payload_mapping())
    try:
        result = graph_service().load_graph(payload, actor=actor_name(), reason=payload.reason)
    except ValueError as exc:
        return jsonify(to_json_ready(ErrorResponse(error=str(exc)))), 400
    return jsonify(to_json_ready(result))


@web_bp.post("/api/graphs/import")
def import_graph():
    payload = GraphImportPayload.from_mapping(payload_mapping())
    try:
        result = graph_service().import_graph(payload, actor=actor_name(), reason=payload.reason)
    except ValueError as exc:
        return jsonify(to_json_ready(ErrorResponse(error=str(exc)))), 400
    return jsonify(to_json_ready(result))


@web_bp.post("/api/graphs/delete")
def delete_saved_graph():
    payload = GraphDeletePayload.from_mapping(payload_mapping())
    try:
        result = graph_service().delete_saved_graph(payload, actor=actor_name(), reason=payload.reason)
    except ValueError as exc:
        error_text = str(exc)
        status = 404 if error_text == "saved graph not found" else 400
        return jsonify(to_json_ready(ErrorResponse(error=error_text))), status
    return jsonify(to_json_ready(result))


@web_bp.post("/api/graphs/clear")
def clear_graph():
    payload = GraphClearPayload.from_mapping(payload_mapping())
    result = graph_service().clear_graph(payload, actor=actor_name(), reason=payload.reason)
    return jsonify(to_json_ready(result))


@web_bp.post("/api/llm/chat")
def llm_chat():
    payload = LLMChatRequest.from_mapping(payload_mapping())
    try:
        snapshot = graph_service().graph_snapshot()
        answer = llm_service().ask(payload, graph_snapshot=snapshot)
    except ValueError as exc:
        return jsonify(to_json_ready(ErrorResponse(error=str(exc)))), 400
    except Exception as exc:
        return jsonify(to_json_ready(ErrorResponse(error=f"LLM request failed: {exc}"))), 502

    return jsonify(to_json_ready(answer))


@web_bp.post("/api/llm/generate-graph")
def llm_generate_graph():
    payload = payload_mapping()
    topic = str(payload.get("topic", "")).strip()
    language = str(payload.get("language", "zh")).strip().lower()
    if language not in {"zh", "en"}:
        language = "zh"
    if not topic:
        return jsonify(to_json_ready(ErrorResponse(error="`topic` is required."))), 400

    try:
        temperature = float(payload.get("temperature", 0.2))
    except (TypeError, ValueError):
        temperature = 0.2

    try:
        max_tokens = int(payload.get("max_tokens", 1400))
    except (TypeError, ValueError):
        max_tokens = 1400

    try:
        max_nodes = int(payload.get("max_nodes", 18))
    except (TypeError, ValueError):
        max_nodes = 18

    try:
        generated = llm_service().generate_graph_from_topic(
            topic=topic,
            temperature=temperature,
            max_tokens=max_tokens,
            max_nodes=max_nodes,
            language=language,
        )
    except ValueError as exc:
        return jsonify(to_json_ready(ErrorResponse(error=str(exc)))), 400
    except Exception as exc:
        return jsonify(to_json_ready(ErrorResponse(error=f"LLM generate graph failed: {exc}"))), 502

    if not bool(generated.get("enabled", False)):
        return jsonify(to_json_ready(generated))

    generated_nodes = generated.get("nodes")
    if not isinstance(generated_nodes, list) or not generated_nodes:
        return jsonify(
            to_json_ready(
                ErrorResponse(
                    error=str(
                        generated.get("message")
                        or "LLM did not return valid nodes for graph generation."
                    )
                )
            )
        ), 502

    actor = actor_name()
    reason = f"llm generate graph from topic: {topic[:80]}"

    graph_service().clear_graph(
        GraphClearPayload(reason=reason),
        actor=actor,
        reason=reason,
    )

    node_id_map: dict[str, str] = {}
    created_nodes = 0
    created_connections = 0
    used_colors: set[str] = set()

    for index, item in enumerate(generated_nodes):
        if not isinstance(item, Mapping):
            continue

        source_node_id = str(item.get("id", "")).strip()
        node_color = pick_llm_node_color(index, item.get("color"), used_colors)
        node_payload = NodeCreatePayload.from_mapping(
            {
                "content": item.get("content", ""),
                "summary": item.get("summary", ""),
                "confidence": item.get("confidence", 1.0),
                "color": node_color,
                "reason": reason,
            }
        )
        try:
            created = graph_service().create_node(
                payload=node_payload,
                actor=actor,
                reason=reason,
            )
        except ValueError:
            continue

        created_nodes += 1
        used_colors.add(node_color)
        if source_node_id:
            node_id_map[source_node_id] = created.id

    generated_connections = generated.get("connections")
    if isinstance(generated_connections, list):
        for item in generated_connections:
            if not isinstance(item, Mapping):
                continue

            old_source = str(item.get("source_id", "")).strip()
            old_target = str(item.get("target_id", "")).strip()
            new_source = node_id_map.get(old_source)
            new_target = node_id_map.get(old_target)
            if not new_source or not new_target or new_source == new_target:
                continue

            conn_payload = ConnectionCreatePayload.from_mapping(
                {
                    "source_id": new_source,
                    "target_id": new_target,
                    "conn_type": item.get("conn_type", "relates"),
                    "description": item.get("description", ""),
                    "strength": item.get("strength", 1.0),
                    "reason": reason,
                }
            )
            try:
                graph_service().create_connection(
                    payload=conn_payload,
                    actor=actor,
                    reason=reason,
                )
            except ValueError:
                continue
            created_connections += 1

    return jsonify(
        {
            "enabled": True,
            "model": generated.get("model"),
            "message": "graph replaced by LLM generation",
            "node_count": created_nodes,
            "connection_count": created_connections,
        }
    )


@web_bp.post("/api/llm/review-graph")
def llm_review_graph():
    payload = payload_mapping()
    language = str(payload.get("language", "zh")).strip().lower()
    if language not in {"zh", "en"}:
        language = "zh"
    snapshot = graph_service().graph_snapshot()
    try:
        result = llm_service().review_graph(snapshot, language=language)
    except ValueError as exc:
        return jsonify(to_json_ready(ErrorResponse(error=str(exc)))), 400
    except Exception as exc:
        return jsonify(to_json_ready(ErrorResponse(error=f"LLM review failed: {exc}"))), 502

    return jsonify(to_json_ready(result))
