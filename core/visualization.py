"""Visualization payload helpers for web graph rendering."""

from __future__ import annotations

from datamodels.graph_models import (
    Connection,
    ConnectionType,
    Node,
    VisualEdge,
    VisualizationPayload,
    VisualNode,
)


EDGE_COLORS: dict[str, str] = {
    ConnectionType.SUPPORTS.value: "#2d936c",
    ConnectionType.OPPOSES.value: "#d1495b",
    ConnectionType.RELATES.value: "#6c757d",
    ConnectionType.LEADS_TO.value: "#f4a259",
    ConnectionType.DERIVES_FROM.value: "#3f88c5",
}


def build_vis_payload(nodes: list[Node], connections: list[Connection]) -> VisualizationPayload:
    """Convert domain objects to frontend-friendly datasets."""
    node_payload: list[VisualNode] = []
    for index, node in enumerate(nodes, start=1):
        node_label = node.summary or node.content[:24]
        title_parts = [f"#{index}", node.content]
        node_payload.append(
            VisualNode(
                id=node.id,
                label=f"{index}. {node_label}",
                title="\n".join(part for part in title_parts if part),
                x=node.position.x,
                y=node.position.y,
                color=node.color,
                value=max(node.size, 0.2),
                confidence=node.confidence,
            )
        )

    edge_payload = [
        VisualEdge(
            id=conn.id,
            source=conn.source_id,
            target=conn.target_id,
            label=conn.conn_type,
            title=conn.description,
            color=EDGE_COLORS.get(conn.conn_type, "#6c757d"),
            width=max(conn.strength, 0.2) * 2,
        )
        for conn in connections
    ]

    return VisualizationPayload(nodes=node_payload, edges=edge_payload)
