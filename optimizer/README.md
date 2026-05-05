# FACE CLINIC Agent Optimizer

Автономная система улучшения агента Стилия, вдохновлённая [autoresearch](https://github.com/karpathy/autoresearch).

## Структура

```
optimizer/
  eval.py          — фиксированный оценщик (не менять)
  test_cases.py    — 19 тест-кейсов (не менять)
  apply.py         — применяет изменения в БД
  program.md       — инструкции для AI-агента-оптимизатора
  results.tsv      — лог всех экспериментов (auto)
  backups/         — автобэкапы промптов и флоу (auto)
```

## Быстрый старт

```bash
cd /opt/myapp/optimizer

# Посмотреть текущее состояние агента в БД
python apply.py --what status

# Запустить baseline eval
OPTIMIZER_API_KEY=EFzHRBGi1ZlJ8ZbsaGLfK3tdwnkCuld4sFvu9sLgGDI \
  python eval.py --experiment-id baseline

# Запустить один конкретный тест-кейс
OPTIMIZER_API_KEY=... python eval.py --cases tc_01 tc_02 --experiment-id debug_greeting
```

## Как работает оценка

Каждый тест-кейс получает оценку 0–1 по 4 осям:

| Ось | Что проверяет |
|---|---|
| `format_score` | Нет списков, нет запрещённых фраз, длина ≤ лимита |
| `tool_score` | Вызваны нужные инструменты (graphrag, search_expert_tactics и т.д.) |
| `content_score` | Эмпатия где нужна, не критикует конкурентов, не придумывает факты |
| `booking_score` | Есть следующий шаг/вопрос, уточняет тип услуги, ведёт к записи |

`total_score = среднее по всем кейсам`

## Цикл улучшения

1. `eval.py` → найди кейсы с низким score
2. Выдели паттерн ошибки (см. таблицу в `program.md`)
3. Измени промпт или compiled_text флоу
4. `apply.py` → примени в БД
5. `eval.py` → сравни с предыдущим
6. Если хуже → `apply.py --restore backups/...`

## Агент FACE CLINIC

- **UUID**: `176548eb-cce1-4ca8-8775-1f24d45a1b6d`
- **Персонаж**: Стилия, косметологическая клиника
- **Модель**: `openai:gpt-4.1`
- **Скрипт-флоу**: `5cecd7e3-...` (Биоревитализацию, published)
