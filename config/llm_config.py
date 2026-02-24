"""LLM runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(slots=True)
class LLMConfig:
    api_key: str | None
    base_url: str
    model: str
    backend: str
    model_dir: str
    npu_device: str
    require_npu: bool
    onnx_provider: str | None

    @classmethod
    def from_env(cls) -> "LLMConfig":
        root = Path(__file__).resolve().parent.parent
        return cls(
            api_key=os.getenv("LLM_API_KEY"),
            base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            backend=os.getenv("LLM_BACKEND", "openai").strip().lower(),
            model_dir=os.getenv("LLM_MODEL_DIR", str(root / "models")),
            npu_device=os.getenv("LLM_NPU_DEVICE", "NPU").strip() or "NPU",
            require_npu=_read_env_bool("LLM_REQUIRE_NPU", default=True),
            onnx_provider=_read_optional_text("LLM_ONNX_PROVIDER"),
        )


def _read_env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _read_optional_text(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None

    text = value.strip()
    return text if text else None
