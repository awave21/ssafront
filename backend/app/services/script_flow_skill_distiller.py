"""Дистилляция навыка (skill_doc) из compiled_text потока-сценария.

Модель «навык = продолжение эксперта»: из скомпилированного сценария эксперта
извлекается связная структура навыка — контекст, обработки возражений с
дословными фразами и уровнями дословности, последовательность шагов, факты
(берутся из инструмента, не из головы), концовки и ПРОБЕЛЫ.

Ключевой принцип — строго EXTRACTIVE: сервис только извлекает то, что эксперт
уже написал. Он НИКОГДА не сочиняет реплики за эксперта. Если для ситуации нет
фраз эксперта — это пробел (`gaps`): фиксируем ситуацию и триггер, но
`phrases: []`. Это защита от «дрейфа голоса», ради которой навык и вводится.

Модель — reasoning (gpt-5.1 по умолчанию); задача офлайн (при публикации потока),
не в горячем пути рантайма.
"""

from __future__ import annotations

import json
import re
from typing import Any

import structlog

from app.core.config import get_settings
from app.services.runtime.model_resolver import resolve_openai_client

logger = structlog.get_logger(__name__)

PHRASE_LEVELS = ("пример", "дословно", "обязательно")

# Этапы диалога — «линия жизни» разговора (для потока диалога в UI).
DIALOG_STAGES = (
    "приветствие",      # контакт, первичное обращение
    "уточнение",        # квалификация потребности
    "презентация",      # рассказ о методе/виде услуги
    "цена",             # обсуждение стоимости
    "возражения",       # сомнения, «дорого», «подумаю»
    "запись",           # оформление визита
    "завершение",       # завершение/тёплый контакт без давления
    "другое",
)

# ── Строгая JSON-схема выхода (OpenAI strict) ──────────────────────────────────
_PHRASE_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "level": {"type": "string", "enum": list(PHRASE_LEVELS)},
    },
    "required": ["text", "level"],
    "additionalProperties": False,
}

_OBJECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "situation": {"type": "string"},
        "trigger_when": {"type": "string"},
        "stage": {"type": "string", "enum": list(DIALOG_STAGES)},
        "approach": {"type": "string"},
        "phrases": {"type": "array", "items": _PHRASE_SCHEMA},
        "forbidden": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["situation", "trigger_when", "stage", "approach", "phrases", "forbidden"],
    "additionalProperties": False,
}

_GAP_SCHEMA = {
    "type": "object",
    "properties": {
        "situation": {"type": "string"},
        "trigger_when": {"type": "string"},
    },
    "required": ["situation", "trigger_when"],
    "additionalProperties": False,
}

SKILL_DOC_SCHEMA = {
    "type": "object",
    "properties": {
        "context": {"type": "string"},
        "objections": {"type": "array", "items": _OBJECTION_SCHEMA},
        "sequence": {"type": "array", "items": {"type": "string"}},
        "facts_from_tool": {"type": "array", "items": {"type": "string"}},
        "endings": {"type": "array", "items": {"type": "string"}},
        "gaps": {"type": "array", "items": _GAP_SCHEMA},
    },
    "required": ["context", "objections", "sequence", "facts_from_tool", "endings", "gaps"],
    "additionalProperties": False,
}

_SYSTEM_PROMPT = (
    "Ты — методист, который превращает сценарий опытного администратора клиники в "
    "структурированный НАВЫК. Навык — это продолжение эксперта: он помогает вести "
    "пациента голосом эксперта, а не переопределяет поведение ассистента.\n\n"
    "ЖЁСТКОЕ ПРАВИЛО (нарушение недопустимо): работай СТРОГО ИЗВЛЕКАЮЩЕ. Ты только "
    "переносишь то, что эксперт уже написал в сценарии. Ты НИКОГДА не придумываешь "
    "реплики, фразы, цифры или обработки, которых нет в источнике.\n"
    "- Каждая фраза в phrases должна дословно присутствовать в исходном тексте "
    "(допустима лёгкая нормализация пробелов/переменных {{...}}).\n"
    "- Если для ситуации в источнике НЕТ готовых фраз эксперта — не сочиняй их. "
    "Внеси такую ситуацию в gaps c описанием ситуации и триггера, а в objections "
    "её не добавляй (или добавляй с phrases: []).\n"
    "- Факты, цены, названия услуг НЕ переноси как утверждения — они берутся "
    "ассистентом из инструментов. В facts_from_tool перечисли, ЧТО нужно спросить "
    "у инструмента (например: «цену активной услуги», «свободные слоты»), без "
    "конкретных чисел.\n\n"
    "Уровни дословности фразы (поле level):\n"
    "- «пример» — образец интонации, можно адаптировать;\n"
    "- «дословно» — сохранить формулировку максимально близко;\n"
    "- «обязательно» — критичная формулировка, использовать буквально.\n"
    "Если эксперт не пометил уровень явно — ставь «пример».\n\n"
    "Поле stage — этап диалога, к которому относится ситуация (для линии диалога): "
    "приветствие · уточнение · презентация · цена · возражения · запись · завершение · другое. "
    "Выбери наиболее подходящий по смыслу.\n\n"
    "Верни строго JSON по заданной схеме. Все тексты на русском."
)


