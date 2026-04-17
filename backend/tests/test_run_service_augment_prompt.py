from __future__ import annotations

from app.services.run_service import _normalize_augment_prompt_blocks


def test_normalize_augment_prompt_dedupes_and_drops_empty() -> None:
    blocks, meta = _normalize_augment_prompt_blocks(
        ["  ", "Первый", "Первый", "Второй"],
        max_blocks=5,
        max_chars=100,
    )

    assert blocks == ["Первый", "Второй"]
    assert meta["dropped_empty"] == 1
    assert meta["dropped_duplicates"] == 1
    assert meta["dropped_overflow"] == 0
    assert meta["truncated_last_block"] is False


def test_normalize_augment_prompt_caps_block_count() -> None:
    blocks, meta = _normalize_augment_prompt_blocks(
        ["A", "B", "C"],
        max_blocks=2,
        max_chars=100,
    )

    assert blocks == ["A", "B"]
    assert meta["dropped_overflow"] == 1


def test_normalize_augment_prompt_truncates_to_char_budget() -> None:
    blocks, meta = _normalize_augment_prompt_blocks(
        ["12345", "67890"],
        max_blocks=5,
        max_chars=7,
    )

    assert blocks == ["12345", "67"]
    assert meta["truncated_last_block"] is True
    assert meta["kept_chars"] == 7
