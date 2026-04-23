from __future__ import annotations

from app.services.run_service import _select_optional_runtime_tool_categories


def test_optional_runtime_tools_always_all_categories_for_llm() -> None:
    categories, meta = _select_optional_runtime_tool_categories("любой текст пользователя")

    assert categories == {"knowledge", "direct_questions", "expertise", "directory"}
    assert meta["selection"] == "all_optional_tools_exposed_to_llm"
    assert meta["matched_categories"] == sorted(categories)