async def distill_skill(
    compiled_text: str,
    service_name: str,
    *,
    openai_api_key: str,
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> dict[str, Any]:
    """Извлечь skill_doc из compiled_text сценария.

    Возвращает dict по схеме SKILL_DOC_SCHEMA. `service_external_ids` в выход
    НЕ пишется — связь навык↔услуга живёт в колонке script_flows и добавляется
    вызывающей стороной.
    """
    settings = get_settings()
    effective_model = (model or settings.skill_distiller_model or "openai:gpt-5.1")
    if effective_model.startswith("openai:"):
        effective_model = effective_model.split(":", 1)[1]
    effort = reasoning_effort or settings.skill_distiller_reasoning_effort or "low"

    source = (compiled_text or "").strip()
    if not source:
        raise ValueError("compiled_text is empty — nothing to distill")

    user_content = (
        f"УСЛУГА/НАВЫК: {service_name or '(без названия)'}\n\n"
        "ИСХОДНЫЙ СЦЕНАРИЙ ЭКСПЕРТА (единственный источник фраз):\n"
        "<scenario>\n"
        f"{source}\n"
        "</scenario>\n\n"
        "Извлеки навык по схеме. Помни: только то, что есть в сценарии; "
        "недостающие ситуации — в gaps."
    )

    client = resolve_openai_client(openai_api_key=openai_api_key)
    request_kwargs: dict[str, Any] = dict(
        model=effective_model,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "skill_doc",
                "schema": SKILL_DOC_SCHEMA,
                "strict": True,
            },
        },
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )
    # reasoning-модели (gpt-5.x) принимают reasoning_effort и не принимают temperature
    if effort and effort != "off":
        request_kwargs["reasoning_effort"] = effort

    response = await client.chat.completions.create(**request_kwargs)
    content_text = response.choices[0].message.content or "{}"
    parsed = json.loads(content_text)

    skill_doc = _sanitize_skill_doc(parsed)

    usage = getattr(response, "usage", None)
    logger.info(
        "skill_distilled",
        service_name=service_name,
        model=effective_model,
        reasoning_effort=effort,
        objections=len(skill_doc["objections"]),
        gaps=len(skill_doc["gaps"]),
        tokens_in=int(getattr(usage, "prompt_tokens", 0) or 0),
        tokens_out=int(getattr(usage, "completion_tokens", 0) or 0),
    )
    return skill_doc


_CHAT_SYSTEM_PROMPT = (
    "Ты — ассистент, который помогает опытному администратору клиники собрать НАВЫК "
    "(продолжение эксперта) по услуге. Эксперт в диалоге и через приложенные материалы "
    "(файлы/текст) передаёт свой практический опыт: в каких ситуациях что говорить, "
    "какими словами вести пациента, как обрабатывать возражения.\n\n"
    "Твоя роль — вести короткий продуктивный диалог и структурировать ТО, ЧТО ДАЛ ЭКСПЕРТ, "
    "в skill_doc.\n\n"
    "ЖЁСТКИЕ ПРАВИЛА (нарушение недопустимо):\n"
    "- Не выдумывай фразы, факты, цены или обработки, которых эксперт не давал (в чате или "
    "материалах). Ты — не автор навыка, а его редактор.\n"
    "- Фразы в phrases бери из слов эксперта/материалов (допустима лёгкая нормализация).\n"
    "- Если для важной ситуации эксперт ещё не дал фраз — не сочиняй: занеси её в gaps и "
    "задай КОРОТКИЙ уточняющий вопрос в reply.\n"
    "- Факты (цены, слоты, названия) не фиксируй как истину — в facts_from_tool перечисли, "
    "ЧТО спросить у инструмента, без конкретных чисел.\n"
    "- Уровни фраз: «пример» (можно адаптировать) / «дословно» (близко к тексту) / "
    "«обязательно» (буквально). Если эксперт не указал — ставь «пример».\n\n"
    "reply — что сказать эксперту: по-человечески, коротко (1–3 предложения), обычно это "
    "подтверждение что записал + один уточняющий вопрос, что дать дальше. "
    "additions — ТОЛЬКО НОВЫЕ обработки и пробелы из ЭТОГО хода эксперта (дельта), а не весь "
    "навык. Что уже есть в текущем навыке — НЕ повторяй. Если эксперт в этом ходе ничего нового "
    "не дал (только спросил/уточнил) — верни пустые массивы.\n"
    "У каждой обработки поле stage — этап диалога (приветствие · уточнение · презентация · "
    "цена · возражения · запись · завершение · другое); выбери подходящий по смыслу. "
    "Верни строго JSON по схеме. Всё на русском."
)

