"""LLM backend adapters - unified interface for different LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from config import LLMConfig


class LLMBackend(ABC):
    """Abstract base class for LLM backends."""
    
    @abstractmethod
    def chat_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        """Send a chat request and return text response."""
        pass
    
    @property
    @abstractmethod
    def enabled(self) -> bool:
        """Check if backend is properly initialized."""
        pass
    
    @property
    @abstractmethod
    def model_name(self) -> str:
        """Get the model name."""
        pass


class APIBackend(LLMBackend):
    """Backend for remote/local API-based LLM services (OpenAI-compatible)."""
    
    def __init__(
        self,
        config: LLMConfig,
        mode: str = "remote_api",
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        self.config = config
        self.mode = mode
        self._client: Any | None = None
        self._disabled_reason: str | None = None
        
        profile = config.local_api if mode == "local_api" else config.remote_api
        
        self.base_url = (base_url or profile.base_url).strip()
        self.model = (model or profile.model).strip() or profile.model
        self.api_key = api_key if api_key is not None else profile.api_key
        
        # Local API endpoints often don't require a real API key
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
    
    @property
    def enabled(self) -> bool:
        return self._client is not None
    
    @property
    def model_name(self) -> str:
        return self.model
    
    def chat_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        if not self.enabled:
            raise RuntimeError(f"API backend is disabled: {self._disabled_reason}")
        
        assert self._client is not None
        
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt.strip()})
        
        completion = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=float(temperature),
            max_tokens=max(int(max_tokens), 1),
        )
        return (completion.choices[0].message.content or "").strip()


class LocalRuntimeBackend(LLMBackend):
    """Backend for local runtime inference (ONNX/OpenVINO)."""
    
    def __init__(
        self,
        config: LLMConfig,
        backend: str = "onnxruntime",
        model: str | None = None,
    ):
        self.config = config
        self.backend = backend
        self._local_backend: Any | None = None
        self._disabled_reason: str | None = None
        
        runtime_profile = config.local_runtime
        self.model = (model or runtime_profile.model).strip() or runtime_profile.model
        
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
    
    @property
    def enabled(self) -> bool:
        return self._local_backend is not None
    
    @property
    def model_name(self) -> str:
        return self.model
    
    def chat_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        if not self.enabled:
            raise RuntimeError(f"Local runtime backend is disabled: {self._disabled_reason}")
        
        assert self._local_backend is not None
        
        return self._local_backend.generate(
            prompt,
            system_prompt=system_prompt,
            temperature=float(temperature),
            max_new_tokens=max(int(max_tokens), 1),
        )


def create_llm_backend(
    config: LLMConfig,
    backend_type: str,
    **kwargs: Any,
) -> LLMBackend:
    """Factory function to create appropriate LLM backend."""
    backend_type = backend_type.strip().lower()
    
    if backend_type in {"remote_api", "local_api"}:
        return APIBackend(config, mode=backend_type, **kwargs)
    elif backend_type in {"onnxruntime", "openvino"}:
        return LocalRuntimeBackend(config, backend=backend_type, **kwargs)
    else:
        raise ValueError(f"Unsupported backend type: {backend_type}")
