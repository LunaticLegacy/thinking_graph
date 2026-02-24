"""Flask routes for Thinking Graph frontend + APIs."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Mapping

from flask import Blueprint, current_app, jsonify, render_template, request

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


@web_bp.post("/api/graphs/load")
def load_graph():
    payload = GraphLoadPayload.from_mapping(payload_mapping())
    try:
        result = graph_service().load_graph(payload, actor=actor_name(), reason=payload.reason)
    except ValueError as exc:
        return jsonify(to_json_ready(ErrorResponse(error=str(exc)))), 400
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
        answer = llm_service().ask(payload)
    except ValueError as exc:
        return jsonify(to_json_ready(ErrorResponse(error=str(exc)))), 400
    except Exception as exc:
        return jsonify(to_json_ready(ErrorResponse(error=f"LLM request failed: {exc}"))), 502

    return jsonify(to_json_ready(answer))


@web_bp.post("/api/llm/review-graph")
def llm_review_graph():
    snapshot = graph_service().graph_snapshot()
    try:
        result = llm_service().review_graph(snapshot)
    except ValueError as exc:
        return jsonify(to_json_ready(ErrorResponse(error=str(exc)))), 400
    except Exception as exc:
        return jsonify(to_json_ready(ErrorResponse(error=f"LLM review failed: {exc}"))), 502

    return jsonify(to_json_ready(result))
