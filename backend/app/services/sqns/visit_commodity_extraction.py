"""
Извлечение ссылок на товары (commodity) из сырых payload SQNS для визитов и платежей.

Структура API между инсталляциями SQNS может отличаться; перечислены типичные ключи.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable

from app.services.sqns.sync_handlers.common import parse_decimal, parse_int


@dataclass(frozen=True)
class VisitCommodityRef:
    commodity_external_id: int | None
    title: str | None
    quantity: Decimal | None
    amount: Decimal | None


def _read_nested(payload: dict[str, Any] | None, paths: Iterable[tuple[str, ...]]) -> Any:
    if not isinstance(payload, dict):
        return None
    for path in paths:
        current: Any = payload
        for key in path:
            if not isinstance(current, dict) or key not in current:
                break
            current = current[key]
        else:
            if current not in (None, ""):
                return current
    return None


def _parse_title(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _commodity_id_from_item(item: dict[str, Any]) -> int | None:
    direct = parse_int(
        item.get("commodityId")
        or item.get("commodity_id")
        or item.get("productId")
        or item.get("product_id")
        or item.get("goodsId")
        or item.get("goods_id")
    )
    if direct is not None:
        return direct
    comm = item.get("commodity")
    if isinstance(comm, dict):
        nested = parse_int(comm.get("id"))
        if nested is not None:
            return nested
    type_l = str(item.get("type", "")).strip().lower()
    if type_l in {"commodity", "product", "good", "goods", "товар"}:
        return parse_int(item.get("id"))
    return None


def _title_from_item(item: dict[str, Any]) -> str | None:
    raw = (
        item.get("title")
        or item.get("name")
        or item.get("commodityName")
        or item.get("commodity_name")
        or item.get("productName")
        or item.get("product_name")
    )
    if raw is not None:
        return _parse_title(raw)
    comm = item.get("commodity")
    if isinstance(comm, dict):
        return _parse_title(comm.get("title") or comm.get("name"))
    return None


def _item_maybe_commodity(item: dict[str, Any]) -> bool:
    if _commodity_id_from_item(item) is not None:
        return True
    t = str(item.get("type", "")).strip().lower()
    if t in {"commodity", "product", "good", "goods", "товар", "productservice"}:
        return True
    if "commodity" in item or "commodityId" in item or "commodity_id" in item:
        return True
    return False


def _refs_from_item_dict(item: dict[str, Any]) -> VisitCommodityRef | None:
    cid = _commodity_id_from_item(item)
    title = _title_from_item(item)
    # In SQNS: "amount" is the quantity (units), "paySum" is the monetary amount.
    # Generic APIs may use different field names.
    qty = parse_decimal(
        item.get("amount")
        or item.get("quantity")
        or item.get("count")
        or item.get("qty")
        or item.get("amountCount")
    )
    amt = parse_decimal(
        item.get("paySum")
        or item.get("pay_sum")
        or item.get("sum")
        or item.get("total")
        or item.get("price")
        or item.get("cost")
    )
    if cid is None and not title:
        return None
    return VisitCommodityRef(
        commodity_external_id=cid,
        title=title,
        quantity=qty,
        amount=amt,
    )


def _collect_from_list(items: list[Any], *, strict_commodity: bool) -> list[VisitCommodityRef]:
    out: list[VisitCommodityRef] = []
    for raw_item in items:
        if not isinstance(raw_item, dict):
            continue
        if strict_commodity and not _item_maybe_commodity(raw_item):
            continue
        ref = _refs_from_item_dict(raw_item)
        if ref is not None:
            out.append(ref)
    return out


_LIST_PATHS_COMMODITY_NAMED: tuple[tuple[str, ...], ...] = (
    ("commodities",),
    ("visit", "commodities"),
    ("appointment", "commodities"),
    ("visit", "appointment", "commodities"),
    ("commodityItems",),
    ("commodity_items",),
    ("basket", "commodities"),
    ("sale", "commodities"),
    ("payment", "commodities"),
)

_LIST_PATHS_NESTED_ITEMS: tuple[tuple[str, ...], ...] = (
    ("basket", "items"),
    ("sale", "items"),
    ("payment", "items"),
    ("check", "items"),
    ("check", "lines"),
    ("receipt", "items"),
    ("positions",),
    ("paymentPositions",),
    ("payment_positions",),
    ("lines",),
)

_LIST_PATHS_TOP_LEVEL_LOOSE: tuple[tuple[str, ...], ...] = (
    ("items",),
    ("visit", "items"),
    ("appointment", "items"),
    ("products",),
    ("goods",),
)


def extract_commodity_refs_from_visit_payload(raw: dict[str, Any] | None) -> list[VisitCommodityRef]:
    if not isinstance(raw, dict):
        return []

    collected: list[VisitCommodityRef] = []

    direct_id = parse_int(
        _read_nested(
            raw,
            (
                ("commodityId",),
                ("commodity_id",),
                ("commodity", "id"),
                ("visit", "commodityId"),
                ("visit", "commodity_id"),
                ("visit", "commodity", "id"),
                ("appointment", "commodityId"),
                ("appointment", "commodity_id"),
                ("appointment", "commodity", "id"),
                ("productId",),
                ("product_id",),
            ),
        )
    )
    direct_title = _read_nested(
        raw,
        (
            ("commodityName",),
            ("commodity_name",),
            ("commodity", "title"),
            ("commodity", "name"),
            ("visit", "commodity", "title"),
            ("appointment", "commodity", "title"),
        ),
    )
    title = _parse_title(direct_title)
    if direct_id is not None or title:
        collected.append(
            VisitCommodityRef(
                commodity_external_id=direct_id,
                title=title,
                quantity=None,
                amount=None,
            )
        )

    for path in _LIST_PATHS_COMMODITY_NAMED:
        node = _read_nested(raw, (path,))
        if isinstance(node, list):
            collected.extend(_collect_from_list(node, strict_commodity=False))

    for path in _LIST_PATHS_NESTED_ITEMS:
        node = _read_nested(raw, (path,))
        if isinstance(node, list):
            collected.extend(_collect_from_list(node, strict_commodity=True))

    for path in _LIST_PATHS_TOP_LEVEL_LOOSE:
        node = _read_nested(raw, (path,))
        if isinstance(node, list):
            collected.extend(_collect_from_list(node, strict_commodity=True))

    dedup: list[VisitCommodityRef] = []
    seen: set[tuple[int | None, str]] = set()
    for ref in collected:
        key = (ref.commodity_external_id, (ref.title or "").strip().lower())
        if key in seen:
            continue
        if ref.commodity_external_id is None and not ref.title:
            continue
        seen.add(key)
        dedup.append(ref)
    return dedup


def extract_commodity_refs_from_payment_payload(raw: dict[str, Any] | None) -> list[VisitCommodityRef]:
    if not isinstance(raw, dict):
        return []
    refs = extract_commodity_refs_from_visit_payload(raw)
    nested = raw.get("payment")
    if isinstance(nested, dict):
        refs.extend(extract_commodity_refs_from_visit_payload(nested))
    data = raw.get("data")
    if isinstance(data, dict):
        refs.extend(extract_commodity_refs_from_visit_payload(data))

    dedup: list[VisitCommodityRef] = []
    seen: set[tuple[int | None, str]] = set()
    for ref in refs:
        key = (ref.commodity_external_id, (ref.title or "").strip().lower())
        if key in seen:
            continue
        if ref.commodity_external_id is None and not ref.title:
            continue
        seen.add(key)
        dedup.append(ref)
    return dedup
