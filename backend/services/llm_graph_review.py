"""LLM graph review pipeline - structural validation and semantic review."""

from __future__ import annotations

import json
import re
from typing import Any

from backend.services.llm_backends import LLMBackend
from backend.services.llm_prompt_builders import (
    build_review_graph_prompt,
    build_review_graph_system_prompt,
)
from datamodels.llm_schemas import (
    LLMGraphIssue,
    LLMGraphReviewAggregate,
    LLMGraphReviewDraft,
    LLMGraphWarning,
)
from datamodels.graph_models import ConnectionType, GraphSnapshot


class GraphReviewPipeline:
    """Pipeline for reviewing thinking graphs."""
    
    def __init__(self, backend: LLMBackend):
        self.backend = backend
    
    def review(
        self,
        snapshot: GraphSnapshot,
        language: str = "zh",
    ) -> LLMGraphReviewAggregate:
        """Review a thinking graph using multi-layer approach.
        
        Layer 1: Structural validator (rule-based)
        Layer 2: Semantic reviewer (LLM-based)
        Layer 3: Aggregator (merge results)
        """
        # Layer 1: Rule-based structural validation
        rule_issues, rule_warnings = self._structural_validate(snapshot, language)
        
        # Layer 2: LLM-based semantic review (if backend available)
        llm_draft = LLMGraphReviewDraft()
        if self.backend.enabled:
            try:
                llm_draft = self._semantic_review(snapshot, language)
            except Exception:
                # If LLM review fails, continue with rule-based only
                pass
        
        # Layer 3: Aggregate results
        aggregate = self._aggregate_reviews(
            rule_issues=rule_issues,
            rule_warnings=rule_warnings,
            llm_draft=llm_draft,
            language=language,
        )
        
        return aggregate
    
    def _structural_validate(
        self,
        snapshot: GraphSnapshot,
        language: str,
    ) -> tuple[list[LLMGraphIssue], list[LLMGraphWarning]]:
        """Layer 1: Pure code-based structural validation."""
        issues: list[LLMGraphIssue] = []
        warnings: list[LLMGraphWarning] = []
        
        node_ids = {node.id for node in snapshot.nodes}
        connection_types = ConnectionType.values()
        
        # Check nodes
        for node in snapshot.nodes:
            # Empty content
            if not node.content.strip():
                reason = (
                    "Node content is empty."
                    if language == "en"
                    else "节点 content 为空。"
                )
                issues.append(LLMGraphIssue(
                    entity_type="node",
                    entity_id=node.id,
                    reason=reason,
                    severity="error",
                    source="rule",
                ))
            
            # Warning: High confidence but no evidence
            if node.confidence > 0.8 and not node.evidence:
                warning_text = (
                    f"High confidence ({node.confidence}) without evidence."
                    if language == "en"
                    else f"高置信度 ({node.confidence}) 但缺少证据。"
                )
                warnings.append(LLMGraphWarning(
                    entity_type="node",
                    entity_id=node.id,
                    reason=warning_text,
                    suggestion="Consider adding evidence to support this claim.",
                    source="rule",
                ))
        
        # Check connections
        pair_types: dict[tuple[str, str], set[str]] = {}
        pair_connections: dict[tuple[str, str], list[str]] = {}
        
        for conn in snapshot.connections:
            # Self-loop
            if conn.source_id == conn.target_id:
                reason = (
                    "Connection is a self-loop (source_id == target_id)."
                    if language == "en"
                    else "连接存在自环 (source_id == target_id)。"
                )
                issues.append(LLMGraphIssue(
                    entity_type="connection",
                    entity_id=conn.id,
                    reason=reason,
                    severity="error",
                    source="rule",
                ))
            
            # Invalid node reference
            if conn.source_id not in node_ids or conn.target_id not in node_ids:
                reason = (
                    "Connection references a non-existing node id."
                    if language == "en"
                    else "连接引用了不存在的节点 id。"
                )
                issues.append(LLMGraphIssue(
                    entity_type="connection",
                    entity_id=conn.id,
                    reason=reason,
                    severity="error",
                    source="rule",
                ))
            
            # Invalid connection type
            if conn.conn_type not in connection_types:
                reason = (
                    f"Invalid connection type: {conn.conn_type}"
                    if language == "en"
                    else f"连接类型无效: {conn.conn_type}"
                )
                issues.append(LLMGraphIssue(
                    entity_type="connection",
                    entity_id=conn.id,
                    reason=reason,
                    severity="error",
                    source="rule",
                ))
            
            # Warning: Empty description with high strength
            if not conn.description.strip() and conn.strength > 2.0:
                warning_text = (
                    f"Empty description with high strength ({conn.strength})."
                    if language == "en"
                    else f"描述为空但强度很高 ({conn.strength})。"
                )
                warnings.append(LLMGraphWarning(
                    entity_type="connection",
                    entity_id=conn.id,
                    reason=warning_text,
                    suggestion="Add a description to clarify this strong relationship.",
                    source="rule",
                ))
            
            # Track pairs for contradiction detection
            pair_key = (conn.source_id, conn.target_id)
            pair_types.setdefault(pair_key, set()).add(conn.conn_type)
            pair_connections.setdefault(pair_key, []).append(conn.id)
        
        # Check for contradictory relationships
        for pair_key, kinds in pair_types.items():
            if (
                ConnectionType.SUPPORTS.value in kinds
                and ConnectionType.OPPOSES.value in kinds
            ):
                source_id, target_id = pair_key
                reason_template = (
                    "Both supports and opposes exist for the same directed pair: {source} -> {target}"
                    if language == "en"
                    else "同一方向节点同时存在 supports 与 opposes 关系: {source} -> {target}"
                )
                reason = reason_template.format(source=source_id, target=target_id)
                
                for conn_id in pair_connections.get(pair_key, []):
                    issues.append(LLMGraphIssue(
                        entity_type="connection",
                        entity_id=conn_id,
                        reason=reason,
                        severity="error",
                        source="rule",
                    ))
        
        return issues, warnings
    
    def _semantic_review(
        self,
        snapshot: GraphSnapshot,
        language: str,
    ) -> LLMGraphReviewDraft:
        """Layer 2: LLM-based semantic review."""
        prompt = build_review_graph_prompt(snapshot, language)
        system_prompt = build_review_graph_system_prompt(language)
        
        raw_response = self.backend.chat_text(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.0,
            max_tokens=900,
        )
        
        return self._parse_review_response(raw_response, language)
    
    def _parse_review_response(
        self,
        raw_response: str,
        language: str,
    ) -> LLMGraphReviewDraft:
        """Parse structured review response from LLM."""
        payload = self._extract_json_payload(raw_response)
        
        if payload is None:
            # Fallback to heuristic parsing
            return self._heuristic_review_parse(raw_response, language)
        
        result = str(payload.get("result", "")).strip().upper()
        if result not in {"OK", "CONFLICT", "WARNING"}:
            result = "OK"
        
        conflicts: list[LLMGraphIssue] = []
        warnings: list[LLMGraphWarning] = []
        
        default_reason = (
            "No reason provided."
            if language == "en"
            else "未提供原因。"
        )
        
        # Parse conflicts
        conflicts_raw = payload.get("conflicts")
        if isinstance(conflicts_raw, list):
            for item in conflicts_raw:
                if isinstance(item, dict):
                    entity_type = str(item.get("entity_type", "global")).strip() or "global"
                    entity_id = str(item.get("entity_id", "global")).strip() or "global"
                    reason = str(item.get("reason", default_reason)).strip() or default_reason
                    
                    conflicts.append(LLMGraphIssue(
                        entity_type=entity_type,
                        entity_id=entity_id,
                        reason=reason,
                        severity="error",
                        source="llm",
                    ))
                elif isinstance(item, str):
                    text = item.strip()
                    if text:
                        conflicts.append(LLMGraphIssue(
                            entity_type="global",
                            entity_id="global",
                            reason=text,
                            severity="error",
                            source="llm",
                        ))
        
        # Parse warnings (new field)
        warnings_raw = payload.get("warnings")
        if isinstance(warnings_raw, list):
            for item in warnings_raw:
                if isinstance(item, dict):
                    entity_type = str(item.get("entity_type", "global")).strip() or "global"
                    entity_id = str(item.get("entity_id", "global")).strip() or "global"
                    reason = str(item.get("reason", "")).strip()
                    suggestion = str(item.get("suggestion", "")).strip()
                    
                    if reason:
                        warnings.append(LLMGraphWarning(
                            entity_type=entity_type,
                            entity_id=entity_id,
                            reason=reason,
                            suggestion=suggestion,
                            source="llm",
                        ))
        
        overview = str(payload.get("overview", "")).strip()
        
        return LLMGraphReviewDraft(
            result=result,
            conflicts=conflicts,
            warnings=warnings,
            overview=overview,
        )
    
    def _heuristic_review_parse(
        self,
        raw_response: str,
        language: str,
    ) -> LLMGraphReviewDraft:
        """Fallback heuristic parsing when JSON extraction fails."""
        text = (raw_response or "").strip()
        if not text:
            return LLMGraphReviewDraft(result="OK")
        
        lowered = text.lower()
        
        # Check for OK
        if lowered == "ok" or "no conflict" in lowered or "无冲突" in text:
            return LLMGraphReviewDraft(result="OK", overview=text[:200])
        
        # Check for conflict indicators
        has_conflict = (
            "conflict" in lowered or
            "冲突" in text or
            "矛盾" in text or
            "invalid" in lowered or
            "无效" in text
        )
        
        if has_conflict:
            return LLMGraphReviewDraft(
                result="CONFLICT",
                conflicts=[LLMGraphIssue(
                    entity_type="global",
                    entity_id="global",
                    reason=text[:500],
                    severity="error",
                    source="llm",
                )],
                overview=text[:200],
            )
        
        # Default to warning for ambiguous cases
        return LLMGraphReviewDraft(
            result="WARNING",
            warnings=[LLMGraphWarning(
                entity_type="global",
                entity_id="global",
                reason=text[:500],
                source="llm",
            )],
            overview=text[:200],
        )
    
    def _aggregate_reviews(
        self,
        rule_issues: list[LLMGraphIssue],
        rule_warnings: list[LLMGraphWarning],
        llm_draft: LLMGraphReviewDraft,
        language: str,
    ) -> LLMGraphReviewAggregate:
        """Layer 3: Merge rule-based and LLM-based results."""
        all_conflicts: list[LLMGraphIssue] = []
        all_warnings: list[LLMGraphWarning] = []
        
        # Add rule-based issues
        all_conflicts.extend(rule_issues)
        all_warnings.extend(rule_warnings)
        
        # Add LLM-based issues (deduplicate)
        seen_conflicts: set[tuple[str, str, str]] = set()
        for issue in all_conflicts:
            key = (issue.entity_type, issue.entity_id, issue.reason)
            seen_conflicts.add(key)
        
        for llm_issue in llm_draft.conflicts:
            key = (llm_issue.entity_type, llm_issue.entity_id, llm_issue.reason)
            if key not in seen_conflicts:
                all_conflicts.append(llm_issue)
                seen_conflicts.add(key)
        
        # Add LLM-based warnings (deduplicate)
        seen_warnings: set[tuple[str, str, str]] = set()
        for warning in all_warnings:
            key = (warning.entity_type, warning.entity_id, warning.reason)
            seen_warnings.add(key)
        
        for llm_warning in llm_draft.warnings:
            key = (llm_warning.entity_type, llm_warning.entity_id, llm_warning.reason)
            if key not in seen_warnings:
                all_warnings.append(llm_warning)
                seen_warnings.add(key)
        
        # Determine verdict
        if all_conflicts:
            verdict = "CONFLICT"
        elif all_warnings:
            verdict = "WARNING"
        else:
            verdict = "OK"
        
        # Generate overview if missing
        overview = llm_draft.overview
        if not overview:
            overview = self._generate_overview(verdict, all_conflicts, all_warnings, language)
        
        return LLMGraphReviewAggregate(
            verdict=verdict,
            conflicts=all_conflicts,
            warnings=all_warnings,
            overview=overview,
            conflict_count=len(all_conflicts),
            warning_count=len(all_warnings),
        )
    
    @staticmethod
    def _generate_overview(
        verdict: str,
        conflicts: list[LLMGraphIssue],
        warnings: list[LLMGraphWarning],
        language: str,
    ) -> str:
        """Generate overview text from review results."""
        if verdict == "OK":
            return "OK" if language == "en" else "审核通过，未发现明显问题。"
        
        parts: list[str] = []
        
        if conflicts:
            conflict_text = (
                f"Found {len(conflicts)} conflict(s)."
                if language == "en"
                else f"发现 {len(conflicts)} 个冲突。"
            )
            parts.append(conflict_text)
        
        if warnings:
            warning_text = (
                f"Found {len(warnings)} warning(s)."
                if language == "en"
                else f"发现 {len(warnings)} 个警告。"
            )
            parts.append(warning_text)
        
        return " ".join(parts) if parts else verdict
    
    @staticmethod
    def _extract_json_payload(raw_response: str) -> dict[str, Any] | None:
        """Extract JSON from LLM response."""
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