_CHAT_ADDITIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "additions": {
            "type": "object",
            "properties": {
                "objections": {"type": "array", "items": _OBJECTION_SCHEMA},
                "gaps": {"type": "array", "items": _GAP_SCHEMA},
            },
            "required": ["objections", "gaps"],
            "additionalProperties": False,
        },
    },
    "required": ["reply", "additions"],
    "additionalProperties": False,
}


def _build_chat_request(
    *,
    messages: list[dict[str, str]],
    attachments: list[dict[str, str]] | None,
    current_skill_doc: dict[str, Any] | None,
    service_name: str,
    openai_api_key: str,
    model: str | None,
    reasoning_effort: str | None,
) -> tuple[Any, dict[str, Any]]:
    """Собрать OpenAI-клиент и kwargs запроса для чат-ассистента навыка."""
    settings = get_settings()
    effective_model = (model or settings.skill_chat_model or "openai:gpt-5.1")
    if effective_model.startswith("openai:"):
        effective_model = effective_model.split(":", 1)[1]
    effort = reasoning_effort or settings.skill_chat_reasoning_effort or "none"

    context_parts = [f"УСЛУГА/НАВЫК: {service_name or '(без названия)'}"]
    if current_skill_doc:
        context_parts.append(
            "ТЕКУЩЕЕ СОСТОЯНИЕ НАВЫКА (дополняй его, не теряй уже собранное):\n"
            + json.dumps(current_skill_doc, ensure_ascii=False)
        )
    for att in attachments or []:
        name = str(att.get("name") or "материал")
        text = str(att.get("text") or "").strip()
        if text:
            context_parts.append(f"МАТЕРИАЛ ЭКСПЕРТА «{name}»:\n<material>\n{text[:20000]}\n</material>")

    chat_messages: list[dict[str, str]] = [{"role": "system", "content": _CHAT_SYSTEM_PROMPT}]
    chat_messages.append({"role": "system", "content": "\n\n".join(context_parts)})
    for m in messages:
        role = m.get("role")
        content = str(m.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            chat_messages.append({"role": role, "content": content})

    client = resolve_openai_client(openai_api_key=openai_api_key)
    request_kwargs: dict[str, Any] = dict(
        model=effective_model,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "skill_chat", "schema": _CHAT_ADDITIONS_SCHEMA, "strict": True},
        },
        messages=chat_messages,
    )
    if effort and effort not in ("off", "none"):
        request_kwargs["reasoning_effort"] = effort
    return client, request_kwargs


def _extract_partial_reply(buf: str) -> str:
    """Достать текущее значение поля reply из частичного JSON (reply идёт первым)."""
    m = _REPLY_START_RE.search(buf)
    if not m:
        return ""
    i = m.end()
    out: list[str] = []
    esc = False
    escapes = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\", "/": "/"}
    while i < len(buf):
        c = buf[i]
        if esc:
            out.append(escapes.get(c, c))
            esc = False
        elif c == "\\":
            esc = True
        elif c == '"':
            break  # строка reply закончилась
        else:
            out.append(c)
        i += 1
    return "".join(out)


_REPLY_START_RE = re.compile(r'"reply"\s*:\s*"')


