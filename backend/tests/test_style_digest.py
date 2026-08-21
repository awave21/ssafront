"""Тесты стиль-слоя: render_style_digest — выжимка «голоса эксперта» из skill_doc."""

from app.services.runtime.skill_layer import (
    STYLE_DIGEST_MAX_CHARS,
    render_style_digest,
)


def _doc(objections=None, endings=None):
    return {"objections": objections or [], "endings": endings or []}


def _obj(trigger="клиент говорит «дорого»", phrases=None, forbidden=None):
    return {
        "trigger_when": trigger,
        "phrases": phrases or [],
        "forbidden": forbidden or [],
    }


def test_empty_docs_returns_none():
    assert render_style_digest([]) is None
    assert render_style_digest([("Навык", _doc())]) is None


def test_levels_route_to_sections():
    doc = _doc(
        objections=[
            _obj(phrases=[
                {"text": "Обязательная фраза", "level": "обязательно"},
                {"text": "Дословная фраза", "level": "дословно"},
                {"text": "Примерная фраза", "level": "пример"},
            ])
        ]
    )
    out = render_style_digest([("Навык", doc)])
    assert out is not None
    must_pos = out.find("Обязательные формулировки")
    verbatim_pos = out.find("Фирменные фразы")
    example_pos = out.find("Образцы интонации")
    assert -1 not in (must_pos, verbatim_pos, example_pos)
    # приоритет секций: обязательные → дословные → образцы
    assert must_pos < verbatim_pos < example_pos
    assert "«Обязательная фраза»" in out
    assert "«Дословная фраза»" in out
    assert "«Примерная фраза»" in out


def test_forbidden_comes_right_after_musts():
    doc = _doc(objections=[_obj(
        phrases=[
            {"text": "Обязательная", "level": "обязательно"},
            {"text": "Дословная", "level": "дословно"},
        ],
        forbidden=["как скажете"],
    )])
    out = render_style_digest([("Навык", doc)])
    assert out.find("Обязательные формулировки") < out.find("Запрещено") < out.find("Фирменные фразы")


def test_phrases_deduplicated_across_docs():
    phrase = {"text": "Одна и та же фраза", "level": "дословно"}
    docs = [
        ("Навык 1", _doc(objections=[_obj(phrases=[dict(phrase)])])),
        ("Навык 2", _doc(objections=[_obj(phrases=[dict(phrase)])])),
    ]
    out = render_style_digest(docs)
    assert out is not None
    assert out.count("Одна и та же фраза") == 1


def test_examples_capped():
    phrases = [
        {"text": f"Пример номер {i}", "level": "пример"} for i in range(20)
    ]
    out = render_style_digest([("Навык", _doc(objections=[_obj(phrases=phrases)]))])
    assert out is not None
    assert out.count("Пример номер") == 8


def test_budget_respected_and_musts_prioritized():
    long_tail = "х" * 400
    objections = [
        _obj(
            trigger=f"ситуация {i}",
            phrases=[{"text": f"Длинная фраза {i} {long_tail}", "level": "пример"}],
        )
        for i in range(30)
    ]
    objections.append(
        _obj(trigger="страх боли", phrases=[{"text": "Обязательная короткая", "level": "обязательно"}])
    )
    out = render_style_digest([("Навык", _doc(objections=objections))])
    assert out is not None
    # бюджет: небольшой допуск на заголовок секции, но не бесконечность
    assert len(out) <= STYLE_DIGEST_MAX_CHARS + 200
    # обязательная фраза пережила бюджет, хвост примеров — нет
    assert "Обязательная короткая" in out


def test_trigger_prefix_and_absence():
    doc = _doc(objections=[
        _obj(trigger="клиент сомневается", phrases=[{"text": "С триггером", "level": "дословно"}]),
        _obj(trigger="", phrases=[{"text": "Без триггера", "level": "дословно"}]),
    ])
    out = render_style_digest([("Навык", doc)])
    assert "— клиент сомневается: «С триггером»" in out
    assert "— «Без триггера»" in out


def test_forbidden_present_endings_excluded():
    doc = _doc(
        objections=[_obj(
            phrases=[{"text": "Фраза", "level": "дословно"}],
            forbidden=["гарантируем результат", "канцелярит"],
        )],
        endings=["Администратор зафиксировал дату и время"],
    )
    out = render_style_digest([("Навык", doc)])
    assert "Запрещено (никогда не пиши):" in out
    assert "— гарантируем результат" in out
    # endings — протокольные описания, в стилевой блок не попадают
    assert "Администратор зафиксировал" not in out


def test_header_keeps_facts_boundary():
    doc = _doc(objections=[_obj(phrases=[{"text": "Фраза", "level": "пример"}])])
    out = render_style_digest([("Навык", doc)])
    assert "только из инструментов" in out
