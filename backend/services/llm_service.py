"""LLM integration entry for backend APIs - refactored as facade/orchestrator."""

from __future__ import annotations

from typing import Any

from backend.services.llm_backends import LLMBackend, create_llm_backend
from backend.services.llm_graph_generation import GraphGenerationPipeline
from backend.services.llm_graph_review import GraphReviewPipeline
from backend.services.llm_prompt_builders import build_chat_with_graph_prompt
from backend.services.llm_schemas import (
    LLMGraphIssue,
    LLMGraphReviewAggregate,
)
from config import LLMConfig
from datamodels.ai_llm_models import (
    LLMChatRequest,
    LLMChatResponse,
    LLMGraphConflict,
    LLMGraphReviewResponse,
)
from datamodels.graph_models import GraphSnapshot


API_BACKENDS = {"remote_api", "local_api"}
RUNTIME_BACKENDS = {"onnxruntime", "openvino"}


class LLMService:
    """Facade/Orchestrator for LLM operations.
    
    This class delegates to specialized modules:
    - llm_backends.py: Backend adapter management
    - llm_graph_generation.py: Graph generation pipeline
    - llm_graph_review.py: Graph review pipeline
    - llm_prompt_builders.py: Prompt construction
    """

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
        
        # Determine backend type
        backend_type = (backend or config.backend).strip().lower()
        
        # Create appropriate backend
        try:
            self._backend: LLMBackend = create_llm_backend(
                config=config,
                backend_type=backend_type,
                api_key=api_key,
                base_url=base_url,
                model=model,
            )
        except Exception as exc:
            # Create a disabled backend with error message
            from backend.services.llm_backends import LLMBackend
            
            class DisabledBackend(LLMBackend):
                @property
                def enabled(self) -> bool:
                    return False
                
                @property
                def model_name(self) -> str:
                    return model or config.model
                
                def chat_text(self, *args, **kwargs) -> str:
                    raise RuntimeError(f"Backend disabled: {exc}")
            
            self._backend = DisabledBackend()
        
        # Initialize pipelines
        self._generation_pipeline = GraphGenerationPipeline(self._backend)
        self._review_pipeline = GraphReviewPipeline(self._backend)
        
        self._disabled_reason: str | None = None
        if not self._backend.enabled:
            self._disabled_reason = f"LLM backend '{backend_type}' is not available."

    @property
    def enabled(self) -> bool:
        return self._backend.enabled
    
    @property
    def model(self) -> str:
        return self._backend.model_name
    
    @property
    def backend(self) -> str:
        return type(self._backend).__name__

    def ask(
        self,
        payload: LLMChatRequest,
        graph_snapshot: GraphSnapshot | None = None,
    ) -> LLMChatResponse:
        """Handle chat requests, optionally with graph context."""
        text = payload.prompt.strip()
        if not text:
            raise ValueError("`prompt` is required.")
        
        # Attach graph context if provided
        request_payload = payload
        if graph_snapshot is not None:
            final_prompt, system_prompt = build_chat_with_graph_prompt(
                prompt=payload.prompt,
                graph_snapshot=graph_snapshot,
                language=payload.language,
                system_prompt=payload.system_prompt,
            )
            request_payload = LLMChatRequest(
                prompt=final_prompt,
                system_prompt=system_prompt,
                temperature=payload.temperature,
                max_tokens=payload.max_tokens,
                language=payload.language,
            )
        
        if not self.enabled:
            return LLMChatResponse(
                enabled=False,
                model=self.model,
                response=self._disabled_reason or "LLM backend is unavailable.",
            )
        
        try:
            answer = self._backend.chat_text(
                prompt=request_payload.prompt,
                system_prompt=request_payload.system_prompt,
                temperature=float(request_payload.temperature),
                max_tokens=max(int(request_payload.max_tokens), 1),
            )
        except Exception as exc:
            return LLMChatResponse(
                enabled=False,
                model=self.model,
                response=f"LLM request failed: {exc}",
            )
        
        return LLMChatResponse(enabled=True, model=self.model, response=answer)

    def generate_graph_from_topic(
        self,
        topic: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 1400,
        max_nodes: int = 18,
        language: str = "zh",
    ) -> dict[str, Any]:
        """Generate a thinking graph from a topic using the new pipeline."""
        result = self._generation_pipeline.generate(
            topic=topic,
            max_nodes=max_nodes,
            language=language,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        
        if not result.enabled or not result.draft:
            return {
                "enabled": result.enabled,
                "model": result.model,
                "message": result.message or "Graph generation failed.",
                "nodes": [],
                "connections": [],
                "summary": "",
                "node_count": 0,
                "connection_count": 0,
            }
        
        # Convert structured draft to legacy dict format for API compatibility
        nodes = [
            {
                "id": node.id,
                "content": node.content,
                "summary": node.summary,
                "confidence": node.confidence,
                "color": node.color,
                "tags": node.tags,
                "evidence": node.evidence,
            }
            for node in result.draft.nodes
        ]
        
        connections = [
            {
                "source_id": conn.source_id,
                "target_id": conn.target_id,
                "conn_type": conn.conn_type,
                "description": conn.description,
                "strength": conn.strength,
            }
            for conn in result.draft.connections
        ]
        
        return {
            "enabled": True,
            "model": result.model,
            "message": result.message,
            "nodes": nodes,
            "connections": connections,
            "summary": result.draft.summary,
            "node_count": len(nodes),
            "connection_count": len(connections),
        }

    def review_graph(self, snapshot: GraphSnapshot, *, language: str = "zh") -> LLMGraphReviewResponse:
        """Review a thinking graph using the new multi-layer pipeline."""
        aggregate = self._review_pipeline.review(snapshot, language)
        
        # Convert new schema to legacy response format for API compatibility
        conflicts = [
            LLMGraphConflict(
                entity_type=issue.entity_type,
                entity_id=issue.entity_id,
                reason=issue.reason,
            )
            for issue in aggregate.conflicts
        ]
        
        # Generate response text
        if aggregate.verdict == "OK":
            response_text = "OK"
        else:
            response_text = aggregate.overview or self._conflicts_to_text(conflicts)
        
        # Get paradigm items
        from backend.i18n import get_llm_prompt_items, normalize_prompt_language
        normalized_language = normalize_prompt_language(language)
        paradigm = list(get_llm_prompt_items(normalized_language, "thinking_graph_paradigm"))
        
        return LLMGraphReviewResponse(
            enabled=self.enabled,
            model=self.model,
            verdict=aggregate.verdict,
            conflicts=conflicts,
            response=response_text,
            paradigm=paradigm,
        )
    
    @staticmethod
    def _conflicts_to_text(conflicts: list[LLMGraphConflict]) -> str:
        """Convert conflicts list to text representation."""
        if not conflicts:
            return "OK"
        
        rows = [
            f"[{item.entity_type}] {item.entity_id}: {item.reason}"
            for item in conflicts
        ]
        return "\n".join(rows)
