from __future__ import annotations

from typing import Literal

TargetFormat = Literal["single_sentence", "short_paragraph", "bullet_list"]

AI_FIELD_META: dict[str, dict] = {
    "trigger.client_phrase_examples": {
        "ai_instruction": (
            "Дай 3-5 типичных формулировок клиента, как они звучат в реальной "
            "переписке (мессенджер, разговорный стиль). По одной фразе на строку, "
            "без нумерации, без кавычек."
        ),
        "target_format": "bullet_list",
        "max_chars": 400,
    },
    "trigger.when_relevant": {
        "ai_instruction": (
            "Опиши в 1-2 коротких предложениях, в какой именно ситуации этот "
            "сценарий уместен. Без воды, конкретно: что сказал клиент или что "
            "произошло в диалоге."
        ),
        "target_format": "short_paragraph",
        "max_chars": 280,
    },
    "trigger.keyword_hints": {
        "ai_instruction": (
            "Перечисли 5-10 коротких слов или сигналов (по одному на строку), "
            "по которым ассистент опознаёт эту ситуацию. Используй разговорный язык, "
            "разные синонимы. Без нумерации."
        ),
        "target_format": "bullet_list",
        "max_chars": 400,
    },
    "question.good_question": {
        "ai_instruction": (
            "Сформулируй один открытый вопрос ассистента к клиенту в первом лице. "
            "Тёплый, человеческий тон, без канцелярита. До 200 символов."
        ),
        "target_format": "single_sentence",
        "max_chars": 220,
    },
    "question.why_we_ask": {
        "ai_instruction": (
            "Опиши в 1-2 предложениях, какую информацию даёт ответ клиента и как "
            "она помогает в логике сценария. Это для оператора, не для клиента."
        ),
        "target_format": "short_paragraph",
        "max_chars": 240,
    },
    "question.alternative_phrasings": {
        "ai_instruction": (
            "Дай 2-4 альтернативные формулировки того же вопроса. Разный тон/угол, "
            "по одной на строку, без нумерации."
        ),
        "target_format": "bullet_list",
        "max_chars": 400,
    },
    "condition.routing_hint": {
        "ai_instruction": (
            "Объясни в 1-3 предложениях, как интерпретировать ответ клиента и в "
            "какую ветку уходить. Это инструкция для ассистента, не для клиента."
        ),
        "target_format": "short_paragraph",
        "max_chars": 320,
    },
    "goto.transition_phrase": {
        "ai_instruction": (
            "Одна короткая фраза-связка от ассистента (≤120 символов), мягко "
            "переводящая разговор в новую тему. От первого лица, без штампов."
        ),
        "target_format": "single_sentence",
        "max_chars": 130,
    },
    "goto.trigger_situation": {
        "ai_instruction": (
            "Опиши в 1-2 предложениях ситуацию, когда такой переход уместен: что "
            "сказал клиент или что произошло, чтобы перевести разговор."
        ),
        "target_format": "short_paragraph",
        "max_chars": 240,
    },
    "end.final_action": {
        "ai_instruction": (
            "Опиши финальное действие ассистента в этой ветке: что он делает или "
            "говорит на закрытии. 1-2 предложения, конкретно."
        ),
        "target_format": "short_paragraph",
        "max_chars": 280,
    },
    "business_rule.rule_condition": {
        "ai_instruction": (
            "Опиши условие срабатывания правила обычными словами (когда именно оно "
            "применяется): данные клиента, услуга, ситуация в диалоге. 1-2 предложения."
        ),
        "target_format": "short_paragraph",
        "max_chars": 280,
    },
    "business_rule.rule_action": {
        "ai_instruction": (
            "Опиши, что должен сделать ассистент по этому правилу: какие услуги/слоты "
            "предложить, в каком порядке, с каким аргументом. Конкретно, 1-3 предложения."
        ),
        "target_format": "short_paragraph",
        "max_chars": 360,
    },
    "business_rule.sqns_profile_draft": {
        "ai_instruction": (
            "Дай развернутое описание сущности (специалиста или услуги) для справочника: "
            "ключевые особенности, кому подходит, чем выделяется. 2-4 предложения, "
            "продающий тон, без канцелярита."
        ),
        "target_format": "short_paragraph",
        "max_chars": 600,
    },
    "expertise.situation": {
        "ai_instruction": (
            "Опиши состояние/контекст клиента в 1-2 предложениях, безоценочно. "
            "Не перечисляй варианты — выбери самый частый сценарий."
        ),
        "target_format": "short_paragraph",
        "max_chars": 240,
    },
    "expertise.why_it_works": {
        "ai_instruction": (
            "Объясни, что важно понять про клиента в этой ситуации и почему такой "
            "подход сработает. 1-2 предложения, психология продаж."
        ),
        "target_format": "short_paragraph",
        "max_chars": 280,
    },
    "expertise.approach": {
        "ai_instruction": (
            "Опиши основную мысль, логику и тон шага: что сказать и как подать. "
            "Без конкретных фраз — суть подхода. 2-3 предложения."
        ),
        "target_format": "short_paragraph",
        "max_chars": 320,
    },
    "expertise.example_phrases": {
        "ai_instruction": (
            "Дай 3-5 удачных формулировок ассистента по теме шага. Разговорный тон, "
            "по одной на строку, без нумерации и кавычек."
        ),
        "target_format": "bullet_list",
        "max_chars": 500,
    },
    "expertise.watch_out": {
        "ai_instruction": (
            "Перечисли 2-4 фразы, акценты или интонации, которых стоит избегать. "
            "По одной на строку, коротко и конкретно."
        ),
        "target_format": "bullet_list",
        "max_chars": 360,
    },
    "expertise.good_question": {
        "ai_instruction": (
            "Сформулируй один следующий вопрос или переход, который логично "
            "продолжает эту мысль и двигает диалог. 1 предложение, в первом лице."
        ),
        "target_format": "single_sentence",
        "max_chars": 200,
    },
}


def get_field_ai_meta(field_key: str) -> dict | None:
    return AI_FIELD_META.get(field_key)


def field_key_node_type(field_key: str) -> str | None:
    if "." not in field_key:
        return None
    return field_key.split(".", 1)[0]
