from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.api.routers.agents.directories import (
    TEMPLATE_PROMPT_USAGE_SNIPPET_MAP,
    _resolve_tool_description,
)
from app.db.models.directory import Directory
from app.schemas.directory import DirectoryCreate, STANDARD_QA_DIRECTORY_COLUMNS
from app.services.directory.demo_seed import demo_rows_for_template
from app.services.directory.persist_create import (
    DemoItemValidationFailed,
    persist_directory_with_demo_items,
)


def test_directory_create_seed_demo_items_defaults_true() -> None:
    m = DirectoryCreate.model_validate({"name": "faq", "template": "qa"})
    assert m.seed_demo_items is True


def test_directory_create_seed_demo_items_false() -> None:
    m = DirectoryCreate.model_validate(
        {"name": "faq", "template": "qa", "seed_demo_items": False}
    )
    assert m.seed_demo_items is False


def test_resolve_tool_description_empty_uses_preset() -> None:
    text = _resolve_tool_description(None, template="qa")
    assert "get_question_answer" in text
    assert "query" in text.lower()


def test_resolve_tool_description_client_value_preserved() -> None:
    assert _resolve_tool_description("  custom desc  ", template="qa") == "custom desc"


def test_resolve_tool_description_custom_empty_uses_tool_name() -> None:
    text = _resolve_tool_description(None, template="custom", tool_name="get_price_list")
    assert "get_price_list" in text
    assert "query" in text.lower()


def test_prompt_usage_snippet_presets_call_pattern() -> None:
    s = TEMPLATE_PROMPT_USAGE_SNIPPET_MAP["company_info"]
    assert s.startswith("Вызывай ")
    assert "get_company_info" in s
    assert "клиник" in s.lower() or "компан" in s.lower()


def test_demo_rows_three_per_template() -> None:
    assert len(demo_rows_for_template("product_catalog")) == 3


def test_custom_seed_demo_requires_standard_qa_columns() -> None:
    with pytest.raises(ValidationError):
        DirectoryCreate.model_validate(
            {
                "name": "x",
                "template": "custom",
                "columns": [
                    {
                        "name": "foo",
                        "label": "F",
                        "type": "text",
                        "required": True,
                        "searchable": True,
                    },
                ],
            }
        )


def test_custom_without_seed_allows_arbitrary_columns() -> None:
    DirectoryCreate.model_validate(
        {
            "name": "x",
            "template": "custom",
            "seed_demo_items": False,
            "columns": [
                {
                    "name": "foo",
                    "label": "F",
                    "type": "text",
                    "required": True,
                    "searchable": True,
                },
            ],
        }
    )


def test_catalog_templates_normalize_columns() -> None:
    m = DirectoryCreate.model_validate(
        {
            "name": "svc",
            "template": "service_catalog",
            "columns": [
                {
                    "name": "wrong",
                    "label": "W",
                    "type": "text",
                    "required": True,
                    "searchable": True,
                },
            ],
        }
    )
    names = [c.name for c in m.columns]
    assert names == ["question", "answer"]


async def _run_persist_commit_failure() -> None:
    session = MagicMock()
    session.add = MagicMock()
    session.rollback = AsyncMock()

    async def flush_side_effect() -> None:
        directory.id = uuid4()

    session.flush = AsyncMock(side_effect=flush_side_effect)
    session.commit = AsyncMock(side_effect=RuntimeError("commit failed"))

    directory = Directory(
        tenant_id=uuid4(),
        agent_id=uuid4(),
        name="d",
        slug="d",
        tool_name="get_question_answer",
        tool_description="x",
        template="qa",
        columns=list(STANDARD_QA_DIRECTORY_COLUMNS),
        response_mode="function_result",
        search_type="semantic",
    )

    with pytest.raises(RuntimeError, match="commit failed"):
        await persist_directory_with_demo_items(
            session,
            directory=directory,
            columns_data=list(STANDARD_QA_DIRECTORY_COLUMNS),
            demo_rows=demo_rows_for_template("qa"),
            tenant_id=uuid4(),
            validate_item_row=lambda d, cols, rn: [],
        )

    session.rollback.assert_awaited_once()


def test_persist_rollbacks_when_commit_fails() -> None:
    asyncio.run(_run_persist_commit_failure())


async def _run_persist_validation_failure() -> None:
    session = MagicMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    directory = Directory(
        tenant_id=uuid4(),
        agent_id=uuid4(),
        name="d",
        slug="d",
        tool_name="get_question_answer",
        tool_description="x",
        template="qa",
        columns=list(STANDARD_QA_DIRECTORY_COLUMNS),
        response_mode="function_result",
        search_type="semantic",
    )

    async def flush_side_effect() -> None:
        directory.id = uuid4()

    session.flush = AsyncMock(side_effect=flush_side_effect)

    def bad_validate(
        data: dict, cols: list, rn: int
    ) -> list[str]:  # noqa: ANN001
        if rn == 2:
            return ["broken"]
        return []

    with pytest.raises(DemoItemValidationFailed):
        await persist_directory_with_demo_items(
            session,
            directory=directory,
            columns_data=list(STANDARD_QA_DIRECTORY_COLUMNS),
            demo_rows=demo_rows_for_template("qa"),
            tenant_id=uuid4(),
            validate_item_row=bad_validate,
        )

    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()


def test_persist_rollbacks_when_demo_validation_fails_on_second_row() -> None:
    asyncio.run(_run_persist_validation_failure())
