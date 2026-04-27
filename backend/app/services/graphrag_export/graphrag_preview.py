"""Чтение превью Microsoft GraphRAG из ``output/*.parquet`` локального workspace."""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any
from uuid import UUID

import structlog

from app.db.models.agent import Agent

logger = structlog.get_logger(__name__)

_ENTITY_FILES = ("entities.parquet", "create_final_entities.parquet")
_REL_FILES = ("relationships.parquet", "create_final_relationships.parquet")
_MAX_NODES = 800
_MAX_EDGES = 2000


def _slug_dir(agent: Agent) -> str:
    raw = (getattr(agent, "microsoft_graphrag_workspace_slug", None) or "").strip()
    if not raw:
        return str(agent.id)
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", raw).strip("._-") or str(agent.id)
    return safe[:120]


def agent_graphrag_workspace(settings: Any, *, tenant_id: UUID, agent: Agent) -> Path | None:
    root = (getattr(settings, "microsoft_graphrag_workspace_root", None) or "").strip()
    if not root:
        return None
    return Path(root) / str(tenant_id) / _slug_dir(agent)


def _first_existing(base: Path, names: tuple[str, ...]) -> Path | None:
    for n in names:
        p = base / n
        if p.is_file():
            return p
    return None


def _pick_col(df_cols: list[str], candidates: tuple[str, ...]) -> str | None:
    lower = {c.lower(): c for c in df_cols}
    for cand in candidates:
        if cand in df_cols:
            return cand
        lc = cand.lower()
        if lc in lower:
            return lower[lc]
    return None


def _cell_str(row: Any, col: str | None) -> str:
    if not col or col not in row.index:
        return ""
    v = row.get(col)
    if v is None:
        return ""
    s = str(v).strip()
    return s


def load_graphrag_preview_from_workspace(ws: Path) -> dict[str, Any]:
    """
    Возвращает словарь в формате, ожидаемом UI графа знаний:
    ``nodes`` (id/label/type/description), ``relations``, счётчики и мета.
    """
    out_dir = ws / "output"
    if not out_dir.is_dir():
        return {
            "nodes": [],
            "relations": [],
            "node_count": 0,
            "edge_count": 0,
            "truncated": False,
            "preview_source": "no_output",
            "preview_error": None,
            "message": "Каталог output/ не найден. Сначала выполните graphrag index.",
            "preview_legend": None,
        }

    try:
        import pandas as pd
    except ImportError:
        logger.warning("graphrag_preview_pandas_missing")
        return {
            "nodes": [],
            "relations": [],
            "node_count": 0,
            "edge_count": 0,
            "truncated": False,
            "preview_source": "pandas_missing",
            "preview_error": "Для чтения parquet установите pandas/pyarrow в окружении API.",
            "message": None,
            "preview_legend": None,
        }

    ent_path = _first_existing(out_dir, _ENTITY_FILES)
    rel_path = _first_existing(out_dir, _REL_FILES)

    nodes_out: list[dict[str, str]] = []
    rels_out: list[dict[str, str]] = []
    # Связи в GraphRAG parquet часто ссылаются на human_readable_id / title, а не на uuid в колонке id.
    alias_to_canonical: dict[str, str] = {}

    node_total = 0
    edge_total = 0
    truncated = False

    if ent_path is not None:
        try:
            df = pd.read_parquet(ent_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("graphrag_preview_entities_read_failed", path=str(ent_path), error=str(exc))
            return {
                "nodes": [],
                "relations": [],
                "node_count": 0,
                "edge_count": 0,
                "truncated": False,
                "preview_source": "workspace_parquet",
                "preview_error": f"Не удалось прочитать {ent_path.name}: {exc}",
                "message": None,
                "preview_legend": None,
            }

        cols = list(df.columns)
        id_c = _pick_col(cols, ("id", "human_readable_id", "name", "title"))
        hr_c = _pick_col(cols, ("human_readable_id", "readable_id", "entity_name"))
        title_c = _pick_col(cols, ("title", "name", "human_readable_id", "id"))
        name_c = _pick_col(cols, ("name", "entity_name"))
        type_c = _pick_col(cols, ("type", "entity_type", "entity"))
        desc_c = _pick_col(cols, ("description", "text", "desc"))

        node_total = len(df)
        view = df.head(_MAX_NODES)
        if node_total > _MAX_NODES:
            truncated = True

        for _, row in view.iterrows():
            id_val = _cell_str(row, id_c)
            hr_val = _cell_str(row, hr_c) if hr_c else ""
            title_val = _cell_str(row, title_c)
            name_val = _cell_str(row, name_c) if name_c and name_c != title_c else ""
            # Один ключ для узла в API/UI — тот же namespace, что у рёбер в relationships.parquet.
            rid = hr_val or id_val or str(uuid.uuid4())
            label = (title_val or name_val or hr_val or rid)[:500]
            ntype = str(row[type_c]) if type_c and type_c in row.index and row[type_c] is not None else "entity"
            desc = ""
            if desc_c and desc_c in row.index and row[desc_c] is not None:
                desc = str(row[desc_c])
            nodes_out.append(
                {
                    "id": rid,
                    "label": label[:500],
                    "type": ntype[:120],
                    "description": desc[:4000],
                }
            )
            for alias in (id_val, hr_val, title_val, name_val):
                if alias:
                    alias_to_canonical.setdefault(alias, rid)

    node_ids = {n["id"] for n in nodes_out}

    if rel_path is not None:
        try:
            rdf = pd.read_parquet(rel_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("graphrag_preview_rel_read_failed", path=str(rel_path), error=str(exc))
        else:
            cols = list(rdf.columns)
            s_c = _pick_col(cols, ("source", "subject", "source_id", "src_id"))
            t_c = _pick_col(cols, ("target", "object", "target_id", "tgt_id"))
            lbl_c = _pick_col(cols, ("label", "type", "relationship", "description"))
            edge_total = len(rdf)
            rv = rdf.head(_MAX_EDGES)
            if edge_total > _MAX_EDGES:
                truncated = True
            idx = 0
            for _, row in rv.iterrows():
                if not s_c or not t_c:
                    break
                s = row.get(s_c)
                t = row.get(t_c)
                if s is None or t is None:
                    continue
                sk = str(s).strip()
                tk = str(t).strip()
                if not sk or not tk:
                    continue
                src_id = alias_to_canonical.get(sk, sk) if sk not in node_ids else sk
                tgt_id = alias_to_canonical.get(tk, tk) if tk not in node_ids else tk
                if src_id not in node_ids or tgt_id not in node_ids:
                    continue
                lbl = str(row[lbl_c]) if lbl_c and lbl_c in row.index and row[lbl_c] is not None else "связь"
                rels_out.append(
                    {
                        "id": f"rel-{idx}",
                        "source": src_id,
                        "target": tgt_id,
                        "label": lbl[:200],
                    }
                )
                idx += 1

    return {
        "nodes": nodes_out,
        "relations": rels_out,
        "node_count": node_total,
        "edge_count": edge_total,
        "truncated": truncated,
        "preview_source": "workspace_parquet",
        "preview_error": None,
        "message": None,
        "preview_legend": "Parquet в output/.",
    }
