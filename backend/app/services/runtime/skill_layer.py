"""Навык-слой рантайма: «навык = продолжение эксперта».

Идея: вместо пофрагментной RAG-выборки тактик на каждое сообщение —
подгружать целиком дистиллированный навык (skill_doc) той услуги, что уже
определена в диалоге (по последнему resolve_clinic_facts). Навык формирует
поведение голосом эксперта (дословные фразы, обработки, концовки), но НЕ
подменяет факты — цены/слоты/названия остаются за инструментами.

Врезается в run_service.execute_agent_run как добавка к system_prompt_override,
за флагом settings.runtime_skill_layer_enabled.

Границы (жёстко):
- факты (цены, слоты, названия услуг) — только из resolve_clinic_facts/SQNS;
- фразы уровня «обязательно» подаются как жёсткая инструкция в блоке навыка;
- если для ситуации у эксперта нет фраз (gap) — вести своими словами, не
  выдумывать «фирменных» формулировок.

TODO(follow-up): пост-проверка вывода на дословность «обязательных» фраз
(зеркалить механику _extract_forced_reaction_output), сейчас — prompt-level.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)

# сколько последних resolve_clinic_facts просматривать в поисках активной услуги
_LOOKBACK = 8

# порядок и названия этапов диалога (для «линии жизни» разговора в промпте)
_STAGE_ORDER = (
    "приветствие", "уточнение", "презентация", "цена", "возражения", "запись", "завершение", "другое",
)
_STAGE_LABELS = {
    "приветствие": "Приветствие",
    "уточнение": "Уточнение потребности",
    "презентация": "Презентация",
    "цена": "Цена",
    "возражения": "Возражения и сомнения",
    "запись": "Запись",
    "завершение": "Завершение",
    "другое": "Другое",
}


async def find_active_service_ids(
    db: AsyncSession, *, agent_id: UUID, session_id: str
) -> list[str]:
    """Кандидаты активных услуг сессии по последним resolve_clinic_facts.

    Приоритет — однозначно определённая услуга (`resolved.service_external_id`).
    Если её нет (частый случай: несколько услуг, нужно уточнение) — берём
    `services[].external_id` самого свежего вызова. Возвращаем строки — так связь
    сравнивается с script_flows.service_external_ids (массив строк).
    """
    rows = (
        await db.execute(
            text(
                """
                SELECT tcl.response_payload
                FROM tool_call_logs tcl
                JOIN runs r ON r.id = tcl.run_id
                WHERE r.agent_id = :aid
                  AND r.session_id = :sid
                  AND tcl.tool_name = 'resolve_clinic_facts'
                ORDER BY tcl.invoked_at DESC
                LIMIT :lim
                """
            ),
            {"aid": agent_id, "sid": session_id, "lim": _LOOKBACK},
        )
    ).fetchall()

    # 1) однозначно определённая услуга — самый надёжный сигнал
    for (payload,) in rows:
        if not isinstance(payload, dict):
            continue
        resolved = payload.get("resolved")
        if isinstance(resolved, dict):
            svc = resolved.get("service_external_id")
            if svc is not None and str(svc).strip():
                return [str(svc)]

    # 2) fallback: услуги-кандидаты из самого свежего вызова
    for (payload,) in rows:
        if not isinstance(payload, dict):
            continue
        services = payload.get("services")
        if isinstance(services, list) and services:
            ids = [
                str(s.get("external_id"))
                for s in services
                if isinstance(s, dict) and s.get("external_id") is not None
            ]
            ids = [i for i in ids if i.strip()]
            if ids:
                return ids
    return []


# Тема разговора определяется по ТЕКСТУ навыка, без идентификаторов и без
# зависимости от инструментов: у навыка есть имя, контекст и триггеры — реальные
# формулировки клиентов («Клиент спрашивает про биоревитализацию: "У вас есть…"»).
# Их и сопоставляем с сообщением. Работает с первой реплики, до любого тула, и
# одинаково для клиники, автосалона или юрфирмы — материал пишет эксперт, а не код.

# Короткие слова выкидываем: «есть», «хочу», «как» темы не различают.
_MIN_TOKEN_LEN = 5
# Грубая нормализация русской морфологии: сравниваем по началу слова, чтобы
# «биоревитализацию» и «биоревитализация» считались одним словом.
_STEM_LEN = 6
# Вес совпадения: имя навыка — самый сильный сигнал, контекст — самый слабый.
_WEIGHT_NAME = 3
_WEIGHT_TRIGGER = 2
_WEIGHT_CONTEXT = 1
# Минимальный балл, ниже которого тема считается неопределённой (общий режим).
_MIN_TOPIC_SCORE = 3


def _stems(text: str) -> set[str]:
    """Значимые слова текста, огрублённые до основы."""
    out: set[str] = set()
    word = []
    for ch in str(text or "").lower():
        if ch.isalpha() or ch.isdigit():
            word.append(ch)
        else:
            if len(word) >= _MIN_TOKEN_LEN:
                out.add("".join(word[:_STEM_LEN]))
            word = []
    if len(word) >= _MIN_TOKEN_LEN:
        out.add("".join(word[:_STEM_LEN]))
    return out


def score_skill_match(message: str, skill_name: str, skill_doc: dict[str, Any]) -> int:
    """Насколько навык относится к сообщению клиента. 0 — не относится."""
    msg = _stems(message)
    if not msg:
        return 0
    name_stems = _stems(skill_name)
    trigger_stems: set[str] = set()
    for o in (skill_doc.get("objections") or []):
        if isinstance(o, dict):
            trigger_stems |= _stems(o.get("trigger_when") or o.get("situation") or "")
    context_stems = _stems(skill_doc.get("context") or "")

    score = 0
    score += _WEIGHT_NAME * len(msg & name_stems)
    score += _WEIGHT_TRIGGER * len(msg & (trigger_stems - name_stems))
    score += _WEIGHT_CONTEXT * len(msg & (context_stems - name_stems - trigger_stems))
    return score


def find_active_skills_by_message(
    message: str, docs: list[tuple[str, dict[str, Any]]]
) -> set[str]:
    """Навыки, к которым относится сообщение клиента. Пусто — тема не ясна.

    Берём только лидеров: навык с максимальным баллом и те, кто набрал столько же.
    Если лидера нет (балл ниже порога) — сужать нечего, работает общий режим.
    """
    scored = [
        (score_skill_match(message, name, doc), name)
        for name, doc in docs
        if isinstance(doc, dict)
    ]
    scored = [(sc, name) for sc, name in scored if sc >= _MIN_TOPIC_SCORE]
    if not scored:
        return set()
    best = max(sc for sc, _ in scored)
    return {name for sc, name in scored if sc == best}


async def load_skill_docs_for_services(
    db: AsyncSession, *, agent_id: UUID, service_external_ids: list[str]
) -> list[tuple[str, dict[str, Any]]]:
    """Опубликованные навыки, пересекающиеся с любой из услуг-кандидатов.

    Читаем из expert_skills (навыки отделены от потоков): status=published,
    не удалён. Возвращает [(skill_name, skill_doc), ...] без дублей.
    """
    if not service_external_ids:
        return []
    rows = (
        await db.execute(
            text(
                """
                SELECT name, skill_doc, updated_at
                FROM expert_skills es
                WHERE es.agent_id = :aid
                  AND es.status = 'published'
                  AND es.is_deleted = false
                  AND es.skill_doc IS NOT NULL
                  AND EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements_text(es.service_external_ids) AS e
                    WHERE e = ANY(:svcs)
                  )
                ORDER BY updated_at DESC
                """
            ),
            {"aid": agent_id, "svcs": [str(s) for s in service_external_ids]},
        )
    ).fetchall()
    out: list[tuple[str, dict[str, Any]]] = []
    for name, skill_doc, _updated in rows:
        if isinstance(skill_doc, dict):
            out.append((str(name or ""), skill_doc))
    return out


def render_skill_doc(skill_doc: dict[str, Any], *, service_name: str) -> str:
    """Собрать блок навыка для system_prompt — связная инструкция голосом эксперта."""
    lines: list[str] = []
    lines.append(f"## НАВЫК ЭКСПЕРТА: {service_name}".rstrip())
    lines.append(
        "Ниже — накопленный опыт эксперта по этой услуге: как вести пациента и "
        "какими словами. Это ТВОЁ продолжение эксперта — держись его подхода и его "
        "формулировок. Факты (цены, слоты, названия) всё равно бери только из "
        "инструментов, не из этого блока."
    )

    context = str(skill_doc.get("context") or "").strip()
    if context:
        lines.append("\n**Контекст навыка:** " + context)

    def _render_objection(o: dict[str, Any]) -> None:
        situation = str(o.get("situation") or "").strip()
        trigger = str(o.get("trigger_when") or "").strip()
        approach = str(o.get("approach") or "").strip()
        head = f"\n— Если клиент: {trigger}" if trigger else (f"\n— Ситуация: {situation}" if situation else "\n—")
        lines.append(head)
        if situation and trigger:
            lines.append(f"  ({situation})")
        if approach:
            lines.append(f"  Подход: {approach}")
        must: list[str] = []
        example: list[str] = []
        for p in o.get("phrases") or []:
            if not isinstance(p, dict):
                continue
            t = str(p.get("text") or "").strip()
            if not t:
                continue
            if str(p.get("level")) == "обязательно":
                must.append(t)
            else:
                example.append(t)
        if example:
            lines.append("  Фразы эксперта (образцы интонации, можно адаптировать):")
            lines.extend(f"    · {t}" for t in example)
        if must:
            lines.append("  Обязательные формулировки (используй практически дословно):")
            lines.extend(f"    ‼ {t}" for t in must)
        forbidden = [str(f).strip() for f in (o.get("forbidden") or []) if str(f).strip()]
        if forbidden:
            lines.append("  Избегай: " + "; ".join(forbidden))

    objections = [o for o in (skill_doc.get("objections") or []) if isinstance(o, dict)]
    if objections:
        lines.append(
            "\n**Как вести диалог по этапам (сверху вниз — ход разговора), голосом эксперта:**"
        )
        by_stage: dict[str, list[dict[str, Any]]] = {}
        for o in objections:
            st = str(o.get("stage") or "другое")
            if st not in _STAGE_ORDER:
                st = "другое"
            by_stage.setdefault(st, []).append(o)
        for stage in _STAGE_ORDER:
            stage_objs = by_stage.get(stage) or []
            if not stage_objs:
                continue
            lines.append(f"\n### Этап: {_STAGE_LABELS[stage]}")
            for o in stage_objs:
                _render_objection(o)

    facts = [str(f).strip() for f in (skill_doc.get("facts_from_tool") or []) if str(f).strip()]
    if facts:
        lines.append(
            "\n**Эти факты бери из инструментов, не из головы:** " + "; ".join(facts)
        )

    endings = [str(e).strip() for e in (skill_doc.get("endings") or []) if str(e).strip()]
    if endings:
        lines.append("\n**Варианты завершений/переходов к шагу:**")
        lines.extend(f"  · {e}" for e in endings)

    gaps = skill_doc.get("gaps") or []
    if gaps:
        lines.append(
            "\n**Пробелы (готовых фраз эксперта нет — веди своими словами, "
            "не выдумывай «фирменных» реплик):**"
        )
        for g in gaps:
            if not isinstance(g, dict):
                continue
            s = str(g.get("situation") or "").strip()
            if s:
                lines.append(f"  · {s}")

    return "\n".join(lines).strip()


async def build_skill_layer_prompt(
    db: AsyncSession, *, agent_id: UUID, session_id: str
) -> str | None:
    """Собрать добавку навык-слоя для system_prompt_override, либо None.

    None — когда услуга ещё не определена или у её потока нет skill_doc.
    """
    service_ids = await find_active_service_ids(
        db, agent_id=agent_id, session_id=session_id
    )
    if not service_ids:
        return None
    docs = await load_skill_docs_for_services(
        db, agent_id=agent_id, service_external_ids=service_ids
    )
    if not docs:
        return None
    blocks = [render_skill_doc(sd, service_name=name) for name, sd in docs if sd]
    blocks = [b for b in blocks if b]
    if not blocks:
        return None
    logger.info(
        "skill_layer_injected",
        agent_id=str(agent_id),
        session_id=session_id,
        service_external_ids=service_ids,
        skills=len(blocks),
    )
    return "\n\n" + "\n\n".join(blocks)


# ── Стиль-слой (голос эксперта) ──────────────────────────────────────────────
#
# Отличие от навык-слоя выше: тот подгружает skill_doc ЦЕЛИКОМ (десятки тысяч
# символов) и только когда услуга диалога определена resolve_clinic_facts —
# поэтому молчит на первых репликах, где решается тон приветствия. Стиль-слой
# наоборот: компактная выжимка (фразы «обязательно»/«дословно», запреты,
# немного образцов) из ВСЕХ опубликованных навыков агента, в каждом запуске,
# с первой реплики. Полный материал модель по-прежнему может достать сама
# через тул use_expert_skill.

# Бюджет выжимки в символах: ~1.4 тыс. токенов на запрос. Секции добавляются по
# приоритету (обязательные → запреты → дословные → образцы → завершения), пока
# влезают в бюджет; внутри секции фразы не режутся — либо целиком, либо никак.
# Запреты идут сразу за обязательными: они короткие, а анти-паттерны тона
# («давайте я вам всё расскажу») — половина претензий эксперта к модели.
STYLE_DIGEST_MAX_CHARS = 5200

# Образцов интонации («пример») в выжимке не больше стольки — few-shot после
# 5-7 примеров не улучшается, а бюджет съедает.
_STYLE_MAX_EXAMPLES = 8

# У навыков «не про эту услугу» берём только несколько ключевых фраз: иначе
# обязательные реплики одной услуги начинают звучать в разговоре про другую.
# Обрезаем ТОЛЬКО когда услуга диалога известна: пока она не определилась
# (первые реплики), сузить нечего — режем по общему бюджету.
_MAX_OTHER_SKILL_PHRASES = 3

# Потолок секции запретов. Запреты общие и короткие, поэтому при нескольких
# навыках их набираются сотни — без потолка они вытесняют из бюджета сами фразы
# (проверено на живых данных: 99 строк запретов и 3 фразы).
_MAX_FORBIDDEN_LINES = 20


def _iter_skill_phrases(
    skill_doc: dict[str, Any],
) -> tuple[list[tuple[str, str]], list[tuple[str, str]], list[tuple[str, str]], list[str], list[str]]:
    """Разобрать skill_doc на (обязательные, дословные, примеры, запреты, завершения)."""
    musts: list[tuple[str, str]] = []
    verbatims: list[tuple[str, str]] = []
    examples: list[tuple[str, str]] = []
    forbidden: list[str] = []
    endings: list[str] = []
    for o in skill_doc.get("objections") or []:
        if not isinstance(o, dict):
            continue
        trigger = str(o.get("trigger_when") or o.get("situation") or "").strip()
        for p in o.get("phrases") or []:
            if not isinstance(p, dict):
                continue
            phrase = str(p.get("text") or "").strip()
            if not phrase:
                continue
            level = str(p.get("level") or "").strip().lower()
            if level == "обязательно":
                musts.append((trigger, phrase))
            elif level == "дословно":
                verbatims.append((trigger, phrase))
            else:
                examples.append((trigger, phrase))
        for f in o.get("forbidden") or []:
            f_text = str(f).strip()
            if f_text:
                forbidden.append(f_text)
    for e in skill_doc.get("endings") or []:
        e_text = str(e).strip()
        if e_text:
            endings.append(e_text)
    return musts, verbatims, examples, forbidden, endings


def render_style_digest(
    docs: list[tuple[str, dict[str, Any]]],
    *,
    active_skill_names: set[str] | None = None,
) -> str | None:
    """Собрать компактный блок «голос эксперта» из опубликованных skill_doc.

    `active_skill_names` — навыки услуги, о которой идёт речь прямо сейчас (по
    resolve_clinic_facts). Их фразы идут первыми и целиком; у остальных берём
    несколько ключевых, чтобы обязательные реплики одной услуги не подменяли
    другую. Запреты тона общие: они не привязаны к услуге и действуют всегда.

    None — когда стилевого материала нет вообще (агент без навыков).
    """
    active = active_skill_names or set()
    parsed: list[dict[str, Any]] = []
    for name, skill_doc in docs:
        if not isinstance(skill_doc, dict):
            continue
        musts, verbatims, examples, forbidden, _endings = _iter_skill_phrases(skill_doc)
        parsed.append({
            "name": str(name or ""),
            "musts": musts,
            "verbatims": verbatims,
            "examples": examples,
            "forbidden": forbidden,
            "active": str(name or "") in active,
        })
    if not parsed:
        return None

    # Активные навыки — первыми: их фразы важнее и должны выигрывать бюджет.
    parsed.sort(key=lambda sk: not sk["active"])
    multi = len(parsed) > 1
    # Сужать выдачу есть смысл, только когда услуга диалога определена.
    narrowing = multi and any(sk["active"] for sk in parsed)

    seen: set[str] = set()

    def _lines(kind: str, *, only: str = "all") -> list[str]:
        """Строки секции: only='active' | 'other' | 'all'. Активные — первыми, с дедупом."""
        out: list[str] = []
        for sk in parsed:
            if only == "active" and not sk["active"]:
                continue
            if only == "other" and sk["active"]:
                continue
            items = sk[kind]
            if narrowing and not sk["active"]:
                items = items[:_MAX_OTHER_SKILL_PHRASES]
            for trigger, phrase in items:
                key = phrase.strip().lower()
                if not key or key in seen:
                    continue
                seen.add(key)
                scope = f"[{sk['name']}] " if multi else ""
                out.append(f"— {scope}{trigger}: «{phrase}»" if trigger else f"— {scope}«{phrase}»")
        return out

    # Когда услуга известна — фразы её навыка идут первой секцией целиком, и только
    # потом обязательные реплики прочих тем. Иначе чужая «обязательная» вытесняла бы
    # из бюджета фразы того навыка, о котором идёт разговор.
    active_lines = (_lines("musts", only="active") + _lines("verbatims", only="active")) if narrowing else []
    other_lines = (_lines("musts", only="other") + _lines("verbatims", only="other")) if narrowing else []
    musts_lines = [] if narrowing else _lines("musts")
    verbatim_lines = [] if narrowing else _lines("verbatims")
    # Образцы интонации — только у навыков услуги, о которой идёт речь: они
    # длинные, а вне своей темы бесполезны. Если услуга ещё не определилась —
    # берём образцы первого навыка, чтобы тон был задан с первой реплики.
    example_sources = [sk for sk in parsed if sk["active"]] or parsed[: (1 if multi else len(parsed))]
    example_lines: list[str] = []
    for sk in example_sources:
        for trigger, phrase in sk["examples"][:_STYLE_MAX_EXAMPLES]:
            key = phrase.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            scope = f"[{sk['name']}] " if multi else ""
            example_lines.append(
                f"— {scope}{trigger}: «{phrase}»" if trigger else f"— {scope}«{phrase}»"
            )

    forbidden_lines: list[str] = []
    seen_forbidden: set[str] = set()
    for sk in parsed:
        for f in sk["forbidden"]:
            key = f.strip().lower()
            if key and key not in seen_forbidden:
                seen_forbidden.add(key)
                forbidden_lines.append(f"— {f}")

    if not (musts_lines or verbatim_lines or active_lines or other_lines or example_lines):
        return None

    header = [
        "## ГОЛОС ЭКСПЕРТА — стиль ответов",
        "Это формулировки и манера живого эксперта клиники. Держись их во ВСЕХ ответах: "
        "интонация, длина, обороты. Факты (цены, слоты, названия услуг) по-прежнему "
        "бери только из инструментов — фразы ниже задают КАК говорить, а не ЧТО.",
    ]
    if multi:
        header.append(
            "В квадратных скобках — тема, к которой относится фраза: применяй её, "
            "только когда разговор именно об этой теме."
        )
        active_names = [sk["name"] for sk in parsed if sk["active"]]
        if active_names:
            header.append("Сейчас разговор про: " + ", ".join(active_names) + ".")
    header_text = "\n".join(header)

    sections: list[tuple[str, list[str]]] = []
    # Запреты идут первыми: они короткие (потолок _MAX_FORBIDDEN_LINES), универсальны
    # для всех тем и несут комплаенс — их нельзя вытеснять длинными фразами услуги.
    if forbidden_lines:
        sections.append(("Запрещено (никогда не пиши):", forbidden_lines[:_MAX_FORBIDDEN_LINES]))
    if active_lines:
        sections.append((
            "Фразы эксперта по текущей теме (используй практически дословно):",
            active_lines,
        ))
    if musts_lines:
        sections.append((
            "Обязательные формулировки (используй практически дословно, когда ситуация совпала):",
            musts_lines,
        ))
    if other_lines:
        sections.append((
            "Фразы по другим темам (только если разговор перейдёт на них):",
            other_lines,
        ))
    if verbatim_lines:
        sections.append(("Фирменные фразы эксперта (говори именно так):", verbatim_lines))
    if example_lines:
        sections.append((
            "Образцы интонации (адаптируй под контекст, не копируй факты):",
            example_lines,
        ))
    # endings из skill_doc сознательно НЕ включаем: в реальных данных это
    # протокольные описания исходов («администратор зафиксировал…»), а не фразы —
    # модель приняла бы их за инструкции процесса.

    lines: list[str] = [header_text]
    used = len(header_text)
    for title, items in sections:
        block: list[str] = ["", title]
        block_len = sum(len(x) + 1 for x in block)
        added_any = False
        for item in items:
            if used + block_len + len(item) + 1 > STYLE_DIGEST_MAX_CHARS:
                break
            block.append(item)
            block_len += len(item) + 1
            added_any = True
        if added_any:
            lines.extend(block)
            used += block_len

    return "\n".join(lines).strip()


async def build_style_digest_prompt(
    db: AsyncSession, *, agent_id: UUID, input_message: str | None = None
) -> str | None:
    """Загрузить опубликованные навыки агента и собрать стиль-выжимку, либо None.

    Тему разговора определяем по сообщению клиента и ТЕКСТУ навыков (имя,
    контекст, триггеры) — без идентификаторов, без обращения к инструментам и
    без знания сферы бизнеса. Совпавшие навыки активны: их фразы идут первыми
    и целиком. Тема не ясна (приветствие, общий вопрос) — общий режим.
    """
    rows = (
        await db.execute(
            text(
                """
                SELECT name, skill_doc
                FROM expert_skills
                WHERE agent_id = :agent_id
                  AND status = 'published'
                  AND is_deleted = false
                  AND skill_doc IS NOT NULL
                ORDER BY updated_at DESC NULLS LAST
                LIMIT 12
                """
            ),
            {"agent_id": agent_id},
        )
    ).all()
    docs: list[tuple[str, dict[str, Any]]] = []
    for name, skill_doc in rows:
        # asyncpg может отдать JSONB строкой — разбираем оба варианта.
        if isinstance(skill_doc, str):
            try:
                skill_doc = json.loads(skill_doc)
            except (TypeError, ValueError):
                continue
        if not isinstance(skill_doc, dict):
            continue
        docs.append((str(name or ""), skill_doc))
    if not docs:
        return None

    active_names: set[str] = set()
    if input_message and len(docs) > 1:
        active_names = find_active_skills_by_message(input_message, docs)

    digest = render_style_digest(docs, active_skill_names=active_names)
    if digest:
        logger.info(
            "style_layer_injected",
            agent_id=str(agent_id),
            skills=len(docs),
            active_skills=sorted(active_names),
            digest_chars=len(digest),
        )
    return digest
