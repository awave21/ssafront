# Тестирование стабильности БД

## Быстрая проверка (используйте это чаще всего)

```bash
./test-db-stability-quick.sh
```

**Время выполнения**: ~30 секунд  
**Что проверяет**: Подключение, пароль, API, логи, конфигурация

## Полное тестирование (используйте перед релизом)

```bash
./test-db-stability.sh
```

**Время выполнения**: ~5-10 минут  
**Что делает**: 8 тестов включая перезапуски и стресс-тесты

## Когда запускать тесты

### Обязательно:
- ✅ После изменения `docker-compose.yml`
- ✅ После изменения `.env`
- ✅ Перед коммитом изменений в БД
- ✅ Перед релизом в продакшн

### Рекомендуется:
- 🔄 Ежедневно (быстрая проверка)
- 🔄 Еженедельно (полное тестирование)
- 🔄 После перезагрузки сервера

## Автоматические тесты

GitHub Actions запускается автоматически:
- При push в `main` / `develop`
- При изменении БД-связанных файлов
- Каждый день в 3:00 UTC
- Вручную через Actions → Run workflow

## Что делать если тесты падают

См. подробную документацию: `docs/testing-db-stability.md`

## Checklist перед продакшн

```bash
# 1. Быстрая проверка
./test-db-stability-quick.sh

# 2. Если прошла успешно - полное тестирование
./test-db-stability.sh

# 3. Создать бэкап
docker compose exec db pg_dump -U postgres agents > backup_$(date +%Y%m%d).sql

# 4. Проверить что нет костылей
grep -E "entrypoint.*wrapper|db-entrypoint-wrapper" docker-compose.yml
# Должно быть пусто

# 5. Деплой!
```

## Быстрые команды

```bash
# Проверить текущее состояние
docker compose ps
docker compose logs api --tail 20
docker compose logs db --tail 20

# Проверить подключение к БД
docker compose exec db psql -U postgres -d agents -c "SELECT 1"

# Проверить пароль
PGPASSWORD=postgres docker compose exec db psql -U postgres -d agents -c "SELECT 1"

# Проверить API
curl http://localhost:8000/api/v1/health

# Перезапустить всё
docker compose restart

# Полный перезапуск
docker compose down && docker compose up -d
```
