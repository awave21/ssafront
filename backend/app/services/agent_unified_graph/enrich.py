"""Семантическое обогащение unified-графа.

Принцип: создаём только РЁБРА между уже существующими (структурными) узлами,
новых узлов не появляется. Используем детерминированный keyword/fuzzy match
по тексту описаний — без LLM-вызовов и без схемных миграций.

Будущая опция (не в этом модуле): сильнее сигналы через эмбеддинги.
Туда переносятся motive/concern/objection ↔ service связи через cosine.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable
from uuid import UUID

import structlog
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.agent_unified_graph_node import AgentUnifiedGraphNode
from app.db.models.agent_unified_graph_relation import AgentUnifiedGraphRelation

log = structlog.get_logger(__name__)

PROVENANCE = "semantic"

# Минимальная длина названия для разных типов целей.
# Категории короткие (Эпиляция, Ботокс) — понижаем порог; услуги длинные —
# оставляем повыше, чтобы не матчить однокоренные слова случайно.
MIN_LEN_DEFAULT = 7
MIN_LEN_BY_TYPE = {
    "service": 11,
    "category": 6,
    "expertise": 8,
}
# Стоп-слова: часто слишком общие, чтобы быть полезным сигналом.
STOP_TITLES = {
    "услуги", "консультация", "услуга", "приём", "процедура", "процедуры",
    "услуги главного врача", "услуги врача-косметолога",
}

# Медицинские коды вида "А14.01.013" в начале названия услуги — отрезаем перед матчингом.
MED_CODE_RE = re.compile(r"^[А-ЯA-Z]\d{2}\.\d{2}\.\d{2,3}\s*", re.IGNORECASE)
WORD_BOUNDARY_RE = re.compile(r"[^\wа-яА-ЯёЁ-]+")


@dataclass
class EnrichResult:
    relations: int
    by_relation_type: dict[str, int]


def _strip_med_code(s: str) -> str:
    return MED_CODE_RE.sub("", s).strip()


def _normalize_for_match(s: str) -> str:
    """Приводим к нижнему регистру, убираем спец-символы, схлопываем пробелы."""
    if not s:
        return ""
    s = WORD_BOUNDARY_RE.sub(" ", s.lower())
    return " ".join(s.split())


PREFIX_LEN = 6  # обрезка слова для устойчивости к падежным окончаниям (рус.)
TOKEN_MIN_LEN = 5  # короче — служебные/общие слова, не сигнал
STOP_TOKENS = {
    "услуг", "врача", "клини", "консу", "проце", "форма", "очищ", "обыч",
    "запис", "паци", "клиен", "методи", "часто",
}


def _significant_tokens(s: str) -> list[str]:
    """Делим строку на токены, оставляем длинные (>=TOKEN_MIN_LEN), обрезаем до PREFIX_LEN.

    Это устойчиво к падежным/числовым формам в русском: «контурная»→«контур»,
    «контурной»→«контур», «пластика»→«пласти», «пластике»→«пласти».
    """
    if not s:
        return []
    norm = _normalize_for_match(s)
    out: list[str] = []
    for w in norm.split():
        if len(w) < TOKEN_MIN_LEN:
            continue
        prefix = w[:PREFIX_LEN]
        if prefix in STOP_TOKENS:
            continue
        out.append(prefix)
    return out


def _phrase_in_text(needle: str, haystack: str, *, min_len: int = MIN_LEN_DEFAULT) -> bool:
    """Совпадение по «корневым» токенам.

    Берём значимые токены из needle (обрезка PREFIX_LEN), и считаем, что
    совпадение есть, если ≥1 (для коротких targets) или ≥2/N (для длинных)
    токенов встречаются в haystack-токенах.
    """
    if not needle or not haystack:
        return False
    n_norm = _normalize_for_match(needle)
    if len(n_norm) < min_len:
        return False
    if n_norm in STOP_TITLES:
        return False
    needle_tokens = _significant_tokens(needle)
    if not needle_tokens:
        return False
    haystack_tokens = set(_significant_tokens(haystack))
    if not haystack_tokens:
        return False
    matched = sum(1 for t in needle_tokens if t in haystack_tokens)
    if not matched:
        return False
    # Порог: 1 токен достаточно для коротких целей (≤2 значимых слов),
    # для длинных — хотя бы половина значимых слов.
    if len(needle_tokens) <= 2:
        return matched >= 1
    return matched / len(needle_tokens) >= 0.5


def _index_nodes(rows: list[AgentUnifiedGraphNode]) -> dict[str, list[AgentUnifiedGraphNode]]:
    by_type: dict[str, list[AgentUnifiedGraphNode]] = {}
    for n in rows:
        by_type.setdefault(n.entity_type, []).append(n)
    return by_type


def _match_text_against(
    text: str,
    targets: Iterable[AgentUnifiedGraphNode],
    *,
    title_transform=lambda t: t,
) -> list[AgentUnifiedGraphNode]:
    """Возвращает узлы, чьи title встречаются в text."""
    if not text:
        return []
    matched: list[AgentUnifiedGraphNode] = []
    seen: set[str] = set()
    for t in targets:
        if t.graph_node_id in seen:
            continue
        title = title_transform(t.title or "")
        min_len = MIN_LEN_BY_TYPE.get(t.entity_type, MIN_LEN_DEFAULT)
        if _phrase_in_text(title, text, min_len=min_len):
            matched.append(t)
            seen.add(t.graph_node_id)
    return matched


# --- Источники сигналов ---

def _enrich_specialist_to_services(
    by_type: dict[str, list[AgentUnifiedGraphNode]],
) -> list[dict]:
    """specialist.information упоминает услугу → ребро 'упоминает услугу'."""
    edges = []
    services = by_type.get("service", [])
    for spec in by_type.get("specialist", []):
        text = spec.description or ""
        if not text:
            continue
        for srv in _match_text_against(text, services, title_transform=_strip_med_code):
            edges.append({
                "source_graph_node_id": spec.graph_node_id,
                "target_graph_node_id": srv.graph_node_id,
                "relation_type": "проводит услугу",
                "weight": 0.7,
                "origin_slice": "sqns",
            })
    return edges


def _enrich_specialist_to_categories(
    by_type: dict[str, list[AgentUnifiedGraphNode]],
) -> list[dict]:
    edges = []
    categories = by_type.get("category", [])
    for spec in by_type.get("specialist", []):
        text = spec.description or ""
        if not text:
            continue
        for cat in _match_text_against(text, categories):
            edges.append({
                "source_graph_node_id": spec.graph_node_id,
                "target_graph_node_id": cat.graph_node_id,
                "relation_type": "эксперт в",
                "weight": 0.8,
                "origin_slice": "sqns",
            })
    return edges


def _enrich_specialist_to_expertise(
    by_type: dict[str, list[AgentUnifiedGraphNode]],
) -> list[dict]:
    """specialist.information упоминает экспертизу из script-flow."""
    edges = []
    expertise_nodes = by_type.get("expertise", [])
    for spec in by_type.get("specialist", []):
        text = spec.description or ""
        if not text:
            continue
        for exp in _match_text_against(text, expertise_nodes):
            edges.append({
                "source_graph_node_id": spec.graph_node_id,
                "target_graph_node_id": exp.graph_node_id,
                "relation_type": "владеет",
                "weight": 0.75,
                "origin_slice": "sqns",
            })
    return edges


def _enrich_question_to_services(
    by_type: dict[str, list[AgentUnifiedGraphNode]],
) -> list[dict]:
    """Q&A title/content упоминает услугу или категорию."""
    edges = []
    services = by_type.get("service", [])
    categories = by_type.get("category", [])
    for q in by_type.get("question", []):
        text = " ".join(filter(None, [q.title or "", q.description or ""]))
        if not text:
            continue
        for srv in _match_text_against(text, services, title_transform=_strip_med_code):
            edges.append({
                "source_graph_node_id": q.graph_node_id,
                "target_graph_node_id": srv.graph_node_id,
                "relation_type": "о услуге",
                "weight": 0.65,
                "origin_slice": "knowledge",
            })
        for cat in _match_text_against(text, categories):
            edges.append({
                "source_graph_node_id": q.graph_node_id,
                "target_graph_node_id": cat.graph_node_id,
                "relation_type": "о категории",
                "weight": 0.7,
                "origin_slice": "knowledge",
            })
    return edges


def _enrich_motive_to_services(
    by_type: dict[str, list[AgentUnifiedGraphNode]],
) -> list[dict]:
    """Мотив/возражение/сомнение упоминает услугу или категорию по тексту."""
    edges = []
    services = by_type.get("service", [])
    categories = by_type.get("category", [])
    sources = (
        by_type.get("motive", [])
        + by_type.get("objection", [])
        + by_type.get("concern", [])
    )
    for src in sources:
        text = " ".join(filter(None, [src.title or "", src.description or ""]))
        if not text:
            continue
        for srv in _match_text_against(text, services, title_transform=_strip_med_code):
            edges.append({
                "source_graph_node_id": src.graph_node_id,
                "target_graph_node_id": srv.graph_node_id,
                "relation_type": f"{src.entity_type} → услуга",
                "weight": 0.55,
                "origin_slice": "script_bridge",
            })
        for cat in _match_text_against(text, categories):
            edges.append({
                "source_graph_node_id": src.graph_node_id,
                "target_graph_node_id": cat.graph_node_id,
                "relation_type": f"{src.entity_type} → категория",
                "weight": 0.6,
                "origin_slice": "script_bridge",
            })
    return edges


def _dedupe(edges: list[dict]) -> list[dict]:
    seen: set[tuple[str, str, str]] = set()
    result: list[dict] = []
    for e in edges:
        key = (e["source_graph_node_id"], e["target_graph_node_id"], e["relation_type"])
        if key in seen:
            continue
        seen.add(key)
        result.append(e)
    return result


# --- Основная функция ---

def _cosine(a: list[float], b: list[float]) -> float:
    """Косинусное сходство двух векторов одинаковой длины."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / ((na ** 0.5) * (nb ** 0.5))


