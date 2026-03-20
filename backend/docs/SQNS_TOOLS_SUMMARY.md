# Сводка SQNS тулов

## Текущая архитектура

### FastMCP Toolset (предпочтительный подход)

Если `fastmcp` доступен, используется `FastMCPToolset` с 10 тулами:

1. **sqns_find_booking_options** ⭐ ГЛАВНЫЙ
   - Умный поиск услуг и специалистов
   - Проверка совместимости
   - Возвращает готовые ID для записи
   - Используй СНАЧАЛА этот инструмент!

2. **sqns_list_resources** ⚠️ Fallback
   - Полный список всех специалистов
   - Используй ТОЛЬКО если `sqns_find_booking_options` не подходит

3. **sqns_list_services** ⚠️ Fallback
   - Полный список всех услуг
   - Используй ТОЛЬКО если `sqns_find_booking_options` не подходит

4. **sqns_find_client**
   - Поиск клиента по телефону
   - Возвращает данные клиента (ФИО/контакты) или null
   - Для создания визита `client_id` не требуется (визит создается по `user.name` + `user.phone`)

5. **sqns_list_slots**
   - Получение свободных слотов для записи
   - Требует resource_id и service_ids

6. **sqns_create_visit**
   - Создание новой записи
   - Создает визит по `user.name` + `user.phone` и `appointment` (serviceIds/resourceId/datetime)

7. **sqns_update_visit**
   - Обновление существующей записи

8. **sqns_list_visits**
   - Список визитов за период

9. **sqns_client_visits** ⭐ для переноса/отмены
   - Поиск визитов конкретного клиента по телефону и дате
   - Поддерживает `date` (один день) и `date_from/date_till` (период)
   - Возвращает компактный список записей без лишнего payload

10. **sqns_delete_visit**
   - Удаление записи

### Legacy Tools (fallback, если FastMCP недоступен)

Если `fastmcp` НЕ доступен, создаются 9 отдельных `PydanticTool`:

1. sqns_list_resources
2. sqns_list_services
3. sqns_find_client
4. sqns_list_slots
5. sqns_list_visits
6. sqns_client_visits
7. sqns_create_visit
8. sqns_update_visit
9. sqns_delete_visit

**Важно:** Legacy тулы НЕ имеют `sqns_find_booking_options`!

## Архитектура pydantic-ai

### Правильная архитектура:

- **Toolsets** (FastMCPToolset) - для SQNS интеграции
- **Tools** (PydanticTool) - для пользовательских тулов из БД

### Текущая реализация:

```python
# В runtime.py:
if FASTMCP_AVAILABLE:
    # Используем toolset (правильно)
    sqns_toolsets.append(FastMCPToolset(mcp_server))
else:
    # Fallback: создаем отдельные tools (legacy)
    for defn in sqns_tools_definitions:
        wrapped_tools.append(PydanticTool.from_schema(...))

# Агент создается с:
agent = PydanticAgent(
    model_name,
    tools=wrapped_tools,  # Пользовательские тулы из БД
    toolsets=sqns_toolsets  # SQNS toolset
)
```

## Проверка на дублирование

✅ **Нет дублирования:**

- Если FastMCP доступен → используется только toolset
- Если FastMCP недоступен → используются только legacy tools
- Никогда не используются оба одновременно

## Избыточность

⚠️ **Минимальная избыточность:**

- `sqns_list_resources` и `sqns_list_services` дублируют функциональность `sqns_find_booking_options`
- Но они нужны как fallback для случаев, когда нужен полный список
- В описаниях явно указано, что нужно использовать `sqns_find_booking_options` сначала

## Рекомендации

1. ✅ Используй FastMCP toolset (если доступен)
2. ✅ Используй `sqns_find_booking_options` как главный инструмент
3. ✅ Используй `sqns_list_resources`/`sqns_list_services` только как fallback
4. ✅ Не создавай дублирующие тулы вручную
