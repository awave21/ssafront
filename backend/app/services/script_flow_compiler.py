"""
script_flow_compiler.py

Converts a Vue Flow graph (expert script) into a structured natural-language
document that an LLM can read as expert guidance.

 Секции «осей» (ситуация → мотив → аргументы → вопросы) заданы явными
 заголовками для expertise / question / trigger, чтобы чанкинг в retrieval
 и поиск по смыслу работали стабильнее.
"""
from __future__ import annotations

import re
from typing import Any, Callable

# ── Variable substitution ─────────────────────────────────────────────────────

# Pattern for static variables defined in flow_metadata.variables
# Syntax in node fields: {{имя_переменной}}
_VAR_PATTERN = re.compile(r"\{\{(\w+)\}\}")

# Pattern for dynamic directory-lookup hints
# Syntax: [[поиск: <запрос>]]
# These are left in the compiled text as-is; the LLM expertise bridge instructs
# the model to resolve them using its search tools at response time.
_LOOKUP_PATTERN = re.compile(r"\[\[поиск:\s*([^\]]+)\]\]")


def _condition_handle_map_from_data(data: dict[str, Any]) -> dict[str, str]:
    """Map Vue Flow sourceHandle (`branch:<id>` or legacy `cond-<i>`) to branch labels."""
    raw = data.get("conditions")
    handle_map: dict[str, str] = {}
    if isinstance(raw, list):
        for i, c in enumerate(raw):
            if isinstance(c, dict):
                bid = str(c.get("id") or "").strip()
                lbl = str(c.get("label") or "").strip()
                if bid:
                    handle_map[f"branch:{bid}"] = lbl or f"ветка {i + 1}"
                elif lbl:
                    handle_map[f"cond-{i}"] = lbl
            else:
                lbl = str(c).strip()
                if lbl:
                    handle_map[f"cond-{i}"] = lbl
    handle_map["cond-default"] = "по умолчанию"
    return handle_map


def _branch_label_fallback(src_handle: str) -> str:
    s = str(src_handle)
    if s.startswith("branch:"):
        return "ветка"
    return s.replace("cond-", "ветка ")


def _resolve_variable(key: str, binding: Any) -> str:
    """
    Resolve a single variable binding to its substitution string.

    binding can be:
      - str → treated as a static literal (backward compat)
      - {"source_type": "static",  "value": "..."}   → literal substitution
      - {"source_type": "search",  "search_query": "..."} → [[поиск: query]]
        (the LLM will resolve this using its directory search tools at runtime)
      - {"source_type": "function", "function_id": "...", "argument_hint": "...", "llm_instruction": "..."}
        → [[функция: argument_hint]] — модель должна вызвать указанную функцию агента
    """
    if isinstance(binding, str):
        return binding

    if not isinstance(binding, dict):
        return f"{{{{{key}}}}}"  # unknown format — keep placeholder

    source_type = binding.get("source_type", "static")

    if source_type == "search":
        query = (binding.get("search_query") or "").strip()
        if not query:
            return f"{{{{{key}}}}}"
        return f"[[поиск: {query}]]"

    if source_type == "function":
        hint = (binding.get("argument_hint") or "").strip()
        return f"[[функция: {hint}]]" if hint else f"{{{{{key}}}}}"

    # static
    value = (binding.get("value") or "").strip()
    return value if value else f"{{{{{key}}}}}"


def substitute_flow_variables(text: str, variables: dict[str, Any]) -> str:
    """
    Replace {{variable_name}} placeholders in text.

    Variable bindings come from flow_metadata.variables and support two forms:
      - static  → literal text substitution
      - search  → expands to [[поиск: query]] which the LLM resolves at runtime
        using its directory/knowledge tools (prices, service names, employees…)

    Unknown variables (key not defined) are left unchanged.
    """
    if not variables or not text:
        return text

    def _replace(m: re.Match) -> str:
        key = m.group(1)
        if key not in variables:
            return m.group(0)  # keep original if variable not defined
        return _resolve_variable(key, variables[key])

    return _VAR_PATTERN.sub(_replace, text)


_FUNCTION_HINT_PATTERN = re.compile(r"\[\[функция:\s*([^\]]+)\]\]")


