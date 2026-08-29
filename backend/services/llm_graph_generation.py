"""LLM graph generation pipeline - topic to structured graph."""

from __future__ import annotations

import json
import re
from typing import Any

from backend.services.llm_backends import LLMBackend
from backend.services.llm_prompt_builders import (
    build_generate_graph_prompt,
    build_generate_graph_system_prompt,
)
from datamodels.llm_schemas import (
    LLMGeneratedConnection,
    LLMGeneratedNode,
    LLMGraphDraft,
    LLMGraphGenerationResult,
    LLMOperationError,
    LLMOperationStatus,
)
from datamodels.graph_models import ConnectionType


class GraphGenerationPipeline:
    """Pipeline for generating thinking graphs from topics."""
    
    def __init__(self, backend: LLMBackend):
        self.backend = backend
    
    def generate(
        self,
        topic: str,
        max_nodes: int = 18,
        language: str = "zh",
        temperature: float = 0.2,
        max_tokens: int = 1400,
    ) -> LLMGraphGenerationResult:
        """Generate a thinking graph from a topic.
        
        This implements a multi-stage pipeline:
        1. Draft generation via LLM
        2. Local normalization and validation
        3. Optional internal critique (lightweight)
        """
        if not topic.strip():
            return LLMGraphGenerationResult(
                status=LLMOperationStatus(
                    success=False,
                    error_message="Topic is required."
                ),
                model=self.backend.model_name,
                message="Topic is required."
            )
        
        if not self.backend.enabled:
            return LLMGraphGenerationResult(
                status=LLMOperationStatus(
                    success=False,
                    error_message="LLM backend is unavailable."
                ),
                model=self.backend.model_name,
                message="LLM backend is unavailable. Check backend/runtime configuration."
            )
        
        normalized_max_nodes = min(max(int(max_nodes), 3), 40)
        
        # Stage 1: Generate draft
        try:
            draft = self._generate_draft(
                topic=topic.strip(),
                max_nodes=normalized_max_nodes,
                language=language,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            return LLMGraphGenerationResult(
                status=LLMOperationStatus(
                    success=False,
                    error_message=f"Generation failed: {exc}"
                ),
                model=self.backend.model_name,
                message=f"Generation failed: {exc}"
            )
        
        if not draft.nodes:
            return LLMGraphGenerationResult(
                status=LLMOperationStatus(success=False),
                draft=draft,
                model=self.backend.model_name,
                message="LLM did not return valid nodes."
            )
        
        # Stage 2: Normalize and validate
        normalized_draft = self._normalize_and_validate(draft, language=language)
        
        # Stage 3: Optional internal critique (lightweight, rule-based by default)
        critique_result = self._internal_critique(normalized_draft, language=language)
        
        if not critique_result.success:
            return LLMGraphGenerationResult(
                status=LLMOperationStatus(success=False),
                draft=normalized_draft,
                model=self.backend.model_name,
                message=critique_result.error_message or "Internal critique failed."
            )
        
        return LLMGraphGenerationResult(
            status=LLMOperationStatus(success=True),
            draft=normalized_draft,
            model=self.backend.model_name,
            message="Graph generated successfully."
        )
    
    def _generate_draft(
        self,
        topic: str,
        max_nodes: int,
        language: str,
        temperature: float,
        max_tokens: int,
    ) -> LLMGraphDraft:
        """Stage 1: Generate initial graph draft from LLM."""
        prompt = build_generate_graph_prompt(
            topic=topic,
            max_nodes=max_nodes,
            language=language,
        )
        system_prompt = build_generate_graph_system_prompt(language=language)
        
        raw_response = self.backend.chat_text(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        # Parse JSON payload
        payload = self._extract_json_payload(raw_response)
        if payload is None:
            return LLMGraphDraft()
        
        # Handle nested structure
        graph_payload = payload
        nested_payload = payload.get("graph")
        if isinstance(nested_payload, dict):
            graph_payload = nested_payload
        
        # Extract nodes and connections
        nodes = self._parse_generated_nodes(graph_payload.get("nodes", []), max_nodes)
        connections = self._parse_generated_connections(
            graph_payload.get("connections", []),
            node_ids={n.id for n in nodes},
            language=language,
        )
        
        # Extract summary
        summary = self._extract_summary(payload, graph_payload, nodes)
        
        return LLMGraphDraft(
            nodes=nodes,
            connections=connections,
            summary=summary,
        )
    
    def _normalize_and_validate(
        self,
        draft: LLMGraphDraft,
        language: str,
    ) -> LLMGraphDraft:
        """Stage 2: Normalize and validate the generated graph."""
        # Filter out empty content nodes
        valid_nodes = [n for n in draft.nodes if n.content.strip()]
        
        # Deduplicate by ID
        seen_ids: set[str] = set()
        unique_nodes: list[LLMGeneratedNode] = []
        for node in valid_nodes:
            if node.id not in seen_ids:
                seen_ids.add(node.id)
                unique_nodes.append(node)
        
        # Normalize node properties
        normalized_nodes = []
        for node in unique_nodes:
            normalized_node = LLMGeneratedNode(
                id=node.id,
                content=node.content.strip(),
                summary=node.summary.strip() if node.summary else "",
                confidence=self._clamp_float(node.confidence, 0.0, 1.0),
                color=self._normalize_hex_color(node.color),
                tags=[str(t) for t in node.tags],
                evidence=[str(e) for e in node.evidence],
            )
            normalized_nodes.append(normalized_node)
        
        node_ids = {n.id for n in normalized_nodes}
        
        # Normalize connections
        valid_connections = []
        for conn in draft.connections:
            # Skip invalid connections
            if not conn.source_id or not conn.target_id:
                continue
            if conn.source_id == conn.target_id:  # Self-loop
                continue
            if conn.source_id not in node_ids or conn.target_id not in node_ids:
                continue
            
            # Normalize connection type
            conn_type = conn.conn_type if conn.conn_type in ConnectionType.values() else "relates"
            
            # Normalize description
            description = self._normalize_connection_description(
                conn.description,
                conn_type,
                conn.source_id,
                conn.target_id,
                normalized_nodes,
                language,
            )
            
            normalized_conn = LLMGeneratedConnection(
                source_id=conn.source_id,
                target_id=conn.target_id,
                conn_type=conn_type,
                description=description,
                strength=self._clamp_float(conn.strength, 0.1, 3.0),
            )
            valid_connections.append(normalized_conn)
        
        # Ensure confidence variation
        self._ensure_confidence_variation(normalized_nodes)
        
        # Extract or generate summary
        summary = draft.summary if draft.summary else self._fallback_summary(normalized_nodes)
        
        return LLMGraphDraft(
            nodes=normalized_nodes,
            connections=valid_connections,
            summary=summary,
        )
    
    def _internal_critique(
        self,
        draft: LLMGraphDraft,
        language: str,
    ) -> LLMOperationStatus:
        """Stage 3: Lightweight internal critique (rule-based by default)."""
        issues: list[str] = []
        
        # Check for too few nodes
        if len(draft.nodes) < 2:
            issues.append("Graph has very few nodes (< 2)")
        
        # Check for isolated nodes (no connections)
        connected_nodes = set()
        for conn in draft.connections:
            connected_nodes.add(conn.source_id)
            connected_nodes.add(conn.target_id)
        
        isolated_count = sum(
            1 for node in draft.nodes 
            if node.id not in connected_nodes
        )
        if isolated_count > len(draft.nodes) * 0.5:
            issues.append(f"Too many isolated nodes ({isolated_count})")
        
        # Check summary consistency (basic check)
        if not draft.summary and len(draft.nodes) > 0:
            issues.append("Missing summary for graph with nodes")
        
        if issues:
            # For now, just log warnings but don't fail
            # In future, could trigger LLM-based critique here
            pass
        
        return LLMOperationStatus(success=True)
    
    # ==================== Helper Methods ====================
    
    @staticmethod
    def _extract_json_payload(raw_response: str) -> dict[str, Any] | None:
        """Extract JSON from LLM response with robust parsing."""
        text = (raw_response or "").strip()
        if not text:
            return None
        
        # Remove code fences
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text).strip()
        
        candidates = [text]
        start = text.find("{")
        end = text.rfind("}")
        if 0 <= start < end:
            candidates.append(text[start : end + 1])
        
        for candidate in candidates:
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
        
        return None
    
    def _parse_generated_nodes(
        self,
        raw_nodes: Any,
        max_nodes: int,
    ) -> list[LLMGeneratedNode]:
        """Parse and validate generated nodes."""
        if not isinstance(raw_nodes, list):
            return []
        
        nodes: list[LLMGeneratedNode] = []
        used_ids: set[str] = set()
        
        for index, item in enumerate(raw_nodes, start=1):
            if not isinstance(item, dict):
                continue
            
            content = str(item.get("content", "")).strip()
            if not content:
                continue
            
            # Handle duplicate IDs
            raw_id = str(item.get("id", "")).strip() or f"N{index}"
            node_id = raw_id
            suffix = 2
            while node_id in used_ids:
                node_id = f"{raw_id}_{suffix}"
                suffix += 1
            used_ids.add(node_id)
            
            node = LLMGeneratedNode(
                id=node_id,
                content=content,
                summary=str(item.get("summary", "")).strip(),
                confidence=self._to_float(item.get("confidence"), 1.0),
                color=str(item.get("color", "")).strip() or "#157f83",
                tags=[str(t) for t in item.get("tags", [])] if isinstance(item.get("tags"), list) else [],
                evidence=[str(e) for e in item.get("evidence", [])] if isinstance(item.get("evidence"), list) else [],
            )
            nodes.append(node)
            
            if len(nodes) >= max_nodes:
                break
        
        return nodes
    
    def _parse_generated_connections(
        self,
        raw_connections: Any,
        node_ids: set[str],
        language: str,
    ) -> list[LLMGeneratedConnection]:
        """Parse and validate generated connections."""
        if not isinstance(raw_connections, list):
            return []
        
        connections: list[LLMGeneratedConnection] = []
        
        for item in raw_connections:
            if not isinstance(item, dict):
                continue
            
            source_id = str(item.get("source_id", "")).strip()
            target_id = str(item.get("target_id", "")).strip()
            
            if not source_id or not target_id or source_id == target_id:
                continue
            if source_id not in node_ids or target_id not in node_ids:
                continue
            
            conn_type = str(item.get("conn_type", "relates")).strip()
            if conn_type not in ConnectionType.values():
                conn_type = "relates"
            
            conn = LLMGeneratedConnection(
                source_id=source_id,
                target_id=target_id,
                conn_type=conn_type,
                description=str(item.get("description", "")).strip(),
                strength=self._to_float(item.get("strength"), 1.0),
            )
            connections.append(conn)
        
        return connections
    
    @staticmethod
    def _extract_summary(
        payload: dict[str, Any],
        graph_payload: dict[str, Any],
        nodes: list[LLMGeneratedNode],
    ) -> str:
        """Extract summary from payload or generate fallback."""
        for source in (graph_payload, payload):
            for field in ("summary", "graph_summary", "overview", "abstract"):
                value = source.get(field)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        
        return GraphGenerationPipeline._fallback_summary(nodes)
    
    @staticmethod
    def _fallback_summary(nodes: list[LLMGeneratedNode]) -> str:
        """Generate fallback summary from nodes."""
        highlights: list[str] = []
        for node in nodes[:3]:
            text = node.summary or node.content
            if text:
                highlights.append(text[:96])
        
        if not highlights:
            return ""
        
        return "Core points: " + "; ".join(highlights)
    
    def _normalize_connection_description(
        self,
        raw_description: str,
        conn_type: str,
        source_id: str,
        target_id: str,
        nodes: list[LLMGeneratedNode],
        language: str,
    ) -> str:
        """Normalize connection description with fallback."""
        text = (raw_description or "").strip()
        invalid_tokens = {"", "none", "n/a", "na", "null", "unknown", "tbd"}
        
        if text and text.lower() not in invalid_tokens:
            return text
        
        # Generate fallback description
        return self._fallback_connection_description(
            conn_type=conn_type,
            source_id=source_id,
            target_id=target_id,
            nodes=nodes,
            language=language,
        )
    
    @staticmethod
    def _fallback_connection_description(
        conn_type: str,
        source_id: str,
        target_id: str,
        nodes: list[LLMGeneratedNode],
        language: str,
    ) -> str:
        """Generate fallback connection description."""
        node_map = {n.id: n for n in nodes}
        source_node = node_map.get(source_id)
        target_node = node_map.get(target_id)
        
        source_text = GraphGenerationPipeline._node_hint(source_node) or "source"
        target_text = GraphGenerationPipeline._node_hint(target_node) or "target"
        
        if language == "en":
            templates = {
                "supports": f"{source_text} supports {target_text}.",
                "opposes": f"{source_text} opposes {target_text}.",
                "relates": f"{source_text} is related to {target_text}.",
                "leads_to": f"{source_text} may lead to {target_text}.",
                "derives_from": f"{source_text} derives from {target_text}.",
            }
        else:
            templates = {
                "supports": f"{source_text} 支持 {target_text}。",
                "opposes": f"{source_text} 反驳 {target_text}。",
                "relates": f"{source_text} 与 {target_text} 相关。",
                "leads_to": f"{source_text} 可能导致 {target_text}。",
                "derives_from": f"{source_text} 源自 {target_text}。",
            }
        
        return templates.get(conn_type, templates["relates"])
    
    @staticmethod
    def _node_hint(node: LLMGeneratedNode | None, max_len: int = 28) -> str:
        """Get a short hint text for a node."""
        if not node:
            return ""
        text = node.summary or node.content
        if not text:
            return ""
        if len(text) <= max_len:
            return text
        return text[:max_len - 3].rstrip() + "..."
    
    @staticmethod
    def _ensure_confidence_variation(nodes: list[LLMGeneratedNode]) -> None:
        """Ensure nodes have varied confidence values."""
        if len(nodes) < 2:
            return
        
        rounded_values = {round(n.confidence, 3) for n in nodes}
        if len(rounded_values) >= 2:
            return
        
        # Create a small descending spread
        base = nodes[0].confidence
        span = min(0.4, 0.1 * max(len(nodes) - 1, 1))
        center = max(min(base, 1.0 - span / 2), span / 2)
        start = center + span / 2
        end = center - span / 2
        step = (start - end) / max(len(nodes) - 1, 1)
        
        for index, node in enumerate(nodes):
            value = max(min(start - index * step, 1.0), 0.0)
            node.confidence = round(value, 3)
    
    @staticmethod
    def _to_float(value: object, default: float) -> float:
        """Safely convert value to float."""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return default
        return default
    
    @staticmethod
    def _clamp_float(value: float, low: float, high: float) -> float:
        """Clamp float value to range."""
        return min(max(value, low), high)
    
    @staticmethod
    def _normalize_hex_color(value: str | None) -> str:
        """Normalize hex color string."""
        if value and re.fullmatch(r"#(?:[0-9a-fA-F]{6})", value):
            return value.lower()
        return "#157f83"
