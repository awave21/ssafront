"""
Gold-standard test cases for FACE CLINIC agent evaluation.
Built from real patient conversations (runs table) + known edge cases.

Each case has:
  message       — patient input
  session_id    — unique per run (reset between experiments)
  expected_*    — what the ideal response should do
  tags          — categories for grouped scoring
"""

TEST_CASES = [
    # === FIRST CONTACT ===
    {
        "id": "tc_01",
        "message": "Добрый день",
        "tags": ["greeting", "first_contact"],
        "must_introduce": True,      # должна назвать себя Стилия
        "must_ask_intent": True,     # должна спросить с чем пришли
        "must_not_list": True,
        "max_length": 200,
    },
    {
        "id": "tc_02",
        "message": "Здравствуйте, хотела узнать об услугах",
        "tags": ["greeting", "first_contact"],
        "must_introduce": True,
        "must_ask_intent": True,
        "must_not_list": True,
        "max_length": 250,
    },

    # === SERVICE INQUIRY — BIOREVITALIZATION ===
    {
        "id": "tc_10",
        "message": "Сколько стоит биоревитализация?",
        "tags": ["service_inquiry", "biorev", "price"],
        "must_use_tools": ["query_microsoft_graphrag"],
        "must_clarify_type": True,   # инъекционная vs безинъекционная
        "must_not_list": True,
        "max_length": 300,
    },
    {
        "id": "tc_11",
        "message": "Делаете биоревитализацию?",
        "tags": ["service_inquiry", "biorev"],
        "must_use_tools": ["query_microsoft_graphrag"],
        "must_clarify_type": True,
        "must_not_list": True,
        "max_length": 250,
    },
    {
        "id": "tc_12",
        "message": "Хочу записаться на биоревитализацию",
        "tags": ["booking", "biorev"],
        "must_use_tools": ["query_microsoft_graphrag"],
        "must_clarify_type": True,
        "must_not_list": True,
        "max_length": 300,
    },

    # === BOTOX ===
    {
        "id": "tc_20",
        "message": "Делаете ботокс?",
        "tags": ["service_inquiry", "botox"],
        "must_use_tools": ["query_microsoft_graphrag"],
        "must_ask_clarification": True,  # уточнить какую услугу
        "must_not_list": True,
        "max_length": 300,
    },
    {
        "id": "tc_21",
        "message": "Сколько единиц ботокса нужно для лба?",
        "tags": ["service_inquiry", "botox", "info"],
        "must_not_invent_facts": True,   # не называть цифры без инструментов
        "must_not_list": True,
        "max_length": 350,
    },

    # === FEAR / OBJECTION ===
    {
        "id": "tc_30",
        "message": "Боюсь иголок, страшно",
        "tags": ["objection", "fear", "needles"],
        "must_use_tools": ["search_expert_tactics"],
        "must_suggest_non_injectable": True,
        "must_show_empathy": True,
        "must_not_list": True,
        "max_length": 350,
    },
    {
        "id": "tc_31",
        "message": "Не знаю, страшно немного",
        "tags": ["objection", "fear"],
        "must_not_pressure": True,
        "must_show_empathy": True,
        "must_not_list": True,
        "max_length": 300,
    },

    # === PRICE OBJECTION ===
    {
        "id": "tc_40",
        "message": "Дорого",
        "tags": ["objection", "price"],
        "must_use_tools": ["search_expert_tactics"],
        "must_not_apologize_for_price": True,
        "must_not_list": True,
        "must_have_next_step": True,
        "max_length": 350,
    },
    {
        "id": "tc_41",
        "message": "У других видела существенно дешевле",
        "tags": ["objection", "price", "competition"],
        "must_use_tools": ["search_expert_tactics"],
        "must_not_bash_competition": True,
        "must_not_list": True,
        "must_have_next_step": True,
        "max_length": 400,
    },

    # === THINKING / HESITATION ===
    {
        "id": "tc_50",
        "message": "Я ещё подумаю",
        "tags": ["objection", "hesitation"],
        "must_not_pressure": True,
        "must_offer_slot_hold": True,  # предложить забронировать без оплаты
        "must_not_list": True,
        "max_length": 250,
    },
    {
        "id": "tc_51",
        "message": "Ну... не знаю, наверное дорого для меня",
        "tags": ["objection", "hesitation", "price"],
        "must_not_pressure": True,
        "must_show_empathy": True,
        "must_ask_clarifying_question": True,
        "must_not_list": True,
        "max_length": 300,
    },

    # === NEGATIVE EXPERIENCE ===
    {
        "id": "tc_60",
        "message": "Делала в другой клинике, не понравилось",
        "tags": ["objection", "negative_experience"],
        "must_show_empathy": True,
        "must_ask_what_went_wrong": True,
        "must_not_bash_competition": True,
        "must_not_list": True,
        "max_length": 300,
    },

    # === MISSING INFO ===
    {
        "id": "tc_70",
        "message": "Есть ли рассрочка?",
        "tags": ["faq", "payment"],
        "must_not_invent_facts": True,   # не выдумывать ответ без поиска
        "must_use_tools": ["search_direct_questions"],
        "must_not_list": True,
        "max_length": 300,
    },
    {
        "id": "tc_71",
        "message": "Какие препараты используете?",
        "tags": ["faq", "products"],
        "must_not_invent_facts": True,
        "must_not_list": True,
        "max_length": 350,
    },

    # === BOOKING INTENT ===
    {
        "id": "tc_80",
        "message": "Хочу записаться на пятницу вечером",
        "tags": ["booking", "scheduling"],
        "must_use_tools": ["query_microsoft_graphrag"],
        "must_ask_what_service": True,   # без услуги нельзя бронировать
        "must_not_list": True,
        "max_length": 300,
    },
    {
        "id": "tc_81",
        "message": "Запишите меня на чистку лица",
        "tags": ["booking", "cleaning"],
        "must_use_tools": ["query_microsoft_graphrag"],
        "must_clarify_type": True,  # ультразвуковая vs комбинированная
        "must_not_list": True,
        "max_length": 300,
    },

    # === OUT OF SCOPE ===
    {
        "id": "tc_90",
        "message": "Порекомендуй ресторан рядом с вами",
        "tags": ["out_of_scope"],
        "must_stay_in_scope": True,
        "must_redirect_to_services": True,
        "must_not_list": True,
        "max_length": 200,
    },
]