def highlight_lookup_hints(text: str) -> str:
    """
    Wrap [[поиск: X]] and [[функция: X]] hints so the LLM clearly understands
    these are dynamic placeholders to resolve via tools at runtime.
    """
    def _wrap_search(m: re.Match) -> str:
        query = m.group(1).strip()
        return f"[⚡ найди в справочнике: «{query}»]"

    def _wrap_function(m: re.Match) -> str:
        hint = m.group(1).strip()
        return f"[🔧 вызови функцию для: «{hint}»]"

    text = _LOOKUP_PATTERN.sub(_wrap_search, text)
    return _FUNCTION_HINT_PATTERN.sub(_wrap_function, text)


# ── Stage label map ───────────────────────────────────────────────────────────
_STAGE_LABELS: dict[str, str] = {
    "opening":              "Открытие",
    "qualification":        "Квалификация",
    "presentation":         "Презентация",
    "objection_price":      "Возражение — цена",
    "objection_comparison": "Возражение — сравнение",
    "objection_time":       "Возражение — время/занятость",
    "objection_trust":      "Возражение — доверие",
    "closing":              "Закрытие / запись",
    "universal":            "Универсальный",
}

_NODE_TYPE_LABELS: dict[str, str] = {
    "trigger":       "Триггер",
    "expertise":     "Экспертиза",
    "question":      "Вопрос",
    "condition":     "Условие",
    "goto":          "Переход",
    "business_rule": "Бизнес-правило",
    "end":           "Конец",
}