# Пороги cosine для разных пар «источник→цель». Подобраны под text-embedding-3-small;
# при необходимости можно вынести в settings.
COSINE_THRESHOLDS: dict[tuple[str, str], tuple[float, str]] = {
    ("specialist", "service"): (0.46, "может выполнять"),
    ("specialist", "category"): (0.42, "работает в"),
    ("specialist", "expertise"): (0.45, "связан с"),
    ("question", "service"): (0.42, "о услуге"),
    ("question", "category"): (0.40, "о категории"),
    ("motive", "service"): (0.40, "мотив → услуга"),
    ("motive", "category"): (0.40, "мотив → категория"),
    ("objection", "service"): (0.40, "objection → услуга"),
    ("objection", "category"): (0.40, "objection → категория"),
    ("concern", "service"): (0.40, "concern → услуга"),
    ("concern", "category"): (0.40, "concern → категория"),
}
# Сколько TOP-N целей оставлять по cosine, чтобы не плодить рёбра с каждым.
COSINE_TOP_N = 5


def _cosine_match_pairs(
    sources: list[AgentUnifiedGraphNode],
    targets: list[AgentUnifiedGraphNode],
    *,
    threshold: float,
    top_n: int = COSINE_TOP_N,
) -> list[tuple[AgentUnifiedGraphNode, AgentUnifiedGraphNode, float]]:
    """Возвращает пары (source, target, score) с наибольшим cosine выше порога."""
    out: list[tuple[AgentUnifiedGraphNode, AgentUnifiedGraphNode, float]] = []
    for src in sources:
        if src.embedding is None:
            continue
        scored: list[tuple[AgentUnifiedGraphNode, float]] = []
        for tgt in targets:
            if tgt.embedding is None or tgt.graph_node_id == src.graph_node_id:
                continue
            score = _cosine(list(src.embedding), list(tgt.embedding))
            if score >= threshold:
                scored.append((tgt, score))
        scored.sort(key=lambda x: -x[1])
        for tgt, score in scored[:top_n]:
            out.append((src, tgt, score))
    return out


