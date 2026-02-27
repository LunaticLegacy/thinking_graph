"""LLM prompt i18n resource helpers."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DEFAULT_PROMPT_LANGUAGE = "zh"
SUPPORTED_PROMPT_LANGUAGES = {"zh", "en"}


def normalize_prompt_language(language: str | None) -> str:
    candidate = (language or DEFAULT_PROMPT_LANGUAGE).strip().lower()
    if candidate in SUPPORTED_PROMPT_LANGUAGES:
        return candidate
    return DEFAULT_PROMPT_LANGUAGE


@lru_cache(maxsize=1)
def _load_prompt_catalog() -> dict[str, dict[str, Any]]:
    prompt_file = Path(__file__).with_name("llm_prompts.json")
    with prompt_file.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise ValueError("Invalid LLM prompt catalog: top-level value must be an object.")

    catalog: dict[str, dict[str, Any]] = {}
    for language, value in payload.items():
        if isinstance(language, str) and isinstance(value, dict):
            catalog[language] = value
    return catalog


def _resolve_prompt_value(language: str | None, key: str) -> Any:
    catalog = _load_prompt_catalog()
    normalized_language = normalize_prompt_language(language)

    primary = catalog.get(normalized_language, {})
    if key in primary:
        return primary[key]

    fallback = catalog.get(DEFAULT_PROMPT_LANGUAGE, {})
    if key in fallback:
        return fallback[key]

    raise KeyError(f"Missing LLM prompt key: {key}")


def get_llm_prompt_text(language: str | None, key: str) -> str:
    value = _resolve_prompt_value(language, key)
    if isinstance(value, str):
        return value
    raise TypeError(f"Prompt key `{key}` is not a text value.")


def get_llm_prompt_items(language: str | None, key: str) -> tuple[str, ...]:
    value = _resolve_prompt_value(language, key)
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return tuple(value)
    raise TypeError(f"Prompt key `{key}` is not a string list.")


def render_llm_prompt_template(language: str | None, key: str, **params: object) -> str:
    template = get_llm_prompt_text(language, key)
    return template.format(**params)
