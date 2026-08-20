"""Тесты помощника-конструктора.

В наборе нет ни conftest.py, ни pytest-asyncio, поэтому фикстуры не используем,
а асинхронное гоняем через asyncio.run — как в тестах действий правил.

LLM не вызываем: PydanticAgent в сервисе импортирован на уровне модуля именно
ради этого — подменяем его классом-заглушкой.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

import app.api.routers.agents.assistant as assistant_router
import app.services.agent_assistant.service as service
from app.schemas.agent_assistant import (
    AssistantCatalogItem,
    AssistantChatRequest,
    AssistantSuggestion,
)
from app.schemas.auth import AuthContext
from app.services.agent_assistant.catalog import known_preset_ids, sanitize_actions
from app.services.agent_assistant.context import (
    _prompt_headings,
    analyze_prompt_blocks,
    render_snapshot,
)


def _item(value: str, label: str = "Подпись", description: str = "") -> AssistantCatalogItem:
    return AssistantCatalogItem(value=value, label=label, description=description)


def _user() -> AuthContext:
    return AuthContext(
        user_id=uuid4(),
        tenant_id=uuid4(),
        role="owner",
        scopes=["agents:read", "agents:write"],
    )


def _agent(tenant_id=None) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        tenant_id=tenant_id or uuid4(),
        name="Стилия",
        model="openai:gpt-4.1-mini",
        system_prompt="Ты консультант клиники",
        is_disabled=False,
        function_rules_enabled=True,
        runtime_bridges_mode="manual",
        sqns_enabled=True,
        microsoft_graphrag_enabled=False,
    )


class _DbStub:
    """Помощник в базу не пишет — стаб это фиксирует."""

    def __init__(self) -> None:
        self.commits = 0
        self.added: list[object] = []

    async def commit(self) -> None:
        self.commits += 1

    def add(self, obj: object) -> None:
        self.added.append(obj)


# --- каталог ---------------------------------------------------------------


def test_sanitize_actions_keeps_only_executable_types() -> None:
    allowed = sanitize_actions(
        [_item("send_message"), _item("table_write"), _item("crm_note"), _item("noop")]
    )

    assert [item.value for item in allowed] == ["send_message", "table_write", "noop"]


def test_sanitize_actions_drops_soon_stubs_and_duplicates() -> None:
    allowed = sanitize_actions(
        [_item("soon_bitrix24"), _item("soon_amocrm"), _item("set_tag"), _item("set_tag")]
    )

    assert [item.value for item in allowed] == ["set_tag"]


def test_known_preset_ids_skips_blank_values() -> None:
    assert known_preset_ids([_item("client_to_table"), _item("  ")]) == {"client_to_table"}


# --- снимок конфигурации ---------------------------------------------------


def _snapshot(**overrides) -> dict:
    base = {
        "agent": {
            "name": "Стилия",
            "model": "openai:gpt-4.1-mini",
            "prompt_chars": 1200,
            "prompt_headings": [],
            "is_disabled": False,
            "function_rules_enabled": True,
            "sqns_enabled": True,
            "graphrag_enabled": False,
        },
        "rules": [],
        "tables": [],
        "knowledge": {
            "files_count": 0,
            "file_titles": [],
            "direct_questions_count": 0,
            "directories": [],
            "script_flows_count": 0,
        },
        "channels": [],
    }
    base.update(overrides)
    return base


def test_render_snapshot_describes_rules_and_tables() -> None:
    text = render_snapshot(
        _snapshot(
            rules=[
                {
                    "name": "save_client",
                    "kind": "function",
                    "enabled": True,
                    "trigger_mode": "post_tool",
                    "condition_type": "always",
                    "reaction": "ai_self_reply",
                    "behavior": "continue",
                    "parameters": [{"name": "client_phone", "type": "string", "description": "", "required": True}],
                    "actions": ["table_write"],
                }
            ],
            tables=[
                {
                    "name": "Заявки",
                    "description": "",
                    "records_count": 12,
                    "used_by_agent": True,
                    "columns": [{"name": "phone", "label": "Телефон", "type": "text"}],
                }
            ],
            channels=["telegram"],
        )
    )

    assert "save_client (функция, включена)" in text
    assert "параметры: client_phone" in text
    assert "действия: table_write" in text
    assert "Заявки (12 строк, используется этим агентом); колонки: phone:text" in text
    assert "Каналы: telegram" in text


def test_render_snapshot_states_emptiness_explicitly() -> None:
    # Пустой список должен читаться как «ничего нет», иначе модель додумает,
    # что данные просто не приехали, и начнёт советовать вслепую.
    text = render_snapshot(_snapshot())

    assert "Ни одного правила." in text
    assert "Ни одной таблицы." in text
    assert "Каналы: ни одного" in text


def test_prompt_headings_collects_h1_h2_h3() -> None:
    # Живые промпты пишут `# РОЛЬ`, мета-агент обучения — `## Роль и цель`.
    # Собирать надо оба, иначе половина промптов покажется бесструктурной.
    headings = _prompt_headings("# РОЛЬ\nТы админ\n\n## Цель\nЗаписать\n### Детали\nтекст")

    assert headings == ["# РОЛЬ", "## Цель", "### Детали"]


def test_prompt_headings_ignores_hashes_inside_text() -> None:
    headings = _prompt_headings("Тариф #3 действует\n#безпробела\n# РОЛЬ")

    assert headings == ["# РОЛЬ"]


def test_prompt_headings_are_capped() -> None:
    from app.services.agent_assistant.context import MAX_HEADINGS

    text = "\n".join(f"# Раздел {i}" for i in range(MAX_HEADINGS + 10))

    assert len(_prompt_headings(text)) == MAX_HEADINGS


def test_analyze_prompt_blocks_recognises_real_headings() -> None:
    # Заголовки живого агента «Консультант». Модель раз за разом объявляла
    # эти блоки недостающими — поэтому разбор считает код, а не она.
    blocks = analyze_prompt_blocks(
        [
            "# ЛИЧНОСТЬ",
            "# ПРАВИЛА ПРИВЕТСТВИЯ",
            "# ЗОНА ОТВЕТСТВЕННОСТИ",
            "# ИСТОЧНИКИ ФАКТОВ",
            "# ЛОГИКА ДИАЛОГА",
            "# СТИЛЬ ОТВЕТОВ",
            "# ПРАВИЛА ИНСТРУМЕНТОВ",
            "# ПРИМЕРЫ",
        ]
    )

    assert blocks["detectable"] is True
    for present in (
        "Роль и личность",
        "Приветствие",
        "Зона ответственности и границы",
        "Источники фактов",
        "Логика и приоритеты",
        "Стиль и формат ответов",
        "Правила инструментов",
        "Примеры реплик",
    ):
        assert present in blocks["present"], present
    assert "Эскалация и фолбэк" in blocks["missing"]


def test_analyze_prompt_blocks_gives_up_without_headings() -> None:
    # Флагманский агент написан сплошной прозой осознанно. Объявить, что в нём
    # нет ни одного блока, было бы неправдой.
    blocks = analyze_prompt_blocks([])

    assert blocks == {"detectable": False, "present": [], "missing": []}


def test_render_snapshot_lists_headings_and_computed_gaps() -> None:
    snapshot = _snapshot()
    snapshot["agent"]["prompt_headings"] = ["# РОЛЬ", "# ЦЕЛЬ"]

    text = render_snapshot(snapshot)

    assert "## Разбор системного промпта" in text
    assert "- # РОЛЬ\n- # ЦЕЛЬ" in text
    assert "Блоки, которые видно в заголовках: Роль и личность, Цель" in text
    assert "Отдельного заголовка нет под блоки: " in text
    assert "Приветствие" in text.split("Отдельного заголовка нет под блоки: ")[1]


def test_render_snapshot_refuses_to_judge_prompt_without_headings() -> None:
    text = render_snapshot(_snapshot())

    assert "состав блоков по нему определить нельзя" in text
    assert "Не утверждай, что каких-то блоков не хватает." in text


# --- мета-агент ------------------------------------------------------------


class _FakeResult:
    def __init__(self, output: service.AssistantOutput) -> None:
        self.output = output

    def all_messages(self) -> list:
        return []


class _FakeAgent:
    """Заглушка PydanticAgent: запоминает промпт и возвращает готовый ответ."""

    last: "_FakeAgent | None" = None
    reply: service.AssistantOutput | None = None

    def __init__(self, model, output_type=None, system_prompt=None) -> None:
        self.model = model
        self.output_type = output_type
        self.system_prompt = system_prompt
        self.user_prompt: str | None = None
        _FakeAgent.last = self

    async def run(self, user_prompt: str):
        self.user_prompt = user_prompt
        return _FakeResult(_FakeAgent.reply or service.AssistantOutput(message="ок"))


def _run_assistant(monkeypatch, *, reply=None, **overrides):
    _FakeAgent.reply = reply
    monkeypatch.setattr(service, "PydanticAgent", _FakeAgent)
    kwargs = {
        "question": "Куда сохранять заявки?",
        "history": [],
        "snapshot_text": "# Текущая настройка агента",
        "actions": [_item("table_write", "Запись в таблицу")],
        "function_presets": [_item("client_to_table", "Записать клиента в таблицу")],
        "scenario_presets": [_item("night_reply", "Ночной автоответ")],
        "model_name": "openai:gpt-4.1-mini",
    }
    kwargs.update(overrides)
    return asyncio.run(service.run_assistant(**kwargs))


def test_run_assistant_puts_question_and_catalogs_into_prompt(monkeypatch) -> None:
    _run_assistant(monkeypatch)

    prompt = _FakeAgent.last.user_prompt
    assert "Куда сохранять заявки?" in prompt
    assert "`table_write`" in prompt
    assert "`client_to_table`" in prompt
    assert _FakeAgent.last.system_prompt == service.SYSTEM_PROMPT


def test_run_assistant_drops_unknown_preset_id(monkeypatch) -> None:
    reply = service.AssistantOutput(
        message="Нужна функция",
        suggestions=[
            AssistantSuggestion(kind="function", title="Создать функцию", preset_id="no_such_preset")
        ],
    )

    result = _run_assistant(monkeypatch, reply=reply)

    # Ссылка на несуществующую заготовку открыла бы пустой конструктор.
    assert result.output.suggestions[0].preset_id is None
    assert result.output.suggestions[0].title == "Создать функцию"


def test_run_assistant_keeps_known_preset_id(monkeypatch) -> None:
    reply = service.AssistantOutput(
        message="Есть заготовка",
        suggestions=[
            AssistantSuggestion(kind="function", title="Записать клиента", preset_id="client_to_table")
        ],
    )

    result = _run_assistant(monkeypatch, reply=reply)

    assert result.output.suggestions[0].preset_id == "client_to_table"


def test_run_assistant_clears_preset_for_non_constructor_kinds(monkeypatch) -> None:
    reply = service.AssistantOutput(
        message="Загляните в таблицы",
        suggestions=[
            AssistantSuggestion(kind="table", title="Создать таблицу", preset_id="client_to_table")
        ],
    )

    result = _run_assistant(monkeypatch, reply=reply)

    assert result.output.suggestions[0].preset_id is None


def test_run_assistant_caps_suggestions_and_followups(monkeypatch) -> None:
    reply = service.AssistantOutput(
        message="Много идей",
        suggestions=[
            AssistantSuggestion(kind="function", title=f"Идея {i}") for i in range(6)
        ],
        followups=["a", "b", "c", "d", "  "],
    )

    result = _run_assistant(monkeypatch, reply=reply)

    assert len(result.output.suggestions) == 3
    assert result.output.followups == ["a", "b", "c"]


def test_run_assistant_rejects_blank_model(monkeypatch) -> None:
    with pytest.raises(ValueError):
        _run_assistant(monkeypatch, model_name="   ")


def test_run_assistant_rejects_blank_question(monkeypatch) -> None:
    with pytest.raises(ValueError):
        _run_assistant(monkeypatch, question="  ")


# --- эндпоинт --------------------------------------------------------------


def _call_endpoint(db, user, payload):
    return asyncio.run(assistant_router.assistant_chat(uuid4(), payload, db=db, user=user))


def test_endpoint_requires_tenant_llm_key(monkeypatch) -> None:
    from fastapi import HTTPException

    user = _user()
    agent = _agent(tenant_id=user.tenant_id)

    async def _agent_ok(*_args, **_kwargs):
        return agent

    async def _no_key(*_args, **_kwargs):
        return None

    monkeypatch.setattr(assistant_router, "get_agent_or_404", _agent_ok)
    monkeypatch.setattr(assistant_router, "get_decrypted_api_key", _no_key)

    with pytest.raises(HTTPException) as exc:
        _call_endpoint(_DbStub(), user, AssistantChatRequest(message="Как собрать запись?"))

    assert exc.value.status_code == 422
    assert "OpenAI" in exc.value.detail


def test_endpoint_returns_answer_without_touching_the_database(monkeypatch) -> None:
    user = _user()
    agent = _agent(tenant_id=user.tenant_id)
    db = _DbStub()
    captured: dict = {}

    async def _agent_ok(*_args, **_kwargs):
        return agent

    async def _key(*_args, **_kwargs):
        return "sk-test"

    async def _snapshot_ok(*_args, **_kwargs):
        return _snapshot()

    async def _assistant(**kwargs):
        captured.update(kwargs)
        return service.AssistantRunResult(
            output=service.AssistantOutput(
                message="Заявки удобно складывать в таблицу",
                suggestions=[
                    AssistantSuggestion(
                        kind="function",
                        title="Записать клиента в таблицу",
                        rationale="Соберёт имя и телефон",
                        preset_id="client_to_table",
                    )
                ],
                followups=["Как потом найти клиента?"],
            ),
            token_usage_steps=[],
            model_name="openai:gpt-4.1-mini",
        )

    monkeypatch.setattr(assistant_router, "get_agent_or_404", _agent_ok)
    monkeypatch.setattr(assistant_router, "get_decrypted_api_key", _key)
    monkeypatch.setattr(assistant_router, "build_agent_snapshot", _snapshot_ok)
    monkeypatch.setattr(assistant_router, "run_assistant", _assistant)

    response = _call_endpoint(
        db,
        user,
        AssistantChatRequest(
            message="Куда сохранять заявки?",
            actions=[_item("table_write"), _item("soon_bitrix24")],
            function_presets=[_item("client_to_table")],
        ),
    )

    assert response.message.startswith("Заявки удобно")
    assert response.suggestions[0].preset_id == "client_to_table"
    assert response.model == "openai:gpt-4.1-mini"
    # Заглушки «Скоро» до модели не доходят.
    assert [item.value for item in captured["actions"]] == ["table_write"]
    # Ни записи, ни коммита: без токенов списывать нечего.
    assert db.commits == 0
    assert db.added == []
