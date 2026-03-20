# Документация AgentsApp

Актуальная документация платформы для создания и управления AI-агентами с SQNS CRM интеграцией.

---

## 📚 SQNS Интеграция

Документация по интеграции с SQNS CRM системой:

### 🎯 Основные документы

1. **[SQNS-TOOLS-VERIFICATION-REPORT.md](./SQNS-TOOLS-VERIFICATION-REPORT.md)** (12KB)
   - **✅ ИТОГОВЫЙ ОТЧЕТ** проверки всех SQNS инструментов
   - Результаты тестирования 4 инструментов
   - Технические детали исправлений
   - Статус: готов к продакшену

2. **[sqns-tools-reference.md](./sqns-tools-reference.md)** (19KB)
   - **📖 СПРАВОЧНИК** всех 8 SQNS инструментов
   - Детальное описание каждого инструмента
   - Параметры, примеры, сценарии использования
   - Рекомендации для AI агента

3. **[sqns-integration-flow.md](./sqns-integration-flow.md)** (20KB)
   - **🔄 КАК РАБОТАЕТ** интеграция SQNS с агентом
   - Подключение к конкретному агенту
   - Передача системного промпта
   - Работа с историей сообщений
   - Диагностика и логирование

4. **[sqns-quick-check.md](./sqns-quick-check.md)** (8.5KB)
   - **⚡ БЫСТРАЯ ПРОВЕРКА** статуса интеграции
   - Чеклист готовности
   - Команды для диагностики
   - Решение частых проблем

### 🔧 Технические спецификации

5. **[sqns-frontend-spec.md](./sqns-frontend-spec.md)** (8.9KB)
   - Спецификация для фронтенд разработки
   - UI/UX для включения/отключения SQNS
   - Контракты API эндпоинтов
   - Обработка ошибок

6. **[sqns-enable-by-password-schema.md](./sqns-enable-by-password-schema.md)** (3.7KB)
   - Схема API для включения SQNS по email/password
   - Параметры запросов
   - Примеры ответов

---

## 🏗️ Архитектура

7. **[agent-tools-architecture-summary.md](./agent-tools-architecture-summary.md)** (6.4KB)
   - **Краткая сводка** архитектуры агентов и инструментов
   - Основные компоненты системы
   - Взаимодействие между модулями

8. **[c4-architecture.md](./c4-architecture.md)** (5.0KB)
   - C4 диаграммы архитектуры
   - Контекст, контейнеры, компоненты

---

## 🗄️ База данных

9. **[database-connection.md](./database-connection.md)** (3.1KB)
   - Настройки подключения к PostgreSQL
   - Пул соединений
   - Мониторинг подключений

10. **[postgres-password-fix.md](./postgres-password-fix.md)** (6.7KB)
    - **Решение проблемы** аутентификации PostgreSQL
    - Root cause анализ
    - Правильная конфигурация

11. **[testing-db-stability.md](./testing-db-stability.md)** (9.1KB)
    - Тестирование стабильности БД
    - Нагрузочное тестирование
    - Мониторинг пула соединений

---

## 🚀 Деплой и обновления

12. **[deploy-update.md](./deploy-update.md)** (3.8KB)
    - Инструкции по обновлению на сервере
    - Процедура деплоя изменений
    - Диагностика проблем

---

## 📁 Структура документации

```
docs/
├── README.md                               # Этот файл - индекс документации
│
├── SQNS Интеграция/
│   ├── SQNS-TOOLS-VERIFICATION-REPORT.md  # ← ИТОГОВЫЙ ОТЧЕТ
│   ├── sqns-tools-reference.md            # ← СПРАВОЧНИК
│   ├── sqns-integration-flow.md           # ← КАК РАБОТАЕТ
│   ├── sqns-quick-check.md                # ← БЫСТРАЯ ПРОВЕРКА
│   ├── sqns-frontend-spec.md              # Для фронтенда
│   └── sqns-enable-by-password-schema.md  # API схема
│
├── Архитектура/
│   ├── agent-tools-architecture-summary.md
│   └── c4-architecture.md
│
├── База данных/
│   ├── database-connection.md
│   ├── postgres-password-fix.md
│   └── testing-db-stability.md
│
└── Деплой/
    └── deploy-update.md
```

---

## 🎯 Быстрый старт

### Для понимания SQNS интеграции:
1. Начните с [SQNS-TOOLS-VERIFICATION-REPORT.md](./SQNS-TOOLS-VERIFICATION-REPORT.md) - итоги проверки
2. Изучите [sqns-tools-reference.md](./sqns-tools-reference.md) - справочник инструментов
3. Прочитайте [sqns-integration-flow.md](./sqns-integration-flow.md) - как это работает

### Для разработки фронтенда:
1. [sqns-frontend-spec.md](./sqns-frontend-spec.md) - спецификация UI
2. [sqns-enable-by-password-schema.md](./sqns-enable-by-password-schema.md) - API схема

### Для диагностики проблем:
1. [sqns-quick-check.md](./sqns-quick-check.md) - быстрая проверка
2. [postgres-password-fix.md](./postgres-password-fix.md) - решение проблем БД
3. [deploy-update.md](./deploy-update.md) - обновление на сервере

---

## 🗑️ Удаленные файлы (устаревшие)

Следующие файлы были удалены как дублирующиеся или устаревшие:

- ❌ `sqns-tools-reference.md` (корневая) - пустой дубликат
- ❌ `fix-agent-prompt.sql` - временный файл
- ❌ `docs/SQNS-AGENT-CHECK-REPORT.md` - промежуточный отчет
- ❌ `docs/fix-postgres-auth-issue.md` - дубликат postgres-password-fix.md
- ❌ `docs/sqns-tools-improvements.md` - включено в VERIFICATION-REPORT
- ❌ `docs/architecture-analysis-agents-tools.md` - старый анализ (31KB)
- ❌ `docs/root-cause-500-agents.md` - проблема решена
- ❌ `docs/troubleshooting-502-bad-gateway.md` - проблема решена

**Итого удалено:** 8 файлов (~75KB устаревшей документации)

---

## 📝 Контрибьютинг

При добавлении новой документации:
1. Используйте понятные названия файлов
2. Добавляйте дату и статус в начало документа
3. Обновляйте этот README.md
4. Удаляйте устаревшие версии документов

---

**Последнее обновление:** 26 января 2026  
**Всего документов:** 12 актуальных файлов