async def converse_skill_stream(
    *,
    messages: list[dict[str, str]],
    attachments: list[dict[str, str]] | None,
    current_skill_doc: dict[str, Any] | None,
    service_name: str,
    openai_api_key: str,
    model: str | None = None,
    reasoning_effort: str | None = None,
):
    """Потоковый вариант converse_skill.

    Отдаёт события: ("delta", text) — прирост поля reply по мере генерации;
    в конце ("done", {"reply", "additions"}) — финальный reply + дельта навыка.
    """
    client, request_kwargs = _build_chat_request(
        messages=messages,
        attachments=attachments,
        current_skill_doc=current_skill_doc,
        service_name=service_name,
        openai_api_key=openai_api_key,
        model=model,
        reasoning_effort=reasoning_effort,
    )
    request_kwargs["stream"] = True

    buf = ""
    sent = 0
    stream = await client.chat.completions.create(**request_kwargs)
    async for chunk in stream:
        try:
            delta = chunk.choices[0].delta.content or ""
        except (IndexError, AttributeError):
            delta = ""
        if not delta:
            continue
        buf += delta
        reply_now = _extract_partial_reply(buf)
        if len(reply_now) > sent:
            yield ("delta", reply_now[sent:])
            sent = len(reply_now)

    parsed = {}
    try:
        parsed = json.loads(buf)
    except json.JSONDecodeError:
        pass
    raw_add = parsed.get("additions") or {}
    delta_doc = _sanitize_skill_doc({
        "objections": raw_add.get("objections") or [],
        "gaps": raw_add.get("gaps") or [],
    })
    additions = {"objections": delta_doc["objections"], "gaps": delta_doc["gaps"]}
    reply = str(parsed.get("reply") or _extract_partial_reply(buf) or "").strip()
    logger.info(
        "skill_conversed_stream",
        service_name=service_name,
        added_objections=len(additions["objections"]),
        added_gaps=len(additions["gaps"]),
    )
    yield ("done", {"reply": reply, "additions": additions})


async def converse_skill(
    *,
    messages: list[dict[str, str]],
    attachments: list[dict[str, str]] | None,
    current_skill_doc: dict[str, Any] | None,
    service_name: str,
    openai_api_key: str,
    model: str | None = None,
    reasoning_effort: str | None = None,
) -> dict[str, Any]:
    """Разговорная сборка навыка: чат эксперта + материалы → {reply, additions}.

    Возвращает ТОЛЬКО дельту (additions = новые обработки/пробелы этого хода), а не
    весь навык — так выход маленький и постоянный, а латентность не растёт с размером
    навыка. Мёрж делает вызывающая сторона по кнопке «Принять».

    messages — история диалога [{role: 'user'|'assistant', content}].
    attachments — приложенные материалы [{name, text}] (текст уже извлечён).
    current_skill_doc — текущий навык (как контекст, чтобы не дублировать).
    """
    client, request_kwargs = _build_chat_request(
        messages=messages,
        attachments=attachments,
        current_skill_doc=current_skill_doc,
        service_name=service_name,
        openai_api_key=openai_api_key,
        model=model,
        reasoning_effort=reasoning_effort,
    )

    response = await client.chat.completions.create(**request_kwargs)
    parsed = json.loads(response.choices[0].message.content or "{}")
    raw_add = parsed.get("additions") or {}
    # переиспользуем санитайзер: он гарантирует инвариант «обработка без фраз → пробел»
    delta = _sanitize_skill_doc({
        "objections": raw_add.get("objections") or [],
        "gaps": raw_add.get("gaps") or [],
    })
    additions = {"objections": delta["objections"], "gaps": delta["gaps"]}
    reply = str(parsed.get("reply") or "").strip()

    usage = getattr(response, "usage", None)
    logger.info(
        "skill_conversed",
        service_name=service_name,
        added_objections=len(additions["objections"]),
        added_gaps=len(additions["gaps"]),
        attachments=len(attachments or []),
        tokens_in=int(getattr(usage, "prompt_tokens", 0) or 0),
        tokens_out=int(getattr(usage, "completion_tokens", 0) or 0),
    )
    return {"reply": reply, "additions": additions}


