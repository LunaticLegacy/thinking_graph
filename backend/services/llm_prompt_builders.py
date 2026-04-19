"""LLM prompt builders - centralized prompt construction logic."""

from __future__ import annotations

import json

from backend.i18n import (
    get_llm_prompt_items,
    get_llm_prompt_text,
    normalize_prompt_language,
    render_llm_prompt_template,
)
from datamodels.graph_models import ConnectionType, GraphSnapshot


def build_chat_with_graph_prompt(
    prompt: str,
    graph_snapshot: GraphSnapshot,
    language: str = "zh",
    system_prompt: str | None = None,
) -> tuple[str, str]:
    """Build prompt for chat with graph context.
    
    Returns:
        Tuple of (final_prompt, merged_system_prompt)
    """
    normalized_language = normalize_prompt_language(language)
    
    # Build graph JSON block
    graph_json = _graph_snapshot_to_json(graph_snapshot)
    graph_block = (
        "[CURRENT_THINKING_GRAPH_JSON]\n"
        f"{graph_json}\n"
        "[END_CURRENT_THINKING_GRAPH_JSON]\n"
    )
    
    # Build system prompt
    if system_prompt:
        merged_system_prompt = (
            f"{system_prompt.strip()}\n\n"
            f"{get_llm_prompt_text(normalized_language, 'chat_graph_system_prompt')}"
        )
    else:
        merged_system_prompt = get_llm_prompt_text(
            normalized_language, 
            "chat_graph_system_prompt"
        )
    
    # Build user prompt with graph instruction
    graph_instruction = get_llm_prompt_text(
        normalized_language, 
        "attach_graph_instruction"
    )
    final_prompt = f"{prompt.strip()}\n\n{graph_instruction}{graph_block}"
    
    return final_prompt, merged_system_prompt


def build_generate_graph_prompt(
    topic: str,
    max_nodes: int = 18,
    language: str = "zh",
) -> str:
    """Build prompt for generating a thinking graph from a topic."""
    normalized_language = normalize_prompt_language(language)
    connection_types = " / ".join(sorted(ConnectionType.values()))
    
    return render_llm_prompt_template(
        normalized_language,
        "generate_graph_prompt_template",
        topic=topic,
        max_nodes=max_nodes,
        connection_types=connection_types,
    )


def build_generate_graph_system_prompt(language: str = "zh") -> str:
    """Build system prompt for graph generation."""
    normalized_language = normalize_prompt_language(language)
    
    base_prompt = get_llm_prompt_text(
        normalized_language, 
        "graph_generate_system_prompt_base"
    )
    summary_rule = get_llm_prompt_text(
        normalized_language, 
        "graph_generate_system_summary_rule"
    )
    connection_rule = get_llm_prompt_text(
        normalized_language, 
        "graph_generate_system_connection_rule"
    )
    confidence_rule = get_llm_prompt_text(
        normalized_language, 
        "graph_generate_system_confidence_rule"
    )
    
    return (
        f"{base_prompt}\n"
        f"{summary_rule}\n"
        f"{connection_rule}\n"
        f"{confidence_rule}"
    )


def build_review_graph_prompt(
    snapshot: GraphSnapshot,
    language: str = "zh",
) -> str:
    """Build prompt for reviewing a thinking graph."""
    normalized_language = normalize_prompt_language(language)
    
    paradigm_text = "\n".join(
        f"{index}. {item}"
        for index, item in enumerate(
            get_llm_prompt_items(normalized_language, "thinking_graph_paradigm"), 
            start=1
        )
    )
    
    graph_payload = {
        "node_count": len(snapshot.nodes),
        "connection_count": len(snapshot.connections),
        "nodes": [
            {
                "id": node.id,
                "summary": node.summary,
                "content": node.content,
                "confidence": node.confidence,
                "tags": node.tags,
                "evidence": node.evidence,
            }
            for node in snapshot.nodes
        ],
        "connections": [
            {
                "id": conn.id,
                "source_id": conn.source_id,
                "target_id": conn.target_id,
                "conn_type": conn.conn_type,
                "description": conn.description,
                "strength": conn.strength,
            }
            for conn in snapshot.connections
        ],
    }
    
    graph_json = json.dumps(graph_payload, ensure_ascii=False)
    
    return render_llm_prompt_template(
        normalized_language,
        "review_prompt_template",
        paradigm_text=paradigm_text,
        graph_json=graph_json,
    )


def build_review_graph_system_prompt(language: str = "zh") -> str:
    """Build system prompt for graph review."""
    normalized_language = normalize_prompt_language(language)
    return get_llm_prompt_text(normalized_language, "review_system_prompt")


def _graph_snapshot_to_json(snapshot: GraphSnapshot) -> str:
    """Convert graph snapshot to JSON string for prompt injection."""
    payload = {
        "node_count": len(snapshot.nodes),
        "connection_count": len(snapshot.connections),
        "nodes": [
            {
                "id": node.id,
                "summary": node.summary,
                "content": node.content,
                "confidence": node.confidence,
                "tags": node.tags,
                "evidence": node.evidence,
            }
            for node in snapshot.nodes
        ],
        "connections": [
            {
                "id": conn.id,
                "source_id": conn.source_id,
                "target_id": conn.target_id,
                "conn_type": conn.conn_type,
                "description": conn.description,
                "strength": conn.strength,
            }
            for conn in snapshot.connections
        ],
    }
    return json.dumps(payload, ensure_ascii=False)
