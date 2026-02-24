"""OpenVINO backend wrapper with explicit NPU device support."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

try:
    from openvino import Core
except Exception:  # pragma: no cover - optional dependency
    try:
        from openvino.runtime import Core  # type: ignore
    except Exception:  # pragma: no cover - optional dependency
        Core = None  # type: ignore[assignment]

try:
    import openvino_genai as ov_genai
except Exception:  # pragma: no cover - optional dependency
    ov_genai = None  # type: ignore[assignment]


def _compose_prompt(system_prompt: str | None, prompt: str) -> str:
    user_prompt = prompt.strip()
    if not user_prompt:
        raise ValueError("`prompt` is required.")
    if system_prompt and system_prompt.strip():
        return f"[SYSTEM]\n{system_prompt.strip()}\n\n[USER]\n{user_prompt}\n\n[ASSISTANT]\n"
    return user_prompt


def _to_text(output: Any) -> str:
    if isinstance(output, str):
        return output.strip()
    if isinstance(output, Sequence) and output and isinstance(output[0], str):
        return str(output[0]).strip()
    if hasattr(output, "text"):
        return str(getattr(output, "text")).strip()
    if hasattr(output, "texts"):
        texts = getattr(output, "texts")
        if isinstance(texts, Sequence) and texts:
            return str(texts[0]).strip()
    return str(output).strip()


class OpenVINONPUBackend:
    """Use OpenVINO GenAI to run local LLM generation on NPU."""

    backend = "openvino"

    def __init__(
        self,
        model_path: str | Path,
        model_name: str,
        device: str = "NPU",
        require_npu: bool = True,
    ) -> None:
        if Core is None:
            raise RuntimeError("OpenVINO is not installed. Please install `openvino` first.")
        if ov_genai is None:
            raise RuntimeError(
                "openvino-genai is not installed. Please install `openvino-genai`."
            )

        self.model_name = model_name
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(f"OpenVINO model path does not exist: {self.model_path}")

        self.core = Core()
        self.available_devices = tuple(self.core.available_devices)
        self.device = self._select_device(device=device, require_npu=require_npu)

        self._pipeline: Any | None = None

    def _select_device(self, device: str, require_npu: bool) -> str:
        requested = (device or "NPU").strip().upper()
        available = self.available_devices

        if requested.startswith("AUTO"):
            if require_npu and "NPU" not in available:
                raise RuntimeError(
                    "NPU is required but unavailable for OpenVINO. Available devices: "
                    f"{', '.join(available)}"
                )
            return requested if ":" in requested else "AUTO:NPU,CPU"

        if requested in available:
            return requested

        if "NPU" in available:
            return "NPU"

        if require_npu:
            raise RuntimeError(
                "NPU is required but unavailable for OpenVINO. Available devices: "
                f"{', '.join(available)}"
            )

        if "CPU" in available:
            return "CPU"
        if available:
            return available[0]
        return requested

    def _ensure_pipeline(self) -> None:
        if self._pipeline is not None:
            return

        self._pipeline = ov_genai.LLMPipeline(str(self.model_path), self.device)

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_new_tokens: int = 800,
    ) -> str:
        self._ensure_pipeline()
        assert self._pipeline is not None

        final_prompt = _compose_prompt(system_prompt=system_prompt, prompt=prompt)
        output = self._pipeline.generate(
            final_prompt,
            max_new_tokens=max(int(max_new_tokens), 1),
            temperature=max(float(temperature), 0.0),
        )
        return _to_text(output)
