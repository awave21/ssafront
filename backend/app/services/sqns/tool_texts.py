from __future__ import annotations

# Единственный источник "текстов для LLM" по SQNS тулам (язык: русский).
# Эти описания должны быть одинаковыми для:
# - Legacy tool definitions (schemas/agent.py)
# - FastMCP toolset (services/sqns_mcp_server.py)

SQNS_TOOL_DESCRIPTIONS: dict[str, str] = {
    "sqns_find_booking_options": (
        "Вызывай первым для подбора услуги и специалиста по словам клиента. "
        "Передавай service_name и/или specialist_name из диалога; при необходимости добавь category — "
        "фильтр по категории услуги (ILIKE по полю category в кэше), можно только category без имён для списка услуг в разделе. "
        "Точные названия категорий бери из sqns_list_categories. "
        "Нечёткий ILIKE может дать несколько услуг без специалиста: тогда в alternatives.services список услуг, уточни или выбери id. "
        "Если переданы оба параметра и совместимых пар несколько, смотри alternatives.compatible_pairs (для каждой пары в доп. поле оба SQNS id). "
        "Если ready=True, используй service_id и resource_id из корня ответа для sqns_list_slots. "
        "Если ready=False, предложи варианты из alternatives и дождись выбора."
    ),
    "sqns_list_resources": (
        "Возвращает полный список специалистов с resource_id. "
        "Используй, когда нужно показать всех специалистов или выбрать вручную."
    ),
    "sqns_list_services": (
        "Возвращает полный список услуг с service_id. "
        "Используй для показа полного каталога или ручного выбора услуги."
    ),
    "sqns_list_categories": (
        "Возвращает категории услуг из синхронизированной базы (имя, is_enabled, priority, services_count). "
        "Используй, чтобы перечислить направления/разделы каталога или понять, какие категории активны."
    ),
    "sqns_find_client": (
        "Ищи клиента по телефону из диалога. "
        "Если найден, используй name и phone для sqns_create_visit. "
        "Если не найден, попроси ФИО у клиента."
    ),
    "sqns_list_slots": (
        "Показывает свободные слоты по resource_id, service_ids и дате. "
        "Бери resource_id и service_ids из sqns_find_booking_options. "
        "Предложи клиенту 2-3 подходящих времени."
    ),
    "sqns_create_visit": (
        "Создает запись, когда клиент выбрал слот и подтвердил контактные данные. "
        "Передавай resource_id и service_id из sqns_find_booking_options, datetime из sqns_list_slots. "
        "user_name и phone обязательны."
    ),
    "sqns_update_visit": (
        "Обновляет запись по visit_id. "
        "Для переноса передавай новый datetime только из sqns_list_slots. "
        "Передавай только изменяемые поля."
    ),
    "sqns_list_visits": (
        "Возвращает подробный список записей клиента за период. "
        "Используй для просмотра истории и получения visit_id."
    ),
    "sqns_client_visits": (
        "Быстро ищет визиты клиента по телефону и дате/диапазону. "
        "Используй для получения visit_id перед переносом или отменой."
    ),
    "sqns_delete_visit": (
        "Отменяет запись по visit_id. "
        "Используй visit_id из sqns_client_visits и подтверждай отмену только после ok=True."
    ),
}


def get_sqns_tool_description(tool_name: str) -> str:
    return SQNS_TOOL_DESCRIPTIONS.get(tool_name, "")

