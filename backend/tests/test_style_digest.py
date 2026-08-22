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


def test_forbidden_go_first_and_are_capped():
    """Запреты короткие, универсальные и несут комплаенс — идут первой секцией
    с потолком, чтобы длинные фразы услуги их не вытесняли (проверено на живых
    данных: без потолка 99 строк запретов оставляли 3 строки фраз)."""
    doc = _doc(objections=[_obj(
        phrases=[
            {"text": "Обязательная", "level": "обязательно"},
            {"text": "Дословная", "level": "дословно"},
        ],
        forbidden=[f"запрет {i}" for i in range(40)],
    )])
    out = render_style_digest([("Навык", doc)])
    assert out.find("Запрещено") < out.find("Обязательные формулировки") < out.find("Фирменные фразы")
    assert sum(1 for i in range(40) if f"запрет {i}" in out) == 20


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


# ── Разделение по услугам: фразы «не про эту услугу» не должны вытеснять нужные ──


def _skill(name, musts=(), examples=(), forbidden=()):
    phrases = [{"text": t, "level": "обязательно"} for t in musts]
    phrases += [{"text": t, "level": "пример"} for t in examples]
    return (name, _doc(objections=[_obj(trigger=f"тема {name}", phrases=phrases, forbidden=list(forbidden))]))


def test_single_skill_has_no_scope_prefix():
    out = render_style_digest([_skill("Мезотерапия", musts=["Фраза"])])
    assert "[Мезотерапия]" not in out
    assert "«Фраза»" in out


def test_multiple_skills_get_scope_prefix():
    docs = [_skill("Мезотерапия", musts=["Фраза М"]), _skill("Ботулотоксин", musts=["Фраза Б"])]
    out = render_style_digest(docs)
    assert "[Мезотерапия]" in out
    assert "[Ботулотоксин]" in out
    assert "тема, к которой относится фраза" in out


def test_active_skill_comes_first_and_is_announced():
    docs = [_skill("Мезотерапия", musts=["Фраза М"]), _skill("Ботулотоксин", musts=["Фраза Б"])]
    out = render_style_digest(docs, active_skill_names={"Ботулотоксин"})
    assert "Сейчас разговор про: Ботулотоксин." in out
    assert out.find("Фраза Б") < out.find("Фраза М")


def test_inactive_skills_are_trimmed():
    many = [f"Обязательная {i}" for i in range(10)]
    docs = [
        _skill("Активный", musts=["Активная фраза"]),
        _skill("Прочий", musts=many),
    ]
    out = render_style_digest(docs, active_skill_names={"Активный"})
    kept = sum(1 for m in many if m in out)
    assert kept == 3, f"у неактивного навыка должно остаться 3 фразы, осталось {kept}"
    assert "Активная фраза" in out


def test_forbidden_stay_global_across_skills():
    docs = [
        _skill("Активный", musts=["Ф"], forbidden=["запрет активного"]),
        _skill("Прочий", musts=["Ф2"], forbidden=["запрет прочего"]),
    ]
    out = render_style_digest(docs, active_skill_names={"Активный"})
    assert "запрет активного" in out
    assert "запрет прочего" in out, "запреты тона не привязаны к услуге — нужны всегда"


def test_examples_only_from_active_skill():
    docs = [
        _skill("Активный", musts=["Ф"], examples=["образец активного"]),
        _skill("Прочий", musts=["Ф2"], examples=["образец прочего"]),
    ]
    out = render_style_digest(docs, active_skill_names={"Активный"})
    assert "образец активного" in out
    assert "образец прочего" not in out


def test_examples_fallback_when_no_active_skill():
    docs = [
        _skill("Первый", musts=["Ф"], examples=["образец первого"]),
        _skill("Второй", musts=["Ф2"], examples=["образец второго"]),
    ]
    out = render_style_digest(docs)
    assert "образец первого" in out, "без определённой услуги тон задаёт первый навык"
