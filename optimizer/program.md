# program.md — FACE CLINIC Agent Optimizer

Ты — автономный оптимизатор агента Стилия из Face Clinic.
Твоя задача: улучшить `total_score` на eval suite, изменяя **system_prompt** и **compiled_text скрипт-флоу**.
Запускай эксперименты итерационно. Храни только улучшения.

---

## Контекст

**Агент**: FACE CLINIC (UUID `176548eb-cce1-4ca8-8775-1f24d45a1b6d`)  
**Персонаж**: Стилия — администратор косметологической клиники, опыт 20 лет  
**Основная метрика**: `total_score` из `eval.py` (выше = лучше, max 1.0)  
**Ключевая проблема**: агент должен вести клиента к записи, не давить, не выдумывать факты  

**Текущие файлы**:
- `eval.py` — фиксированный оценщик, **не менять**
- `test_cases.py` — тест-кейсы, **не менять**
- `apply.py` — применяет изменения в БД
- `backups/` — автоматические бэкапы
- `results.tsv` — лог экспериментов

**Текущий system_prompt** — в БД (проверь через `python apply.py --what status`)  
**Скрипт-флоу "Биоревитализацию"** — ID `5cecd7e3-0ca1-4726-844c-44294215475c`

---

## Правила

1. **Один эксперимент = одно изменение** (либо промпт, либо один флоу, не оба сразу)
2. **Базовый запуск сначала** — запусти `python eval.py --experiment-id baseline` до любых изменений
3. **5-минутный лимит** — каждый eval занимает ~2-3 мин, не запускай одновременно
4. **Откат при деградации** — если `total_score` упал, восстанови из `backups/`
5. **Логируй** — каждый эксперимент через `--experiment-id` и `--note`
6. **Не трогай** `eval.py`, `test_cases.py`, параметры подключения

---

## Что можно менять

### System Prompt (`agents.system_prompt`)

Хорошие эксперименты:
- Добавить/улучшить примеры для конкретных ситуаций (`<example>`)
- Уточнить когда вызывать `search_expert_tactics`
- Усилить инструкцию про "не изобретать факты"
- Добавить образец для приветствия (сейчас tc_01/tc_02 дают низкий score)
- Добавить инструкцию про рассрочку (tc_70 — no_match в базе знаний)
- Улучшить секцию "Сигналы сомнения"

Не трогать:
- UUID, внешние ключи, SQL
- Логику SQNS (порядок вызовов)
- Структуру GraphRAG (`focus=booking` / `focus=general`)

### Script Flow compiled_text (`script_flows.compiled_text`)

Хорошие эксперименты:
- Добавить узел для обработки страха игл (сейчас в флоу биоревитализации нет)
- Добавить узел "Клиент сравнивает цены"
- Добавить условие для безинъекционной ветки
- Улучшить формулировки `▸ Вариативные формулировки`

---

## Цикл эксперимента

```
1. python apply.py --what status          # посмотреть текущее состояние
2. python eval.py --experiment-id <name>  # запустить оценку
3. Проанализировать failures в выводе
4. Подготовить изменение в файл (new_prompt.txt или new_flow.md)
5. python apply.py --what prompt --file new_prompt.txt  # применить
6. python eval.py --experiment-id <name>-v2 --note "<что изменил>"
7. Сравнить total_score с предыдущим
   - Лучше → продолжить следующий эксперимент
   - Хуже  → python apply.py --what prompt --restore backups/prompt_<ts>.txt
8. Повторить с п.3
```

---

## Форматы результатов

`results.tsv` (автоматически пишет `eval.py`):
```
experiment_id   total_score  n_cases  note
baseline        0.712300     19       initial
add_greeting    0.741200     19       added intro example for tc_01
```

---

## Подсказки по диагностике

| Паттерн ошибки | Вероятная причина | Что менять |
|---|---|---|
| `no self-introduction` в tc_01/02 | Нет примера приветствия в промпте | Добавить `<example>` с Добрый день |
| `required tool not called: search_expert_tactics` | Условие вызова слишком узкое | Расширить раздел "search_expert_tactics" |
| `did not clarify service type` | Агент не уточняет инъекционная/нет | Добавить в флоу или промпт |
| `response contains list formatting` | Агент генерирует списки | Усилить запрет + добавить примеры прозой |
| `no next step / question` | Агент даёт информацию без призыва к действию | Добавить в промпт правило "всегда один шаг вперёд" |
| `did not ask which service before booking` | Агент сразу ищет слоты без уточнения | Добавить в раздел "Порядок записи" |

---

## Пример первого запуска

```bash
cd /opt/myapp/optimizer

# 1. Проверить статус
python apply.py --what status

# 2. Базовый результат
python eval.py --experiment-id baseline --note "initial state"

# 3. Посмотреть failures и выбрать первое улучшение
# ... анализ ...

# 4. Сохранить текущий промпт для редактирования
python apply.py --what status  # и скопировать промпт из БД в файл

# 5. Отредактировать промпт, применить, переоценить
python apply.py --what prompt --file new_prompt_v1.txt
python eval.py --experiment-id v1_greeting_fix --note "добавил пример приветствия"
```
