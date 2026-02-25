"""ONNXRuntime backend wrapper with explicit NPU provider support."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

try:
    import onnxruntime as ort
except Exception:  # pragma: no cover - optional dependency
    ort = None  # type: ignore[assignment]

try:
    import onnxruntime_genai as og
except ImportError:  # pragma: no cover - optional dependency
    og = None  # type: ignore[assignment]


ORT_NPU_PROVIDERS: tuple[str, ...] = (
    "CPUExecutionProvider",
    "QNNExecutionProvider",
    "VitisAIExecutionProvider",
    "ACLExecutionProvider",
    "NnapiExecutionProvider",
)


def _compose_prompt(system_prompt: str | None, prompt: str) -> str:
    user_prompt = prompt.strip()
    if not user_prompt:
        raise ValueError("`prompt` is required.")

    if system_prompt and system_prompt.strip():
        return (
            "<|system|>\n"
            f"{system_prompt.strip()}\n"
            "<|end|>\n"
            "<|user|>\n"
            f"{user_prompt}\n"
            "<|end|>\n"
            "<|assistant|>\n"
        )
    return user_prompt


def _to_text(output: Any) -> str:
    if isinstance(output, str):
        return output.strip()
    if isinstance(output, Sequence) and output and isinstance(output[0], str):
        return str(output[0]).strip()
    if hasattr(output, "text"):
        value = getattr(output, "text")
        return str(value).strip()
    if hasattr(output, "texts"):
        texts = getattr(output, "texts")
        if isinstance(texts, Sequence) and texts:
            return str(texts[0]).strip()
    return str(output).strip()


class OnnxRuntimeNPUBackend:
    """Use ONNXRuntime/ORT GenAI to run local LLM generation on NPU."""

    backend = "onnxruntime"

    def __init__(
        self,
        model_path: str | Path,
        model_name: str,
        device: str = "NPU",
        require_npu: bool = True,
        preferred_provider: str | None = None,
    ) -> None:
        if ort is None:
            raise RuntimeError("onnxruntime is not installed. Please install `onnxruntime` first.")
        if og is None:
            raise RuntimeError(
                "onnxruntime-genai is not installed. Please install `onnxruntime-genai`."
            )

        self.model_name = model_name
        self.model_path = Path(model_path)
        self.device = (device or "NPU").strip().upper()
        self.require_npu = require_npu
        self.available_providers = tuple(ort.get_available_providers())
        self.provider = self._select_provider(preferred_provider)

        if not self.model_path.exists():
            raise FileNotFoundError(f"ONNX model path does not exist: {self.model_path}")

        self._model: Any | None = None
        self._tokenizer: Any | None = None

    def _select_provider(self, preferred_provider: str | None) -> str:
        available = self.available_providers
        if not available:
            raise RuntimeError("No ONNXRuntime execution providers found.")

        if preferred_provider and preferred_provider in available:
            return preferred_provider

        npu_candidates = [
            provider
            for provider in available
            if provider in ORT_NPU_PROVIDERS or "NPU" in provider.upper()
        ]
        if npu_candidates:
            return npu_candidates[0]

        if self.require_npu:
            raise RuntimeError(
                "NPU provider not found for ONNXRuntime. Available providers: "
                f"{', '.join(available)}"
            )

        if "CPUExecutionProvider" in available:
            return "CPUExecutionProvider"
        return available[0]

    def _ensure_model(self) -> None:
        if self._model is not None and self._tokenizer is not None:
            return

        model_obj: Any
        if hasattr(og, "Config"):
            config = og.Config(str(self.model_path))
            if hasattr(config, "clear_providers"):
                config.clear_providers()
            if hasattr(config, "append_provider"):
                config.append_provider(self.provider)
            model_obj = og.Model(config)
        else:
            model_obj = og.Model(str(self.model_path))

        self._model = model_obj
        self._tokenizer = og.Tokenizer(model_obj)

    def generate(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_new_tokens: int = 800,
    ) -> str:
        self._ensure_model()
        assert self._model is not None
        assert self._tokenizer is not None

        final_prompt = _compose_prompt(system_prompt=system_prompt, prompt=prompt)
        if hasattr(self._model, "generate"):
            output = self._model.generate(
                final_prompt,
                max_new_tokens=max(int(max_new_tokens), 1),
                temperature=max(float(temperature), 0.0),
            )
            return _to_text(output)

        params = og.GeneratorParams(self._model)
        if hasattr(params, "set_search_options"):
            params.set_search_options(
                max_length=max(int(max_new_tokens), 1),
                temperature=max(float(temperature), 0.0),
                do_sample=float(temperature) > 0.0,
            )

        input_ids = self._tokenizer.encode(final_prompt)
        if hasattr(params, "set_model_input"):
            params.set_model_input("input_ids", input_ids)
        else:
            params.input_ids = input_ids

        generator = og.Generator(self._model, params)
        output_tokens: list[int] = []
        while not generator.is_done():
            generator.compute_logits()
            generator.generate_next_token()
            new_tokens = generator.get_next_tokens()
            if isinstance(new_tokens, Sequence):
                output_tokens.extend(int(token) for token in new_tokens)
            else:
                output_tokens.append(int(new_tokens))

        return _to_text(self._tokenizer.decode(output_tokens))
