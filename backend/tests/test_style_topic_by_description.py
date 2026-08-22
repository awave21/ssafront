"""Тема разговора определяется по тексту навыка, без идентификаторов.

Навык описывает себя сам: имя, контекст и триггеры (реальные формулировки
клиентов). Их и сопоставляем с сообщением — механизм не знает ни про услуги,
ни про инструменты, ни про сферу бизнеса.
"""

from app.services.runtime.skill_layer import (
    find_active_skills_by_message,
    score_skill_match,
)


def _doc(context="", triggers=()):
    return {
        "context": context,
        "objections": [{"trigger_when": t, "phrases": []} for t in triggers],
    }


BIO = ("Биоревитализация", _doc(
    context="Навык по приёму обращений про биоревитализацию, помощь с выбором вида.",
    triggers=["Клиент спрашивает про биоревитализацию: «У вас есть биоревитализация?»"],
))
BOTOX = ("Ботулотоксин", _doc(
    context="Навык для диалога о ботулотоксине и мышечных паттернах.",
    triggers=["Клиент спрашивает про цену ботулотоксина"],
))


def test_matches_skill_by_name_in_message():
    assert find_active_skills_by_message("Хочу биоревитализацию, сколько стоит?", [BIO, BOTOX]) == {"Биоревитализация"}


def test_morphology_tolerated():
    """«биоревитализациЮ» и «биоревитализациЯ» — одно слово."""
    assert score_skill_match("интересует биоревитализация", *BIO) > 0


def test_greeting_gives_no_topic():
    """На приветствии тема не ясна — сужать нечего, работает общий режим."""
    assert find_active_skills_by_message("Здравствуйте!", [BIO, BOTOX]) == set()


def test_unrelated_message_gives_no_topic():
    assert find_active_skills_by_message("А где вы находитесь?", [BIO, BOTOX]) == set()


def test_matches_by_trigger_not_only_name():
    """Клиент не назвал услугу по имени, но формулировка есть в триггере."""
    skill = ("Запись", _doc(triggers=["Клиент просит записаться на консультацию к косметологу"]))
    assert find_active_skills_by_message("хочу записаться на консультацию", [skill, BIO]) == {"Запись"}


def test_works_for_any_business_domain():
    """Автосалон: тот же механизм, ни строчки про клинику."""
    car = ("Кредит на автомобиль", _doc(
        context="Навык про автокредит: ставки, первоначальный взнос, одобрение.",
        triggers=["Клиент спрашивает про кредит или рассрочку на автомобиль"],
    ))
    trade = ("Трейд-ин", _doc(triggers=["Клиент хочет сдать свою машину в зачёт"]))
    assert find_active_skills_by_message("Можно оформить кредит на автомобиль?", [car, trade]) == {"Кредит на автомобиль"}


def test_single_leader_wins_over_weak_matches():
    """Побеждает навык с максимальным баллом, а не любой зацепившийся."""
    got = find_active_skills_by_message(
        "расскажите про ботулотоксин и его стоимость", [BIO, BOTOX]
    )
    assert got == {"Ботулотоксин"}
