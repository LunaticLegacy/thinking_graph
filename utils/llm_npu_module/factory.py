"""Factory for local NPU-capable LLM backends."""

from __future__ import annotations

from pathlib import Path

from utils.llm_npu_module.llm_npu_onnx import OnnxRuntimeNPUBackend
from utils.llm_npu_module.llm_npu_openvino import OpenVINONPUBackend


def resolve_model_path(model_root: str | Path, model_name: str) -> Path:
    root = Path(model_root)
    preferred = root / model_name

    if preferred.exists():
        return preferred
    if model_name:
        raise FileNotFoundError(
            f"Model directory not found: {preferred}. "
            "Set LLM_MODEL to an existing model folder name."
        )
    if root.exists():
        return root

    raise FileNotFoundError(
        f"Model directory not found. root={root}, model_name={model_name}"
    )


def create_local_llm_backend(
    *,
    backend: str,
    model_root: str | Path,
    model_name: str,
    device: str = "NPU",
    require_npu: bool = True,
    onnx_provider: str | None = None,
):
    backend_name = backend.strip().lower()
    model_path = resolve_model_path(model_root=model_root, model_name=model_name)

    if backend_name == "onnxruntime":
        return OnnxRuntimeNPUBackend(
            model_path=model_path,
            model_name=model_name,
            device=device,
            require_npu=require_npu,
            preferred_provider=onnx_provider,
        )

    if backend_name == "openvino":
        return OpenVINONPUBackend(
            model_path=model_path,
            model_name=model_name,
            device=device,
            require_npu=require_npu,
        )

    raise ValueError(f"Unsupported local backend: {backend}")