async def retag_stages(
    skill_doc: dict[str, Any],
    service_name: str,
    *,
    openai_api_key: str,
    model: str | None = None,
) -> dict[str, Any]:
    """Проставить этап диалога (stage) каждой обработке, НЕ меняя текст.

    Возвращает копию skill_doc с обновлёнными stage у objections.
    """
    objections = [o for o in (skill_doc.get("objections") or []) if isinstance(o, dict)]
    if not objections:
        return skill_doc

    settings = get_settings()
    effective_model = (model or settings.skill_chat_model or "openai:gpt-4.1")
    if effective_model.startswith("openai:"):
        effective_model = effective_model.split(":", 1)[1]

    items = [
        {"i": i, "situation": str(o.get("situation") or ""), "trigger": str(o.get("trigger_when") or "")}
        for i, o in enumerate(objections)
    ]
    schema = {
        "type": "object",
        "properties": {
            "stages": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "i": {"type": "integer"},
                        "stage": {"type": "string", "enum": list(DIALOG_STAGES)},
                    },
                    "required": ["i", "stage"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["stages"],
        "additionalProperties": False,
    }
    system = (
        "Ты размечаешь ситуации навыка по этапам диалога с пациентом клиники. "
        "Этапы по порядку разговора: приветствие · уточнение · презентация · цена · "
        "возражения · запись · завершение · другое. Для каждой ситуации (по её смыслу и "
        "словам клиента) выбери один этап. Текст не меняй — только этап. Верни JSON."
    )
    user = f"УСЛУГА: {service_name}\nСИТУАЦИИ:\n" + json.dumps(items, ensure_ascii=False)

    client = resolve_openai_client(openai_api_key=openai_api_key)
    response = await client.chat.completions.create(
        model=effective_model,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "stage_tags", "schema": schema, "strict": True},
        },
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
    )
    parsed = json.loads(response.choices[0].message.content or "{}")
    by_i = {}
    for row in parsed.get("stages") or []:
        if isinstance(row, dict) and isinstance(row.get("i"), int):
            st = str(row.get("stage") or "")
            by_i[row["i"]] = st if st in DIALOG_STAGES else "другое"

    updated = dict(skill_doc)
    new_objs = []
    for i, o in enumerate(objections):
        o2 = dict(o)
        o2["stage"] = by_i.get(i, o.get("stage") or "другое")
        new_objs.append(o2)
    updated["objections"] = new_objs
    logger.info("skill_stages_retagged", service_name=service_name, count=len(new_objs))
    return updated


def _sanitize_skill_doc(parsed: dict[str, Any]) -> dict[str, Any]:
    """Нормализовать выход модели к схеме + гарантировать extractive-инвариант.

    Инвариант: у элементов gaps не бывает фраз; objection без фраз перекидывается
    в gaps (защита на случай, если модель всё же попытается «додумать»).
    """

    def _str_list(v: Any) -> list[str]:
        if not isinstance(v, list):
            return []
        return [str(x).strip() for x in v if str(x or "").strip()]

    objections: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []

    for raw in parsed.get("objections") or []:
        if not isinstance(raw, dict):
            continue
        situation = str(raw.get("situation") or "").strip()
        trigger = str(raw.get("trigger_when") or "").strip()
        if not situation and not trigger:
            continue
        phrases: list[dict[str, str]] = []
        for p in raw.get("phrases") or []:
            if not isinstance(p, dict):
                continue
            text = str(p.get("text") or "").strip()
            if not text:
                continue
            level = str(p.get("level") or "пример").strip()
            if level not in PHRASE_LEVELS:
                level = "пример"
            phrases.append({"text": text, "level": level})
        if not phrases:
            # без фраз эксперта — это пробел, не обработка
            gaps.append({"situation": situation, "trigger_when": trigger})
            continue
        stage = str(raw.get("stage") or "").strip()
        if stage not in DIALOG_STAGES:
            stage = "другое"
        objections.append(
            {
                "situation": situation,
                "trigger_when": trigger,
                "stage": stage,
                "approach": str(raw.get("approach") or "").strip(),
                "phrases": phrases,
                "forbidden": _str_list(raw.get("forbidden")),
            }
        )

    for raw in parsed.get("gaps") or []:
        if not isinstance(raw, dict):
            continue
        situation = str(raw.get("situation") or "").strip()
        trigger = str(raw.get("trigger_when") or "").strip()
        if situation or trigger:
            gaps.append({"situation": situation, "trigger_when": trigger})

    return {
        "context": str(parsed.get("context") or "").strip(),
        "objections": objections,
        "sequence": _str_list(parsed.get("sequence")),
        "facts_from_tool": _str_list(parsed.get("facts_from_tool")),
        "endings": _str_list(parsed.get("endings")),
        "gaps": gaps,
    }
