"""LLM integration entry for backend APIs."""

from __future__ import annotations

import json
import re
from typing import Any

from config import LLMConfig
from datamodels.ai_llm_models import (
    LLMChatRequest,
    LLMChatResponse,
    LLMGraphConflict,
    LLMGraphReviewResponse,
)
from datamodels.graph_models import ConnectionType, GraphSnapshot


API_BACKENDS = {"remote_api", "local_api"}
RUNTIME_BACKENDS = {"onnxruntime", "openvino"}


class LLMService:
    THINKING_GRAPH_PARADIGM: tuple[str, ...] = (
        "节点(node)必须是明确观点，node.content 不能为空。",
        "连接(connection)必须连接两个不同节点，禁止自环(source_id == target_id)。",
        "连接类型必须属于: supports / opposes / relates / leads_to / derives_from。",
        "连接语义: supports=支持，opposes=反驳，relates=相关，leads_to=导向，derives_from=推导来源。",
        "连接的 source_id 与 target_id 必须都存在于节点集合中。",
        "同一方向的两个节点不应同时被 supports 与 opposes 关系并存。",
    )

    REVIEW_SYSTEM_PROMPT = (
        '你是思考图审计器。'
        '你只能输出 JSON，禁止输出 markdown、解释文字或多余字段。'
        '当思考图满足范式时输出 {"result":"OK"}。'
        '否则输出 {"result":"CONFLICT","conflicts":[{"entity_type":"node|connection|global","entity_id":"id-or-global","reason":"..."}]}。'
        '冲突项必须引用输入中的节点或连接 id。'
    )
    CHAT_GRAPH_SYSTEM_PROMPT = (
        "你会在每次对话中收到当前思考图（JSON）。"
        "回答时必须结合该思考图，不要忽略其中的节点和连接关系。"
        "当用户问题与图中信息冲突时，先指出冲突，再给出建议。"
    )
    GRAPH_GENERATE_SYSTEM_PROMPT = (
        "你是思考图生成器。"
        "你只能输出 JSON，禁止输出 markdown、解释文字或多余字段。"
        '输出格式必须是 {"nodes":[...],"connections":[...]}。'
        "每个节点必须有 id 与 content。"
        "每条连接必须有 source_id、target_id、conn_type。"
        "连接类型仅可使用: supports / opposes / relates / leads_to / derives_from。"
        "禁止自环；source_id 与 target_id 必须引用已存在节点。"
    )

    THINKING_GRAPH_PARADIGM_EN: tuple[str, ...] = (
        "Each node must contain a clear claim; node.content must not be empty.",
        "Each connection must link two different nodes; self-loop is forbidden (source_id != target_id).",
        "Each connection type must be one of: supports / opposes / relates / leads_to / derives_from.",
        "Connection semantics: supports=supports, opposes=opposes, relates=related, leads_to=leads to, derives_from=derives from.",
        "Both source_id and target_id of each connection must refer to existing node ids.",
        "For the same directed pair, supports and opposes must not coexist.",
    )

    REVIEW_SYSTEM_PROMPT_EN = (
        "You are a thinking-graph auditor. "
        "Output JSON only; no markdown or extra explanation. "
        'If valid, output {"result":"OK"}. '
        'If invalid, output {"result":"CONFLICT","conflicts":[{"entity_type":"node|connection|global","entity_id":"id-or-global","reason":"..."}]}. '
        "Each conflict must reference an id from input or use global."
    )

    CHAT_GRAPH_SYSTEM_PROMPT_EN = (
        "You will receive the current thinking graph (JSON) in each request. "
        "Your answer must use node and connection information from that graph. "
        "If user input conflicts with graph facts, explain the conflict first, then provide suggestions."
    )

    GRAPH_GENERATE_SYSTEM_PROMPT_EN = (
        "You are a thinking-graph generator. "
        "Output JSON only; no markdown or extra explanation. "
        'Output schema: {"nodes":[...],"connections":[...]}. '
        "Each node must include id and content. "
        "Each connection must include source_id, target_id, conn_type. "
        "conn_type must be one of: supports / opposes / relates / leads_to / derives_from. "
        "No self-loop; source_id and target_id must reference existing nodes."
    )

    def __init__(
        self,
        llm_config: LLMConfig | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        backend: str | None = None,
    ) -> None:
        config = llm_config or LLMConfig.from_env()

        self.config = config
        self.backend = (backend or config.backend).strip().lower()

        self.api_key: str | None = api_key
        self.base_url: str = base_url or ""
        self.model: str = model or ""

        self._client: Any | None = None
        self._local_backend: Any | None = None
        self._disabled_reason: str | None = None

        if self.backend in API_BACKENDS:
            self._init_api_backend(
                mode=self.backend,
                override_api_key=api_key,
                override_base_url=base_url,
                override_model=model,
            )
        elif self.backend in RUNTIME_BACKENDS:
            self._init_local_runtime_backend(override_model=model)
        else:
            self._disabled_reason = (
                "Unsupported backend. Use one of: "
                "remote_api, local_api, onnxruntime, openvino. "
                f"Current: {self.backend}"
            )

    @property
    def enabled(self) -> bool:
        if self.backend in API_BACKENDS:
            return self._client is not None
        if self.backend in RUNTIME_BACKENDS:
            return self._local_backend is not None
        return False

    @staticmethod
    def _normalize_language(language: str | None) -> str:
        candidate = (language or "zh").strip().lower()
        return "en" if candidate == "en" else "zh"

    def _review_system_prompt(self, language: str) -> str:
        normalized = self._normalize_language(language)
        if normalized == "en":
            return self.REVIEW_SYSTEM_PROMPT_EN
        return self.REVIEW_SYSTEM_PROMPT

    def _chat_graph_system_prompt(self, language: str) -> str:
        normalized = self._normalize_language(language)
        if normalized == "en":
            return self.CHAT_GRAPH_SYSTEM_PROMPT_EN
        return self.CHAT_GRAPH_SYSTEM_PROMPT

    def _graph_generate_system_prompt(self, language: str) -> str:
        normalized = self._normalize_language(language)
        if normalized == "en":
            return self.GRAPH_GENERATE_SYSTEM_PROMPT_EN
        return self.GRAPH_GENERATE_SYSTEM_PROMPT

    def _thinking_graph_paradigm(self, language: str) -> tuple[str, ...]:
        normalized = self._normalize_language(language)
        if normalized == "en":
            return self.THINKING_GRAPH_PARADIGM_EN
        return self.THINKING_GRAPH_PARADIGM

    def _init_api_backend(
        self,
        *,
        mode: str,
        override_api_key: str | None,
        override_base_url: str | None,
        override_model: str | None,
    ) -> None:
        profile = self.config.local_api if mode == "local_api" else self.config.remote_api

        self.base_url = (override_base_url or profile.base_url).strip()
        self.model = (override_model or profile.model).strip() or profile.model
        self.api_key = override_api_key if override_api_key is not None else profile.api_key

        # Local API endpoints often do not require a real API key.
        if mode == "local_api" and not self.api_key:
            self.api_key = "LOCAL_API_KEY"

        if mode == "remote_api" and not self.api_key:
            self._disabled_reason = (
                "Remote API backend is not configured. "
                "Set `LLM_REMOTE_API_KEY` (or configure [llm.remote_api].api_key)."
            )
            return

        try:
            from openai import OpenAI

            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        except Exception as exc:
            self._disabled_reason = f"Failed to initialize API client: {exc}"

    def _init_local_runtime_backend(self, *, override_model: str | None) -> None:
        runtime_profile = self.config.local_runtime

        self.model = (override_model or runtime_profile.model).strip() or runtime_profile.model
        self.base_url = ""
        self.api_key = None

        try:
            from utils.llm_npu_module import create_local_llm_backend

            self._local_backend = create_local_llm_backend(
                backend=self.backend,
                model_root=runtime_profile.model_dir,
                model_name=self.model,
                device=runtime_profile.npu_device,
                require_npu=runtime_profile.require_npu,
                onnx_provider=runtime_profile.onnx_provider,
            )
        except Exception as exc:
            self._disabled_reason = f"Failed to initialize {self.backend} backend: {exc}"

    def ask(
        self,
        payload: LLMChatRequest,
        graph_snapshot: GraphSnapshot | None = None,
    ) -> LLMChatResponse:
        text = payload.prompt.strip()
        if not text:
            raise ValueError("`prompt` is required.")

        request_payload = payload
        if graph_snapshot is not None:
            request_payload = self._attach_graph_context(payload, graph_snapshot)

        if not self.enabled:
            return LLMChatResponse(
                enabled=False,
                model=self.model or self.config.model,
                response=self._disabled_reason
                or "LLM backend is unavailable. Check backend/runtime configuration.",
            )

        try:
            if self.backend in API_BACKENDS:
                answer = self._ask_api(request_payload)
            else:
                answer = self._ask_local_runtime(request_payload)
        except Exception as exc:
            return LLMChatResponse(
                enabled=False,
                model=self.model or self.config.model,
                response=f"{self.backend} request failed: {exc}",
            )

        return LLMChatResponse(enabled=True, model=self.model, response=answer)

    def _attach_graph_context(
        self,
        payload: LLMChatRequest,
        snapshot: GraphSnapshot,
    ) -> LLMChatRequest:
        graph_json = self._graph_snapshot_json(snapshot)
        graph_block = (
            "[CURRENT_THINKING_GRAPH_JSON]\n"
            f"{graph_json}\n"
            "[END_CURRENT_THINKING_GRAPH_JSON]\n"
        )

        language = self._normalize_language(payload.language)
        merged_system_prompt = self._chat_graph_system_prompt(language)
        if payload.system_prompt:
            merged_system_prompt = (
                f"{payload.system_prompt.strip()}\n\n{self._chat_graph_system_prompt(language)}"
            )

        graph_instruction = (
            "Please answer based on the current thinking graph below:\n"
            if language == "en"
            else "请结合下面的当前思考图作答：\n"
        )
        merged_prompt = f"{payload.prompt.strip()}\n\n{graph_instruction}{graph_block}"

        return LLMChatRequest(
            prompt=merged_prompt,
            system_prompt=merged_system_prompt,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
            language=language,
        )

    @staticmethod
    def _graph_snapshot_json(snapshot: GraphSnapshot) -> str:
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

    def _ask_api(self, payload: LLMChatRequest) -> str:
        assert self._client is not None

        messages: list[dict[str, str]] = []
        if payload.system_prompt:
            messages.append({"role": "system", "content": payload.system_prompt})
        messages.append({"role": "user", "content": payload.prompt.strip()})

        completion = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=float(payload.temperature),
            max_tokens=max(int(payload.max_tokens), 1),
        )
        return (completion.choices[0].message.content or "").strip()

    def _ask_local_runtime(self, payload: LLMChatRequest) -> str:
        assert self._local_backend is not None

        return self._local_backend.generate(
            payload.prompt,
            system_prompt=payload.system_prompt,
            temperature=float(payload.temperature),
            max_new_tokens=max(int(payload.max_tokens), 1),
        )

    def generate_graph_from_topic(
        self,
        topic: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 1400,
        max_nodes: int = 18,
        language: str = "zh",
    ) -> dict[str, Any]:
        normalized_language = self._normalize_language(language)
        topic_text = topic.strip()
        if not topic_text:
            raise ValueError("`topic` is required.")

        normalized_max_nodes = min(max(int(max_nodes), 3), 40)

        if not self.enabled:
            return {
                "enabled": False,
                "model": self.model or self.config.model,
                "message": self._disabled_reason
                or "LLM backend is unavailable. Check backend/runtime configuration.",
                "nodes": [],
                "connections": [],
                "node_count": 0,
                "connection_count": 0,
            }

        prompt = self._build_generate_graph_prompt(
            topic_text,
            max_nodes=normalized_max_nodes,
            language=normalized_language,
        )
        chat_result = self.ask(
            LLMChatRequest(
                prompt=prompt,
                system_prompt=self._graph_generate_system_prompt(normalized_language),
                temperature=float(temperature),
                max_tokens=max(int(max_tokens), 1),
                language=normalized_language,
            )
        )
        raw_response = (chat_result.response or "").strip()

        if not chat_result.enabled:
            return {
                "enabled": False,
                "model": chat_result.model or self.model or self.config.model,
                "message": raw_response or "LLM graph generation failed.",
                "nodes": [],
                "connections": [],
                "node_count": 0,
                "connection_count": 0,
            }

        payload = self._extract_json_payload(raw_response)
        if payload is None:
            return {
                "enabled": True,
                "model": chat_result.model or self.model or self.config.model,
                "message": "LLM did not return valid JSON for graph generation.",
                "nodes": [],
                "connections": [],
                "node_count": 0,
                "connection_count": 0,
            }

        graph_payload = payload
        nested_payload = payload.get("graph")
        if isinstance(nested_payload, dict):
            graph_payload = nested_payload

        nodes, connections = self._normalize_generated_graph_payload(
            graph_payload,
            max_nodes=normalized_max_nodes,
        )

        if not nodes:
            return {
                "enabled": True,
                "model": chat_result.model or self.model or self.config.model,
                "message": "LLM did not return valid nodes.",
                "nodes": [],
                "connections": [],
                "node_count": 0,
                "connection_count": 0,
            }

        return {
            "enabled": True,
            "model": chat_result.model or self.model or self.config.model,
            "message": "graph generated",
            "nodes": nodes,
            "connections": connections,
            "node_count": len(nodes),
            "connection_count": len(connections),
        }

    def _build_generate_graph_prompt(self, topic: str, *, max_nodes: int, language: str = "zh") -> str:
        connection_types = " / ".join(sorted(ConnectionType.values()))
        normalized_language = self._normalize_language(language)
        if normalized_language == "en":
            return (
                "Generate a thinking graph for the topic below.\n"
                f"Topic: {topic}\n\n"
                "Requirements:\n"
                f"1. Node count between 3 and {max_nodes}.\n"
                "2. Nodes should be concise and debatable; content must not be empty.\n"
                f"3. conn_type can only be: {connection_types}.\n"
                "4. Connections are directed and self-loop is forbidden.\n"
                "5. source_id and target_id must reference defined nodes.\n"
                "6. Keep structure clear; sparse connections are acceptable when appropriate.\n"
                '7. Output JSON only: {"nodes":[...],"connections":[...]}\n'
            )

        return (
            "请围绕下列主题生成思考图。\n"
            f"主题: {topic}\n\n"
            "要求:\n"
            f"1. 节点数量 3 到 {max_nodes} 之间。\n"
            "2. 节点要简洁、可辩论，content 不能为空。\n"
            f"3. conn_type 只允许 {connection_types}。\n"
            "4. 连接必须是有向边，且禁止自环。\n"
            "5. source_id 和 target_id 必须引用已定义节点。\n"
            "6. 如有必要可生成较少连接，但需保证图结构清晰。\n"
            '7. 只输出 JSON 对象: {"nodes":[...],"connections":[...]}\n'
        )

    def _normalize_generated_graph_payload(
        self,
        payload: dict[str, Any],
        *,
        max_nodes: int,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        raw_nodes = payload.get("nodes")
        if not isinstance(raw_nodes, list):
            return [], []

        nodes: list[dict[str, Any]] = []
        used_node_ids: set[str] = set()

        for index, item in enumerate(raw_nodes, start=1):
            if not isinstance(item, dict):
                continue

            content = str(item.get("content", "")).strip()
            if not content:
                continue

            raw_id = str(item.get("id", "")).strip() or f"N{index}"
            node_id = raw_id
            suffix = 2
            while node_id in used_node_ids:
                node_id = f"{raw_id}_{suffix}"
                suffix += 1
            used_node_ids.add(node_id)

            summary = str(item.get("summary", "")).strip()
            confidence = self._clamp_float(
                self._to_float(item.get("confidence"), 1.0),
                0.0,
                1.0,
            )
            color = self._normalize_hex_color(
                str(item.get("color", "")).strip() or None
            )

            nodes.append(
                {
                    "id": node_id,
                    "content": content,
                    "summary": summary,
                    "confidence": confidence,
                    "color": color,
                }
            )
            if len(nodes) >= max_nodes:
                break

        if not nodes:
            return [], []

        node_ids = {node["id"] for node in nodes}
        raw_connections = payload.get("connections")
        connections: list[dict[str, Any]] = []

        if not isinstance(raw_connections, list):
            return nodes, connections

        for item in raw_connections:
            if not isinstance(item, dict):
                continue

            source_id = str(item.get("source_id", "")).strip()
            target_id = str(item.get("target_id", "")).strip()
            if (
                not source_id
                or not target_id
                or source_id == target_id
                or source_id not in node_ids
                or target_id not in node_ids
            ):
                continue

            conn_type = str(
                item.get("conn_type", ConnectionType.RELATES.value)
            ).strip()
            if conn_type not in ConnectionType.values():
                conn_type = ConnectionType.RELATES.value

            description = str(item.get("description", "")).strip()
            strength = self._clamp_float(
                self._to_float(item.get("strength"), 1.0),
                0.1,
                3.0,
            )

            connections.append(
                {
                    "source_id": source_id,
                    "target_id": target_id,
                    "conn_type": conn_type,
                    "description": description,
                    "strength": strength,
                }
            )

        return nodes, connections

    def review_graph(self, snapshot: GraphSnapshot, *, language: str = "zh") -> LLMGraphReviewResponse:
        normalized_language = self._normalize_language(language)
        rule_conflicts = self._rule_based_conflicts(snapshot, language=normalized_language)
        llm_conflicts: list[LLMGraphConflict] = []
        raw_response = ""

        if self.enabled:
            prompt = self._build_review_prompt(snapshot, language=normalized_language)
            chat_result = self.ask(
                LLMChatRequest(
                    prompt=prompt,
                    system_prompt=self._review_system_prompt(normalized_language),
                    temperature=0.0,
                    max_tokens=900,
                    language=normalized_language,
                )
            )
            raw_response = (chat_result.response or "").strip()
            llm_conflicts = self._parse_review_response(
                raw_response,
                language=normalized_language,
            )
        else:
            raw_response = self._disabled_reason or "LLM backend is unavailable."

        conflicts = self._merge_conflicts(
            rule_conflicts + llm_conflicts,
            language=normalized_language,
        )
        verdict = "OK" if not conflicts else "CONFLICT"

        response_text = "OK" if verdict == "OK" else (
            raw_response or self._conflicts_to_text(conflicts)
        )

        return LLMGraphReviewResponse(
            enabled=self.enabled,
            model=self.model or self.config.model,
            verdict=verdict,
            conflicts=conflicts,
            response=response_text,
            paradigm=list(self._thinking_graph_paradigm(normalized_language)),
        )

    def _build_review_prompt(self, snapshot: GraphSnapshot, *, language: str = "zh") -> str:
        normalized_language = self._normalize_language(language)
        paradigm_text = "\n".join(
            f"{index}. {item}"
            for index, item in enumerate(self._thinking_graph_paradigm(normalized_language), start=1)
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
        if normalized_language == "en":
            return (
                "Audit the thinking graph according to the paradigm below.\n"
                'If valid, return JSON: {"result":"OK"}.\n'
                'If invalid, return JSON: {"result":"CONFLICT","conflicts":[...]}.\n'
                "\n"
                f"Paradigm:\n{paradigm_text}\n\n"
                f"Thinking graph JSON:\n{graph_json}\n"
            )

        return (
            "请按下列范式审核思考图。\n"
            '若满足范式，返回 JSON: {"result":"OK"}\n'
            '若不满足，返回 JSON: {"result":"CONFLICT","conflicts":[...]}。\n'
            "\n"
            f"范式:\n{paradigm_text}\n\n"
            f"思考图JSON:\n{graph_json}\n"
        )

    def _rule_based_conflicts(
        self,
        snapshot: GraphSnapshot,
        *,
        language: str = "zh",
    ) -> list[LLMGraphConflict]:
        normalized_language = self._normalize_language(language)
        conflicts: list[LLMGraphConflict] = []
        node_ids = {node.id for node in snapshot.nodes}
        connection_types = ConnectionType.values()

        if normalized_language == "en":
            node_empty_reason = "Node content is empty."
            self_loop_reason = "Connection is a self-loop (source_id == target_id)."
            invalid_node_ref_reason = "Connection references a non-existing node id."
            invalid_conn_type_prefix = "Invalid connection type"
            contradictory_reason_template = (
                "Both supports and opposes exist for the same directed pair: {source} -> {target}"
            )
        else:
            node_empty_reason = "节点 content 为空。"
            self_loop_reason = "连接存在自环(source_id == target_id)。"
            invalid_node_ref_reason = "连接引用了不存在的节点。"
            invalid_conn_type_prefix = "连接类型无效"
            contradictory_reason_template = "同一方向节点同时存在 supports 与 opposes 关系: {source} -> {target}"

        for node in snapshot.nodes:
            if not node.content.strip():
                conflicts.append(
                    LLMGraphConflict(
                        entity_type="node",
                        entity_id=node.id,
                        reason=node_empty_reason,
                    )
                )

        pair_types: dict[tuple[str, str], set[str]] = {}
        pair_connections: dict[tuple[str, str], list[str]] = {}

        for conn in snapshot.connections:
            if conn.source_id == conn.target_id:
                conflicts.append(
                    LLMGraphConflict(
                        entity_type="connection",
                        entity_id=conn.id,
                        reason=self_loop_reason,
                    )
                )

            if conn.source_id not in node_ids or conn.target_id not in node_ids:
                conflicts.append(
                    LLMGraphConflict(
                        entity_type="connection",
                        entity_id=conn.id,
                        reason=invalid_node_ref_reason,
                    )
                )

            if conn.conn_type not in connection_types:
                conflicts.append(
                    LLMGraphConflict(
                        entity_type="connection",
                        entity_id=conn.id,
                        reason=f"{invalid_conn_type_prefix}: {conn.conn_type}",
                    )
                )

            pair_key = (conn.source_id, conn.target_id)
            pair_types.setdefault(pair_key, set()).add(conn.conn_type)
            pair_connections.setdefault(pair_key, []).append(conn.id)

        for pair_key, kinds in pair_types.items():
            if (
                ConnectionType.SUPPORTS.value in kinds
                and ConnectionType.OPPOSES.value in kinds
            ):
                source_id, target_id = pair_key
                for conn_id in pair_connections.get(pair_key, []):
                    conflicts.append(
                        LLMGraphConflict(
                            entity_type="connection",
                            entity_id=conn_id,
                            reason=contradictory_reason_template.format(
                                source=source_id,
                                target=target_id,
                            ),
                        )
                    )

        return self._merge_conflicts(conflicts, language=normalized_language)

    def _parse_review_response(
        self,
        raw_response: str,
        *,
        language: str = "zh",
    ) -> list[LLMGraphConflict]:
        normalized_language = self._normalize_language(language)
        payload = self._extract_json_payload(raw_response)
        if payload is None:
            return self._heuristic_conflicts(raw_response)

        result = str(payload.get("result", "")).strip().upper()
        if result == "OK":
            return []

        conflicts_raw = payload.get("conflicts")
        conflicts: list[LLMGraphConflict] = []
        default_reason = "No reason provided." if normalized_language == "en" else "未提供原因。"

        if isinstance(conflicts_raw, list):
            for item in conflicts_raw:
                if isinstance(item, dict):
                    entity_type = str(item.get("entity_type", "global")).strip() or "global"
                    entity_id = str(item.get("entity_id", "global")).strip() or "global"
                    reason = str(item.get("reason", default_reason)).strip() or default_reason
                    conflicts.append(
                        LLMGraphConflict(
                            entity_type=entity_type,
                            entity_id=entity_id,
                            reason=reason,
                        )
                    )
                elif isinstance(item, str):
                    text = item.strip()
                    if text:
                        conflicts.append(
                            LLMGraphConflict(
                                entity_type="global",
                                entity_id="global",
                                reason=text,
                            )
                        )

        if not conflicts and result and result != "OK":
            fallback_reason = (
                "LLM marked CONFLICT but did not return a structured conflicts list."
                if normalized_language == "en"
                else "LLM \u6807\u8bb0\u4e86\u51b2\u7a81\uff0c\u4f46\u672a\u8fd4\u56de\u7ed3\u6784\u5316 conflicts \u5217\u8868\u3002"
            )
            conflicts.append(
                LLMGraphConflict(
                    entity_type="global",
                    entity_id="global",
                    reason=fallback_reason,
                )
            )
        return self._merge_conflicts(conflicts, language=normalized_language)

    @staticmethod
    def _extract_json_payload(raw_response: str) -> dict[str, Any] | None:
        text = (raw_response or "").strip()
        if not text:
            return None

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

    @staticmethod
    def _heuristic_conflicts(raw_response: str) -> list[LLMGraphConflict]:
        text = (raw_response or "").strip()
        if not text:
            return []

        lowered = text.lower()
        if lowered == "ok":
            return []

        if "conflict" in lowered or "冲突" in text or "无效" in text:
            return [
                LLMGraphConflict(
                    entity_type="global",
                    entity_id="global",
                    reason=text,
                )
            ]

        return []

    @staticmethod
    def _merge_conflicts(
        conflicts: list[LLMGraphConflict],
        *,
        language: str = "zh",
    ) -> list[LLMGraphConflict]:
        normalized_language = "en" if (language or "").strip().lower() == "en" else "zh"
        default_reason = "No reason provided." if normalized_language == "en" else "未提供原因。"

        merged: list[LLMGraphConflict] = []
        seen: set[tuple[str, str, str]] = set()

        for conflict in conflicts:
            key = (
                conflict.entity_type.strip() or "global",
                conflict.entity_id.strip() or "global",
                conflict.reason.strip(),
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(
                LLMGraphConflict(
                    entity_type=key[0],
                    entity_id=key[1],
                    reason=key[2] or default_reason,
                )
            )

        return merged

    @staticmethod
    def _conflicts_to_text(conflicts: list[LLMGraphConflict]) -> str:
        if not conflicts:
            return "OK"

        rows = [
            f"[{item.entity_type}] {item.entity_id}: {item.reason}"
            for item in conflicts
        ]
        return "\n".join(rows)

    @staticmethod
    def _to_float(value: object, default: float) -> float:
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
        return min(max(value, low), high)

    @staticmethod
    def _normalize_hex_color(value: str | None) -> str:
        if value and re.fullmatch(r"#(?:[0-9a-fA-F]{6})", value):
            return value.lower()
        return "#157f83"