# Short hint shown in parentheses after the type label in the compiled document.
# Helps the LLM understand the intent of each node at a glance.
_NODE_TYPE_HINTS: dict[str, str] = {
    "trigger":       "входная точка — с этой ситуации начинается поток",
    "expertise":     "экспертное знание — что сказать и как повести разговор",
    "question":      "уточняющий вопрос — задай клиенту, чтобы продвинуть диалог",
    "condition":     "ветвление — выбери ветку по ответу клиента",
    "goto":          "переход — продолжение в другом потоке или сценарии",
    "business_rule": "структурное правило для сущности или процесса",
    "end":           "финал ветки — цель достигнута или разговор завершён",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _edge_label(edge: dict[str, Any]) -> str:
    lab = edge.get("label")
    if isinstance(lab, str) and lab.strip():
        return lab.strip()
    data = edge.get("data")
    if isinstance(data, dict):
        inner = data.get("label")
        if isinstance(inner, str) and inner.strip():
            return inner.strip()
    return ""


def _str(val: Any, fallback: str = "") -> str:
    if isinstance(val, str) and val.strip():
        return val.strip()
    return fallback


def _node_data(node: dict[str, Any]) -> dict[str, Any]:
    d = node.get("data")
    return d if isinstance(d, dict) else {}


def _node_title(node: dict[str, Any]) -> str:
    data = _node_data(node)
    for key in ("title", "label", "name"):
        v = _str(data.get(key))
        if v:
            return v
    ntype = _str(node.get("type"))
    return _NODE_TYPE_LABELS.get(ntype, ntype) if ntype else "Шаг"


def _node_type(node: dict[str, Any]) -> str:
    data = _node_data(node)
    return _str(data.get("node_type")) or _str(node.get("type")) or "expertise"


def _emit_section_heading(out: list[str], indent: str, title: str) -> None:
    """Явная метка секции для лучшего разбиения текста при индексации."""
    out.append(f"{indent}  ▸ **{title}**")


def _render_business_rule_content(
    *,
    data: dict[str, Any],
    indent: str,
    _v: Callable[[str], str],
    out: list[str],
    profile_text: str | None = None,
) -> None:
    """Структурированный вывод бизнес-правила — отдельно условие и действие, чтобы LLM/RAG не смешивали их с диалоговыми полями."""
    ds = _str(data.get("data_source"))
    if ds:
        _emit_section_heading(out, indent, "Источник данных")
        out.append(f"{indent}  {ds}")

    et = _str(data.get("entity_type"))
    eid = _str(data.get("entity_id"))
    if et or eid:
        _emit_section_heading(out, indent, "Сущность правила")
        parts: list[str] = []
        if et:
            parts.append(et)
        if eid:
            parts.append(f"id: {eid}")
        out.append(f"{indent}  {' · '.join(parts)}")

    if profile_text and profile_text.strip():
        label = (
            "Профиль специалиста (справочник SQNS)"
            if et == "employee"
            else "Описание услуги (справочник SQNS)"
            if et == "service"
            else "Текст из справочника SQNS"
        )
        _emit_section_heading(out, indent, label)
        out.append(f"{indent}  {_v(profile_text.strip())}")

    pri = data.get("rule_priority")
    if isinstance(pri, int):
        out.append(f"{indent}  ▸ **Приоритет**: {pri}")

    if data.get("rule_active") is False:
        out.append(f"{indent}  ▸ **Правило выключено** (не применять до включения в редакторе)")

    cond = _str(data.get("rule_condition"))
    if cond:
        _emit_section_heading(out, indent, "Условие — когда правило срабатывает")
        out.append(f"{indent}  {_v(cond)}")

    act = _str(data.get("rule_action"))
    if act:
        _emit_section_heading(out, indent, "Действие — что делает агент (алгоритм, формат ответа)")
        out.append(f"{indent}  {_v(act)}")

    situation = _str(data.get("situation"))
    if situation:
        _emit_section_heading(out, indent, "Комментарий эксперта (не дословно клиенту)")
        out.append(f"{indent}  {_v(situation)}")

    constraints = data.get("constraints")
    if isinstance(constraints, dict):
        req = _str(constraints.get("requires_entity")).lower()
        if req and req != "none":
            _emit_section_heading(out, indent, "Требования к контексту диалога")
            out.append(f"{indent}  В диалоге должны быть уточнены: **{req}**")
        must = constraints.get("must_follow_node_refs")
        if isinstance(must, list) and must:
            refs = ", ".join(str(x) for x in must if str(x).strip())
            if refs:
                _emit_section_heading(out, indent, "Логический порядок (id узлов, до которых нужно дойти)")
                out.append(f"{indent}  {refs}")


def _render_node_content_axes(
    *,
    ntype: str,
    data: dict[str, Any],
    indent: str,
    _v: Callable[[str], str],
    out: list[str],
    schema_version: int = 1,
) -> None:
    """
    Вывод полей узла с заголовками осей (возражение → мотив → аргументы → …).
    Для типов без явной схемы не вызывается.
    """
    situation = _str(data.get("situation"))
    why = _str(data.get("why_it_works"))
    approach = _str(data.get("approach"))
    phrases = data.get("example_phrases")
    watch = _str(data.get("watch_out"))
    question = _str(data.get("good_question"))
    comm_style = _str(data.get("communication_style"))
    preferred = data.get("preferred_phrases")
    forbidden = data.get("forbidden_phrases")
    followup_q = _str(data.get("required_followup_question"))

    if ntype == "expertise":
        if situation:
            _emit_section_heading(out, indent, "Возражение / ситуация клиента")
            out.append(f"{indent}  {_v(situation)}")
        if why:
            _emit_section_heading(out, indent, "Мотив (психология)")
            out.append(f"{indent}  {_v(why)}")
        if approach:
            _emit_section_heading(out, indent, "Аргументы и тактика")
            out.append(f"{indent}  {_v(approach)}")
        if isinstance(phrases, list) and phrases:
            clean = [_v(str(p).strip()) for p in phrases if str(p).strip()]
            if clean:
                _emit_section_heading(out, indent, "Вариативные формулировки (примеры)")
                for p in clean:
                    out.append(f"{indent}  - «{p}»")
        if comm_style:
            _emit_section_heading(out, indent, "Стиль общения")
            out.append(f"{indent}  {_v(comm_style)}")
        if isinstance(preferred, list) and preferred:
            clean_pref = [_v(str(p).strip()) for p in preferred if str(p).strip()]
            if clean_pref:
                _emit_section_heading(out, indent, "Предпочтительные формулировки")
                for p in clean_pref:
                    out.append(f"{indent}  + «{p}»")
        if isinstance(forbidden, list) and forbidden:
            clean_forb = [_v(str(p).strip()) for p in forbidden if str(p).strip()]
            if clean_forb:
                _emit_section_heading(out, indent, "Запрещённые фразы")
                for p in clean_forb:
                    out.append(f"{indent}  ✗ «{p}»")
        if watch:
            _emit_section_heading(out, indent, "Табу (не делай)")
            out.append(f"{indent}  {_v(watch)}")
        if followup_q:
            _emit_section_heading(out, indent, "Обязательный вопрос после тактики")
            out.append(f"{indent}  «{_v(followup_q)}»")
        elif question:
            _emit_section_heading(out, indent, "Уточняющий вопрос")
            out.append(f"{indent}  «{_v(question)}»")
        return

    if ntype == "question":
        if schema_version >= 2:
            if question:
                _emit_section_heading(out, indent, "Вопрос клиенту")
                out.append(f"{indent}  «{_v(question)}»")
            eat = _str(data.get("expected_answer_type"))
            if eat:
                _emit_section_heading(out, indent, "Ожидаемый тип ответа")
                out.append(f"{indent}  {_v(eat)}")
            why_ask = _str(data.get("why_we_ask"))
            if why_ask:
                _emit_section_heading(out, indent, "Зачем спрашиваем")
                out.append(f"{indent}  {_v(why_ask)}")
            alts = data.get("alternative_phrasings")
            if isinstance(alts, list) and alts:
                clean = [_v(str(p).strip()) for p in alts if str(p).strip()]
                if clean:
                    _emit_section_heading(out, indent, "Альтернативные формулировки")
                    for p in clean:
                        out.append(f"{indent}  - «{p}»")
            return
        if question:
            _emit_section_heading(out, indent, "Ключевой вопрос клиенту")
            out.append(f"{indent}  «{_v(question)}»")
        if situation:
            _emit_section_heading(out, indent, "Контекст: когда задаём")
            out.append(f"{indent}  {_v(situation)}")
        if approach:
            _emit_section_heading(out, indent, "Как подвести к вопросу")
            out.append(f"{indent}  {_v(approach)}")
        if isinstance(phrases, list) and phrases:
            clean = [_v(str(p).strip()) for p in phrases if str(p).strip()]
            if clean:
                _emit_section_heading(out, indent, "Альтернативные формулировки")
                for p in clean:
                    out.append(f"{indent}  - «{p}»")
        if watch:
            _emit_section_heading(out, indent, "Табу")
            out.append(f"{indent}  {_v(watch)}")
        return

    if ntype == "trigger":
        if schema_version >= 2:
            cpe = data.get("client_phrase_examples")
            if isinstance(cpe, list) and cpe:
                _emit_section_heading(out, indent, "Что говорит или делает клиент (примеры)")
                for p in cpe:
                    ps = _v(str(p).strip())
                    if ps:
                        out.append(f"{indent}  - «{ps}»")
            when_rel = _str(data.get("when_relevant"))
            if when_rel:
                _emit_section_heading(out, indent, "Когда релевантно")
                out.append(f"{indent}  {_v(when_rel)}")
            kh = data.get("keyword_hints")
            if isinstance(kh, list) and kh:
                hints = ", ".join(str(x).strip() for x in kh if str(x).strip())
                if hints:
                    _emit_section_heading(out, indent, "Ключевые подсказки")
                    out.append(f"{indent}  {hints}")
            return
        if situation:
            _emit_section_heading(out, indent, "Сигнал / ситуация входа")
            out.append(f"{indent}  {_v(situation)}")
        if why:
            _emit_section_heading(out, indent, "Зачем запускать этот сценарий")
            out.append(f"{indent}  {_v(why)}")
        return


# ── Node renderer ─────────────────────────────────────────────────────────────

def _render_node(
    node: dict[str, Any],
    depth: int,
    via_label: str | None,
    edges: list[dict[str, Any]],
    nodes: dict[str, dict[str, Any]],
    visited: set[str],
    out: list[str],
    variables: dict[str, str] | None = None,
    profile_lookup: dict[str, str] | None = None,
    *,
    schema_version: int = 1,
) -> None:
    """Recursively render a node and all its children into `out`."""
    nid = str(node.get("id", ""))
    if nid in visited:
        return
    visited.add(nid)

    data = _node_data(node)
    indent = "  " * depth
    _vars = variables or {}

    def _v(text: str) -> str:
        """Apply variable substitution + lookup hint formatting to a text."""
        t = substitute_flow_variables(text, _vars)
        return highlight_lookup_hints(t)

    # Transition label from parent
    if via_label:
        out.append(f"\n{indent}→ Если {via_label}:")
        depth += 1
        indent = "  " * depth

    title = _node_title(node)
    ntype = _node_type(node)
    type_label = _NODE_TYPE_LABELS.get(ntype, ntype.capitalize())
    type_hint = _NODE_TYPE_HINTS.get(ntype, "")
    stage = _str(data.get("stage"))
    stage_label = _STAGE_LABELS.get(stage, stage) if stage else ""
    level = data.get("level")

    # Header line
    header_parts = [f"**{title}**"]
    if type_label and type_label != title:
        hint_suffix = f" — {type_hint}" if type_hint else ""
        header_parts.append(f"[{type_label}{hint_suffix}]")
    if stage_label:
        header_parts.append(f"· {stage_label}")
    if isinstance(level, int) and level > 1:
        header_parts.append(f"· Уровень {level}")
    out.append(f"\n{indent}{'—' * (3 - depth) if depth < 3 else '·'} {' '.join(header_parts)}")

    use_axis_layout = ntype in ("expertise", "question", "trigger")
    if use_axis_layout:
        _render_node_content_axes(
            ntype=ntype,
            data=data,
            indent=indent,
            _v=_v,
            out=out,
            schema_version=schema_version,
        )
    elif ntype == "business_rule":
        pk = profile_lookup or {}
        et_raw = _str(data.get("entity_type")).lower()
        eid_raw = _str(data.get("entity_id"))
        pkey = f"{et_raw}:{eid_raw}" if et_raw and eid_raw else ""
        prof = pk.get(pkey) if pkey else None
        _render_business_rule_content(
            data=data,
            indent=indent,
            _v=_v,
            out=out,
            profile_text=prof,
        )
    else:
        # Прежний плоский вывод для остальных типов
        if ntype == "goto":
            tf = _str(data.get("target_flow_id"))
            tn = _str(data.get("target_node_ref"))
            if tf:
                out.append(f"{indent}  **Целевой поток (id)**: `{tf}`")
            if tn:
                out.append(f"{indent}  **Целевая нода (id)**: `{tn}`")
            if schema_version >= 2:
                tp = _str(data.get("transition_phrase"))
                if tp:
                    _emit_section_heading(out, indent, "Фраза перехода")
                    out.append(f"{indent}  {_v(tp)}")
                ts = _str(data.get("trigger_situation"))
                if ts:
                    _emit_section_heading(out, indent, "Когда переходить")
                    out.append(f"{indent}  {_v(ts)}")
        situation = _str(data.get("situation"))
        if situation:
            out.append(f"{indent}  **Клиент говорит или делает**: {_v(situation)}")

        why = _str(data.get("why_it_works"))
        if why:
            out.append(f"{indent}  **Психология момента**: {_v(why)}")

        approach = _str(data.get("approach"))
        if approach:
            out.append(f"{indent}  **Тактика ответа**: {_v(approach)}")

        phrases = data.get("example_phrases")
        if isinstance(phrases, list) and phrases:
            clean = [_v(str(p).strip()) for p in phrases if str(p).strip()]
            if clean:
                out.append(f"{indent}  **Примеры фраз** (адаптируй под разговор):")
                for p in clean:
                    out.append(f"{indent}    - «{p}»")

        watch = _str(data.get("watch_out"))
        if watch:
            out.append(f"{indent}  **Не делай**: {_v(watch)}")

        comm_style = _str(data.get("communication_style"))
        if comm_style:
            out.append(f"{indent}  **Стиль общения**: {_v(comm_style)}")

        preferred = data.get("preferred_phrases")
        if isinstance(preferred, list) and preferred:
            clean_pref = [_v(str(p).strip()) for p in preferred if str(p).strip()]
            if clean_pref:
                out.append(f"{indent}  **Предпочтительные фразы**: {', '.join(f'«{p}»' for p in clean_pref)}")

        forbidden = data.get("forbidden_phrases")
        if isinstance(forbidden, list) and forbidden:
            clean_forb = [_v(str(p).strip()) for p in forbidden if str(p).strip()]
            if clean_forb:
                out.append(f"{indent}  **Запрещённые фразы**: {', '.join(f'«{p}»' for p in clean_forb)}")

        followup_q = _str(data.get("required_followup_question"))
        if followup_q:
            out.append(f"{indent}  **Обязательный вопрос после тактики**: «{_v(followup_q)}»")
        else:
            gq = _str(data.get("good_question"))
            if gq:
                out.append(f"{indent}  **Задай вопрос клиенту**: «{_v(gq)}»")

    # Outcome type for end nodes
    outcome_type = _str(data.get("outcome_type"))
    if outcome_type and ntype == "end":
        outcome_labels = {"success": "✅ Успех", "pending": "⏳ Отложено", "lost": "❌ Отказ"}
        out.append(f"{indent}  **Итог**: {outcome_labels.get(outcome_type, outcome_type)}")

    final_action = _str(data.get("final_action"))
    if final_action:
        out.append(f"{indent}  **Финальное действие**: {final_action}")

    # Legacy content/body fields (for backward compat)
    if not use_axis_layout and ntype != "business_rule":
        situation = _str(data.get("situation"))
        approach = _str(data.get("approach"))
        if not situation and not approach:
            for key in ("content", "body", "text", "hint", "instruction"):
                v = _str(data.get(key))
                if v:
                    out.append(f"{indent}  {v}")
                    break

    # Recurse into children via edges
    out_edges = sorted(
        [e for e in edges if e.get("source") == nid],
        key=lambda e: str(e.get("id") or e.get("target") or ""),
    )

    # For condition nodes: show each branch clearly as a decision point,
    # using FlowBranch objects or legacy strings (or edge labels as fallback)
    if ntype == "condition":
        if schema_version >= 2:
            rh = _str(data.get("routing_hint"))
            if rh:
                _emit_section_heading(out, indent, "Логика развилки")
                out.append(f"{indent}  {_v(rh)}")
        handle_map = _condition_handle_map_from_data(data)

        for e in out_edges:
            target = e.get("target")
            if not isinstance(target, str) or target not in nodes:
                continue

            src_handle = e.get("sourceHandle") or e.get("source_handle") or ""
            # Prefer handle map → edge label → generic
            branch_label = (
                handle_map.get(src_handle)
                or _edge_label(e)
                or (_branch_label_fallback(src_handle) if src_handle else "")
                or "—"
            )
            out.append(f"\n{indent}  🔀 Если «{branch_label}»:")
            _render_node(
                nodes[target],
                depth=depth + 2,
                via_label=None,
                edges=edges,
                nodes=nodes,
                visited=visited,
                out=out,
                variables=_vars,
                profile_lookup=profile_lookup,
                schema_version=schema_version,
            )
        return  # condition node handles all its children above

    for edge in out_edges:
        target = edge.get("target")
        if not isinstance(target, str) or target not in nodes:
            continue
        label = _edge_label(edge) or None
        _render_node(
            nodes[target],
            depth=depth,
            via_label=label,
            edges=edges,
            nodes=nodes,
            visited=visited,
            out=out,
            variables=_vars,
            profile_lookup=profile_lookup,
            schema_version=schema_version,
        )


# ── Public API ────────────────────────────────────────────────────────────────

def compile_script_flow_to_text(
    *,
    name: str,
    flow_metadata: dict[str, Any],
    flow_definition: dict[str, Any],
    profile_lookup: dict[str, str] | None = None,
) -> str:
    """
    Compile a Vue Flow expert script into a structured natural-language document.

    The document is:
    1. Indexed in pgvector-ready node retrieval storage
    2. Injected into the LLM system prompt when a relevant situation is detected
    3. Human-readable so experts can verify the output
    """
    meta = flow_metadata or {}
    variables: dict[str, str] = meta.get("variables") or {}
    schema_ver = int(flow_definition.get("schema_version") or 1) if isinstance(flow_definition, dict) else 1
    out: list[str] = []

    # ── Document header ──────────────────────────────────────────────────────
    out.append(f"# Сценарий: {name}")

    # Emit variable legend so the LLM knows what was substituted / what to look up
    if variables:
        out.append("\n_Переменные потока:_")
        for k, binding in variables.items():
            resolved = _resolve_variable(k, binding)
            if isinstance(binding, dict) and binding.get("source_type") == "function":
                hint = (binding.get("argument_hint") or "").strip()
                instr = (binding.get("llm_instruction") or "").strip()
                fn_line = f"  `{{{{{k}}}}}` → [🔧 вызови функцию для: «{hint}»]"
                if instr:
                    fn_line += f"  _(инструкция: {instr})_"
                out.append(fn_line)
            elif resolved.startswith("[[поиск:"):
                query = resolved[len("[[поиск:"):-2].strip()
                out.append(f"  `{{{{{k}}}}}` → [⚡ найди в справочнике: «{query}»]")
            else:
                out.append(f"  `{{{{{k}}}}}` = {resolved}")

    # Context line: employee · service · stages
    ctx_parts: list[str] = []

    stages = meta.get("stages")
    if isinstance(stages, list) and stages:
        labels = [_STAGE_LABELS.get(s, s) for s in stages]
        ctx_parts.append("Этап: " + ", ".join(labels))

    # service_ids / employee_ids stored as UUIDs; if names are available use them,
    # otherwise just count them so the reader knows context exists
    for key, label in (("employee_ids", "Сотрудники"), ("service_ids", "Услуги")):
        ids = meta.get(key)
        if isinstance(ids, list) and ids:
            ctx_parts.append(f"{label}: {len(ids)} указано")

    if ctx_parts:
        out.append("Контекст: " + " · ".join(ctx_parts))

    # When relevant
    when = _str(meta.get("when_relevant"))
    if when:
        out.append(f"\nКогда применять: {when}")

    # Keyword hints
    hints = meta.get("keyword_hints")
    if isinstance(hints, list):
        clean = [str(h).strip() for h in hints if str(h).strip()]
        if clean:
            out.append(f"Ключевые слова: {', '.join(clean)}")

    # ── Graph traversal ──────────────────────────────────────────────────────
    nodes_raw = flow_definition.get("nodes") if isinstance(flow_definition, dict) else None
    edges_raw = flow_definition.get("edges") if isinstance(flow_definition, dict) else None

    nodes: dict[str, dict[str, Any]] = {}
    if isinstance(nodes_raw, list):
        for n in nodes_raw:
            if isinstance(n, dict) and "id" in n:
                nodes[str(n["id"])] = n

    edges: list[dict[str, Any]] = edges_raw if isinstance(edges_raw, list) else []

    entry_ids: list[str] = []
    targets = {str(e.get("target")) for e in edges if isinstance(e, dict) and e.get("target")}
    for nid, n in nodes.items():
        if nid not in targets:
            entry_ids.append(nid)

    if not entry_ids:
        entry_ids = list(nodes.keys())

    visited_root: set[str] = set()
    for root_id in entry_ids:
        if root_id not in nodes:
            continue
        _render_node(
            nodes[root_id],
            depth=0,
            via_label=None,
            edges=edges,
            nodes=nodes,
            visited=visited_root,
            out=out,
            variables=variables,
            profile_lookup=profile_lookup,
            schema_version=schema_ver,
        )

    # Отдельно включаем узлы бизнес-правил каталога, не достигнутые из входов (изолированные карточки)
    visited_all = set(visited_root)
    for nid, n in nodes.items():
        data = _node_data(n)
        if data.get("node_type") != "business_rule":
            continue
        if data.get("is_catalog_rule") is not True:
            continue
        if nid in visited_all:
            continue
        visited_iso: set[str] = set()
        _render_node(
            n,
            depth=0,
            via_label=None,
            edges=edges,
            nodes=nodes,
            visited=visited_iso,
            out=out,
            variables=variables,
            profile_lookup=profile_lookup,
            schema_version=schema_ver,
        )
        visited_all.update(visited_iso)

    return "\n".join(out).strip() + "\n"
