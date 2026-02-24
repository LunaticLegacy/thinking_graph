"""LLM runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
import os


API_BACKENDS = {"remote_api", "local_api"}
RUNTIME_BACKENDS = {"onnxruntime", "openvino"}


@dataclass(slots=True)
class LLMAPIProfile:
    api_key: str | None
    base_url: str
    model: str


@dataclass(slots=True)
class LLMLocalRuntimeProfile:
    model: str
    model_dir: str
    npu_device: str
    require_npu: bool
    onnx_provider: str | None


@dataclass(slots=True)
class LLMConfig:
    backend: str
    remote_api: LLMAPIProfile
    local_api: LLMAPIProfile
    local_runtime: LLMLocalRuntimeProfile

    # Active backend flattened view (for compatibility)
    api_key: str | None
    base_url: str
    model: str
    model_dir: str
    npu_device: str
    require_npu: bool
    onnx_provider: str | None

    @classmethod
    def from_sources(
        cls,
        data: Mapping[str, object] | None = None,
        project_root: Path | None = None,
    ) -> "LLMConfig":
        root = project_root or Path(__file__).resolve().parent.parent
        section = data or {}

        backend_default_raw = _to_str(section.get("backend"), "remote_api")
        backend = _normalize_backend(os.getenv("LLM_BACKEND", backend_default_raw))

        remote_section = _to_mapping(section.get("remote_api"))
        local_section = _to_mapping(section.get("local_api"))
        runtime_section = _to_mapping(section.get("local_runtime"))

        remote_api = _build_api_profile(
            section=remote_section,
            env_prefix="REMOTE",
            default_base_url="https://api.openai.com/v1",
            default_model="gpt-4o-mini",
        )

        local_api = _build_api_profile(
            section=local_section,
            env_prefix="LOCAL",
            default_base_url="http://127.0.0.1:11434/v1",
            default_model="qwen2.5:7b",
        )

        runtime_model_default = _to_str(
            runtime_section.get("model"),
            "qwen2.5-7b-instruct",
        )
        runtime_model_dir_default = _resolve_path(
            _to_str(runtime_section.get("model_dir"), str(root / "models")),
            root,
        )
        runtime_npu_device_default = _to_str(runtime_section.get("npu_device"), "NPU")
        runtime_require_npu_default = _to_bool(runtime_section.get("require_npu"), True)
        runtime_onnx_provider_default = _to_optional_str(runtime_section.get("onnx_provider"))

        runtime_model = os.getenv("LLM_LOCAL_RUNTIME_MODEL", runtime_model_default)
        runtime_model_dir = _resolve_path(
            os.getenv("LLM_LOCAL_RUNTIME_MODEL_DIR", runtime_model_dir_default),
            root,
        )
        runtime_npu_device = os.getenv(
            "LLM_LOCAL_RUNTIME_NPU_DEVICE",
            runtime_npu_device_default,
        ).strip() or "NPU"
        runtime_require_npu = _read_env_bool(
            "LLM_LOCAL_RUNTIME_REQUIRE_NPU",
            runtime_require_npu_default,
        )
        runtime_onnx_provider = _read_optional_text(
            "LLM_LOCAL_RUNTIME_ONNX_PROVIDER",
            runtime_onnx_provider_default,
        )

        local_runtime = LLMLocalRuntimeProfile(
            model=runtime_model.strip() or runtime_model_default,
            model_dir=runtime_model_dir,
            npu_device=runtime_npu_device,
            require_npu=runtime_require_npu,
            onnx_provider=runtime_onnx_provider,
        )

        selected_api = local_api if backend == "local_api" else remote_api
        selected_model = (
            local_runtime.model if backend in RUNTIME_BACKENDS else selected_api.model
        )

        return cls(
            backend=backend,
            remote_api=remote_api,
            local_api=local_api,
            local_runtime=local_runtime,
            api_key=selected_api.api_key,
            base_url=selected_api.base_url,
            model=selected_model,
            model_dir=local_runtime.model_dir,
            npu_device=local_runtime.npu_device,
            require_npu=local_runtime.require_npu,
            onnx_provider=local_runtime.onnx_provider,
        )

    @classmethod
    def from_env(cls, project_root: Path | None = None) -> "LLMConfig":
        return cls.from_sources(data=None, project_root=project_root)


def _build_api_profile(
    section: Mapping[str, object],
    env_prefix: str,
    default_base_url: str,
    default_model: str,
) -> LLMAPIProfile:
    api_key_default = _to_optional_str(section.get("api_key"))
    base_url_default = _to_str(section.get("base_url"), default_base_url)
    model_default = _to_str(section.get("model"), default_model)

    return LLMAPIProfile(
        api_key=_read_optional_text(f"LLM_{env_prefix}_API_KEY", api_key_default),
        base_url=os.getenv(f"LLM_{env_prefix}_BASE_URL", base_url_default),
        model=os.getenv(f"LLM_{env_prefix}_MODEL", model_default).strip() or model_default,
    )


def _normalize_backend(raw: str) -> str:
    text = raw.strip().lower()
    if text in API_BACKENDS or text in RUNTIME_BACKENDS:
        return text
    if text in {"", "openai", "api", "deepseek", "remote"}:
        return "remote_api"
    if text in {"local", "ollama", "lmstudio", "vllm", "local-openai"}:
        return "local_api"
    return text


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


def _read_optional_text(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default

    text = value.strip()
    return text if text else None


def _to_str(value: object, default: str) -> str:
    if isinstance(value, str):
        text = value.strip()
        if text:
            return text
    return default


def _to_optional_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text if text else None
    text = str(value).strip()
    return text if text else None


def _to_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return default


def _to_mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    return {}


def _resolve_path(value: str, root: Path) -> str:
    raw = Path(value)
    resolved = raw if raw.is_absolute() else (root / raw)
    return str(resolved)
