"""
script_flow_compiler.py

Converts a Vue Flow graph (expert script) into a structured natural-language
document that an LLM can read as expert guidance.

Секции «осей» (ситуация → мотив → аргументы → вопросы) заданы явными
заголовками для expertise / question / trigger, чтобы чанкинг в LightRAG
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


def _resolve_variable(key: str, binding: Any) -> str:
    """
    Resolve a single variable binding to its substitution string.

    binding can be:
      - str → treated as a static literal (backward compat)
      - {"source_type": "static",  "value": "..."}   → literal substitution
      - {"source_type": "search",  "search_query": "..."} → [[поиск: query]]
        (the LLM will resolve this using its directory search tools at runtime)
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


def highlight_lookup_hints(text: str) -> str:
    """
    Wrap [[поиск: X]] hints so the LLM clearly understands these are
    dynamic placeholders to resolve via directory search.
    """
    def _wrap(m: re.Match) -> str:
        query = m.group(1).strip()
        return f"[⚡ найди в справочнике: «{query}»]"

    return _LOOKUP_PATTERN.sub(_wrap, text)


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
    """Явная метка секции для лучшего разбиения текста при индексации (LightRAG)."""
    out.append(f"{indent}  ▸ **{title}**")


def _render_node_content_axes(
    *,
    ntype: str,
    data: dict[str, Any],
    indent: str,
    _v: Callable[[str], str],
    out: list[str],
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
        if watch:
            _emit_section_heading(out, indent, "Табу (не делай)")
            out.append(f"{indent}  {_v(watch)}")
        if question:
            _emit_section_heading(out, indent, "Уточняющий вопрос")
            out.append(f"{indent}  «{_v(question)}»")
        return

    if ntype == "question":
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
        _render_node_content_axes(ntype=ntype, data=data, indent=indent, _v=_v, out=out)
    else:
        # Прежний плоский вывод для остальных типов
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
    if not use_axis_layout:
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
    # using the conditions array (or edge labels as fallback)
    if ntype == "condition":
        conditions_list = data.get("conditions")
        cond_array: list[str] = conditions_list if isinstance(conditions_list, list) else []

        # Build handle → label mapping from the node's conditions
        handle_map: dict[str, str] = {}
        for i, c in enumerate(cond_array):
            handle_map[f"cond-{i}"] = str(c).strip()
        handle_map["cond-default"] = "по умолчанию"

        for e in out_edges:
            target = e.get("target")
            if not isinstance(target, str) or target not in nodes:
                continue

            src_handle = e.get("sourceHandle") or e.get("source_handle") or ""
            # Prefer handle map → edge label → generic
            branch_label = (
                handle_map.get(src_handle)
                or _edge_label(e)
                or src_handle.replace("cond-", "ветка ")
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
        )


# ── Public API ────────────────────────────────────────────────────────────────

def compile_script_flow_to_text(
    *,
    name: str,
    flow_metadata: dict[str, Any],
    flow_definition: dict[str, Any],
) -> str:
    """
    Compile a Vue Flow expert script into a structured natural-language document.

    The document is:
    1. Indexed in LightRAG / pgvector for semantic search
    2. Injected into the LLM system prompt when a relevant situation is detected
    3. Human-readable so experts can verify the output
    """
    meta = flow_metadata or {}
    variables: dict[str, str] = meta.get("variables") or {}
    out: list[str] = []

    # ── Document header ──────────────────────────────────────────────────────
    out.append(f"# Сценарий: {name}")

    # Emit variable legend so the LLM knows what was substituted / what to look up
    if variables:
        out.append("\n_Переменные потока:_")
        for k, binding in variables.items():
            resolved = _resolve_variable(k, binding)
            if resolved.startswith("[[поиск:"):
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
        )

    return "\n".join(out).strip() + "\n"
