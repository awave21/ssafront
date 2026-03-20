# AI Agent Management Frontend

Nuxt 3 frontend для платформы управления ИИ-агентами: создание агентов, настройка системных промптов, функции, интеграции, ключи API, обучение промпта, рабочие разделы команды и базовые бизнес-экраны (dashboard, billing, analytics).

## Основной функционал

- Управление агентами: список, создание, редактирование и детализация по разделам.
- Конфигурирование системного промпта и история изменений промпта.
- Обучение и улучшение промпта агента (prompt training / enhancement flow).
- Настройка функций агента (создание, редактирование, тестовый запуск).
- Интеграции и каналы агента, база знаний, модель и чат.
- Управление API-ключами агента (в рамках разрешений/ролей).
- Экран команды и настройки, приглашения пользователей, платежи и аналитика.

## Технологии

- Nuxt 3 (SPA, `ssr: false`)
- Vue 3 + TypeScript
- Pinia
- Tailwind CSS
- Radix Vue / Reka UI
- VueUse

## Структура (верхнеуровнево)

- `pages/` — маршруты приложения
- `components/` — UI и доменные компоненты
- `composables/` — API-слой и повторно используемая бизнес-логика
- `layouts/` — `default` и `agent` layout
- `types/` — типы домена и API

## Локальный запуск

```bash
npm install
npm run dev
```

Открыть в браузере: `http://localhost:3000`

## Доступные скрипты

- `npm run dev` — запуск в режиме разработки
- `npm run build` — сборка (`nuxt generate`)
- `npm run preview` — локальный предпросмотр сборки
- `npm run deploy` — алиас на `npm run build`

## Переменные окружения

Приложение использует публичные runtime-переменные Nuxt:

- `NUXT_PUBLIC_API_BASE` (по умолчанию: `/api/v1`)
- `NUXT_PUBLIC_SITE_URL` (по умолчанию: `http://localhost:3000`)
- `NUXT_PUBLIC_DOMAIN` (по умолчанию: `localhost`)
- `NUXT_PUBLIC_NODE_ENV` (используется в Docker-сборке)

Пример локального `.env`:

```env
NUXT_PUBLIC_API_BASE=/api/v1
NUXT_PUBLIC_SITE_URL=http://localhost:3000
NUXT_PUBLIC_DOMAIN=localhost
NUXT_PUBLIC_NODE_ENV=development
```

## Важно по безопасности

- Файлы `.env` и `.env.*` должны оставаться вне git.
- В репозиторий не добавляются секреты, ключи и токены.
