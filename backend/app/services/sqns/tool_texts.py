from __future__ import annotations

# Единственный источник "текстов для LLM" по SQNS тулам (язык: русский).
# Эти описания должны быть одинаковыми для:
# - Legacy tool definitions (schemas/agent.py)
# - FastMCP toolset (services/sqns_mcp_server.py)


SQNS_PROMPT_BRIDGE = """\
=== ЗАПИСЬ КЛИЕНТА — ПОРЯДОК ДЕЙСТВИЙ ===

Когда клиент хочет записаться, перенести или отменить запись — строго следуй этому порядку:

ЗАПИСЬ (новая):
1. sqns_find_booking_options(service_name=..., specialist_name=...)
   → ready=True: переходи к шагу 2
   → ready=False: уточни у клиента услугу или специалиста из списка alternatives
2. sqns_list_slots(resource_id=..., service_ids=[...], date=...)
   → предложи клиенту 2–3 варианта времени
3. Клиент выбрал слот → спроси номер телефона (если ещё не дал)
4. sqns_find_client(phone=...) → получи name/phone
   → не найден: попроси ФИО
5. sqns_create_visit(resource_id, service_id, datetime, user_name, phone)
   → подтверди клиенту: услуга, специалист, дата/время

ПЕРЕНОС записи:
1. sqns_client_visits(phone=...) → получи visit_id
2. sqns_list_slots(...) → выбери новый слот вместе с клиентом
3. sqns_update_visit(visit_id=..., datetime=...) → подтверди

ОТМЕНА записи:
1. sqns_client_visits(phone=...) → получи visit_id
2. sqns_delete_visit(visit_id=...) → подтверди только после ok=True

ВАЖНО:
• Не создавай запись без подтверждённого слота из sqns_list_slots.
• Не создавай запись без phone и user_name клиента.
• После ok=True всегда подтверди клиенту детали записи.
=== /ЗАПИСЬ КЛИЕНТА ==="""

SQNS_TOOL_DESCRIPTIONS: dict[str, str] = {
    "sqns_find_booking_options": (
        "Подбирает услугу и/или специалиста по словам клиента. Вызывай первым при любом запросе записи. "
        "Передавай service_name и/или specialist_name; category — для фильтра по разделу (точные названия из sqns_list_categories). "
        "ready=True → бери service_id и resource_id для sqns_list_slots. "
        "ready=False → предложи варианты из alternatives и дождись выбора клиента."
    ),
    "sqns_list_resources": (
        "Список всех специалистов с resource_id. "
        "Используй для показа специалистов или ручного выбора."
    ),
    "sqns_list_services": (
        "Список всех услуг с service_id. "
        "Используй для показа каталога или ручного выбора услуги."
    ),
    "sqns_list_categories": (
        "Категории услуг с именами и статусами. "
        "Используй для перечисления разделов или получения точного имени категории."
    ),
    "sqns_find_client": (
        "Ищет клиента по номеру телефона. "
        "Если найден — передай name и phone в sqns_create_visit. "
        "Если не найден — попроси ФИО."
    ),
    "sqns_list_slots": (
        "Свободные слоты по resource_id, service_ids и дате из sqns_find_booking_options. "
        "Предложи клиенту 2-3 варианта времени."
    ),
    "sqns_create_visit": (
        "Создаёт запись после выбора слота и подтверждения контактов. "
        "resource_id и service_id — из sqns_find_booking_options, datetime — из sqns_list_slots. "
        "user_name и phone обязательны."
    ),
    "sqns_update_visit": (
        "Обновляет запись по visit_id. "
        "При переносе datetime бери только из sqns_list_slots. "
        "Передавай только изменяемые поля."
    ),
    "sqns_list_visits": (
        "Записи клиента за период с деталями. "
        "Используй для истории или получения visit_id."
    ),
    "sqns_client_visits": (
        "Быстрый поиск записей по телефону и дате. "
        "Используй для получения visit_id перед переносом или отменой."
    ),
    "sqns_delete_visit": (
        "Отменяет запись по visit_id. "
        "visit_id бери из sqns_client_visits; подтверждай отмену только после ok=True."
    ),
}


def get_sqns_tool_description(tool_name: str) -> str:
    return SQNS_TOOL_DESCRIPTIONS.get(tool_name, "")

