"""Regression tests for LLM graph generation fallbacks."""

from __future__ import annotations

from config import RuntimeConfig
from web import create_app
from backend.services.llm_service import LLMService


class _FakeLLMService:
    def generate_graph_from_topic(
        self,
        topic: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 1400,
        max_nodes: int = 18,
        language: str = "zh",
    ) -> dict[str, object]:
        _ = (topic, temperature, max_tokens, max_nodes, language)
        return {
            "enabled": True,
            "model": "fake-llm",
            "message": "graph generated",
            "summary": "fake summary",
            "node_count": 2,
            "connection_count": 1,
            "nodes": [
                {"id": "A", "content": "Remote work improves focus", "summary": "Remote work"},
                {"id": "B", "content": "Productivity increases", "summary": "Productivity"},
            ],
            "connections": [
                {
                    "source_id": "A",
                    "target_id": "B",
                    "conn_type": "supports",
                    "description": "N/A",
                    "strength": 1.0,
                }
            ],
        }


def test_normalize_generated_payload_fills_description_by_language():
    service = LLMService.__new__(LLMService)
    payload = {
        "nodes": [
            {"id": "n1", "content": "Remote work improves focus"},
            {"id": "n2", "content": "Productivity increases"},
        ],
        "connections": [
            {
                "source_id": "n1",
                "target_id": "n2",
                "conn_type": "supports",
                "description": "",
            }
        ],
    }

    _, en_connections = service._normalize_generated_graph_payload(
        payload,
        max_nodes=10,
        language="en",
    )
    _, zh_connections = service._normalize_generated_graph_payload(
        payload,
        max_nodes=10,
        language="zh",
    )

    assert en_connections
    assert zh_connections
    assert "supports" in en_connections[0]["description"].lower()
    assert "支持" in zh_connections[0]["description"]


def test_generate_graph_route_fills_missing_connection_description(app_config: RuntimeConfig):
    app = create_app(app_config)
    app.config["TESTING"] = True
    app.extensions["llm_service"] = _FakeLLMService()
    client = app.test_client()

    response = client.post(
        "/api/llm/generate-graph",
        json={"topic": "remote work productivity", "language": "en"},
    )
    assert response.status_code == 200

    graph_response = client.get("/api/graph")
    assert graph_response.status_code == 200
    graph_payload = graph_response.get_json() or {}
    connections = graph_payload.get("connections", [])
    assert len(connections) == 1

    description = str(connections[0].get("description", "")).strip()
    assert description
    assert description.lower() not in {"none", "n/a", "na", "null", "unknown", "tbd"}
