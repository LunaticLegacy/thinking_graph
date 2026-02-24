from dataclasses import dataclass
from typing import Mapping


@dataclass(slots=True)
class LLMContext:
    role: str
    content: str


@dataclass(slots=True)
class LLMChatRequest:
    prompt: str
    system_prompt: str | None = None
    temperature: float = 0.3
    max_tokens: int = 800

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "LLMChatRequest":
        prompt = payload.get("prompt")
        if not isinstance(prompt, str):
            prompt = "" if prompt is None else str(prompt)

        system_prompt_raw = payload.get("system_prompt")
        system_prompt = None
        if isinstance(system_prompt_raw, str):
            stripped = system_prompt_raw.strip()
            if stripped:
                system_prompt = stripped
        elif system_prompt_raw is not None:
            stripped = str(system_prompt_raw).strip()
            if stripped:
                system_prompt = stripped

        temperature = payload.get("temperature", 0.3)
        if isinstance(temperature, str):
            try:
                temperature = float(temperature)
            except ValueError:
                temperature = 0.3
        elif not isinstance(temperature, (int, float)):
            temperature = 0.3

        max_tokens = payload.get("max_tokens", 800)
        if isinstance(max_tokens, str):
            try:
                max_tokens = int(max_tokens)
            except ValueError:
                max_tokens = 800
        elif isinstance(max_tokens, float):
            max_tokens = int(max_tokens)
        elif not isinstance(max_tokens, int):
            max_tokens = 800

        return cls(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=float(temperature),
            max_tokens=int(max_tokens),
        )


@dataclass(slots=True)
class LLMChatResponse:
    enabled: bool
    model: str
    response: str


@dataclass(slots=True)
class LLMGraphConflict:
    entity_type: str
    entity_id: str
    reason: str


@dataclass(slots=True)
class LLMGraphReviewResponse:
    enabled: bool
    model: str
    verdict: str
    conflicts: list[LLMGraphConflict]
    response: str
    paradigm: list[str]
