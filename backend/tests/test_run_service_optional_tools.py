from __future__ import annotations

from app.services.run_service import _select_optional_runtime_tool_categories


def test_select_optional_tools_eager_keeps_all_categories() -> None:
    categories, meta = _select_optional_runtime_tool_categories(
        "привет",
        mode="eager",
    )

    assert categories == {"knowledge", "direct_questions", "expertise", "directory"}
    assert meta["mode"] == "eager"


def test_select_optional_tools_lazy_keywords_matches_relevant_categories() -> None:
    categories, meta = _select_optional_runtime_tool_categories(
        "У клиента возражение по цене, нужен скрипт ответа и готовый ответ из базы знаний",
        mode="lazy_keywords",
    )

    assert "expertise" in categories
    assert "direct_questions" in categories
    assert meta["mode"] == "lazy_keywords"


def test_select_optional_tools_lazy_keywords_falls_back_to_safe_baseline() -> None:
    categories, _meta = _select_optional_runtime_tool_categories(
        "привет как дела",
        mode="lazy_keywords",
    )

    assert categories == {"knowledge", "direct_questions"}