def _enrich_via_cosine(
    by_type: dict[str, list[AgentUnifiedGraphNode]],
) -> list[dict]:
    """Семантические рёбра по cosine эмбеддингов между узлами разных типов."""
    edges: list[dict] = []
    for (src_type, tgt_type), (threshold, rel) in COSINE_THRESHOLDS.items():
        sources = by_type.get(src_type, [])
        targets = by_type.get(tgt_type, [])
        if not sources or not targets:
            continue
        for src, tgt, score in _cosine_match_pairs(sources, targets, threshold=threshold):
            edges.append({
                "source_graph_node_id": src.graph_node_id,
                "target_graph_node_id": tgt.graph_node_id,
                "relation_type": rel,
                "weight": round(score, 3),
                "origin_slice": src.origin_slice,
            })
    return edges


async def enrich_semantic_relations(
    db: AsyncSession,
    *,
    tenant_id: UUID,
    agent_id: UUID,
) -> EnrichResult:
    log.info("unified_graph.enrich.start", agent_id=str(agent_id))

    nodes = (
        await db.execute(
            select(AgentUnifiedGraphNode).where(AgentUnifiedGraphNode.agent_id == agent_id)
        )
    ).scalars().all()
    by_type = _index_nodes(nodes)

    edges: list[dict] = []
    # Слой A — keyword/prefix-match (мгновенно, без LLM).
    edges += _enrich_specialist_to_services(by_type)
    edges += _enrich_specialist_to_categories(by_type)
    edges += _enrich_specialist_to_expertise(by_type)
    edges += _enrich_question_to_services(by_type)
    edges += _enrich_motive_to_services(by_type)
    # Слой B — cosine по эмбеддингам (если эмбеддинги есть; иначе тихо пропустит).
    edges += _enrich_via_cosine(by_type)
    edges = _dedupe(edges)

    by_rel: dict[str, int] = {}
    for e in edges:
        by_rel[e["relation_type"]] = by_rel.get(e["relation_type"], 0) + 1

    # Полная замена семантического слоя — структурный не трогаем.
    await db.execute(
        delete(AgentUnifiedGraphRelation).where(
            AgentUnifiedGraphRelation.agent_id == agent_id,
            AgentUnifiedGraphRelation.provenance_tier == PROVENANCE,
        )
    )
    if edges:
        await db.execute(
            pg_insert(AgentUnifiedGraphRelation).values([
                {
                    "tenant_id": tenant_id,
                    "agent_id": agent_id,
                    "origin_slice": e["origin_slice"],
                    "source_graph_node_id": e["source_graph_node_id"],
                    "target_graph_node_id": e["target_graph_node_id"],
                    "relation_type": e["relation_type"][:80],
                    "weight": float(e.get("weight", 0.5)),
                    "properties": {},
                    "provenance_tier": PROVENANCE,
                }
                for e in edges
            ])
        )
    await db.commit()

    log.info(
        "unified_graph.enrich.done",
        agent_id=str(agent_id),
        relations=len(edges),
        by_relation_type=by_rel,
    )
    return EnrichResult(relations=len(edges), by_relation_type=by_rel)
