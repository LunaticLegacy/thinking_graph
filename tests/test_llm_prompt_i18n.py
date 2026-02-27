"""Tests for backend LLM prompt i18n resources."""

from __future__ import annotations

from backend.i18n import (
    get_llm_prompt_items,
    get_llm_prompt_text,
    normalize_prompt_language,
    render_llm_prompt_template,
)


def test_normalize_prompt_language_fallbacks_to_zh():
    assert normalize_prompt_language("en") == "en"
    assert normalize_prompt_language("zh") == "zh"
    assert normalize_prompt_language("EN") == "en"
    assert normalize_prompt_language("fr") == "zh"
    assert normalize_prompt_language(None) == "zh"


def test_get_llm_prompt_items_returns_paradigm_by_language():
    en_items = get_llm_prompt_items("en", "thinking_graph_paradigm")
    zh_items = get_llm_prompt_items("zh", "thinking_graph_paradigm")

    assert len(en_items) >= 3
    assert len(zh_items) >= 3
    assert en_items != zh_items


def test_render_generate_graph_prompt_template_uses_runtime_values():
    prompt = render_llm_prompt_template(
        "en",
        "generate_graph_prompt_template",
        topic="remote work productivity",
        max_nodes=12,
        connection_types="supports / opposes",
    )

    assert "remote work productivity" in prompt
    assert "12" in prompt
    assert "supports / opposes" in prompt


def test_get_llm_prompt_text_fallback_to_default_language():
    prompt = get_llm_prompt_text("fr", "review_system_prompt")
    assert "JSON" in prompt
