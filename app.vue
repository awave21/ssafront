<template>
  <div>
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
    <Toaster />
  </div>
</template>

<script setup lang="ts">
import Toaster from './components/ui/Toaster.vue'

type PageMeta = {
  title: string
  description: string
}

const APP_NAME = 'ChatMedBot'

const DEFAULT_META: PageMeta = {
  title: 'Умные ИИ-агенты для вашей клиники',
  description: 'Автоматизируйте рутинные задачи, улучшите качество диагностики и освободите врачей для работы с пациентами. Современные AI-решения для современной медицины.'
}

const resolvePageMeta = (path: string): PageMeta => {
  const normalizedPath = path.length > 1 ? path.replace(/\/+$/, '') : path

  if (normalizedPath === '/') {
    return {
      title: 'Искусственный интеллект для медицины',
      description: 'Автоматизируйте рутинные задачи, улучшите качество диагностики и освободите врачей для работы с пациентами. Современные AI-решения для современной медицины.'
    }
  }

  if (normalizedPath === '/login') {
    return {
      title: 'Авторизация',
      description: 'Искусственный интеллект для медицины. Вход и регистрация в ChatMedBot.'
    }
  }

  if (normalizedPath.indexOf('/invite/accept') === 0) {
    return {
      title: 'Принятие приглашения',
      description: 'Завершение регистрации и подключение к организации в ChatMedBot.'
    }
  }

  if (normalizedPath === '/dashboard') {
    return {
      title: 'Дашборд',
      description: 'Обзор ключевых показателей, агентов и активности в системе.'
    }
  }

  if (normalizedPath === '/analytics') {
    return {
      title: 'Аналитика',
      description: 'Статистика и графики по работе агентов и системы.'
    }
  }

  if (normalizedPath === '/patients') {
    return {
      title: 'Пациенты',
      description: 'Управление списком пациентов и связанными данными.'
    }
  }

  if (normalizedPath === '/dialogs') {
    return {
      title: 'Диалоги',
      description: 'Просмотр и управление диалогами агентов.'
    }
  }

  if (normalizedPath === '/credentials') {
    return {
      title: 'Учетные данные',
      description: 'Хранилище и настройка учетных данных для интеграций.'
    }
  }

  if (normalizedPath === '/api-keys') {
    return {
      title: 'API-ключи',
      description: 'Создание и управление API-ключами доступа.'
    }
  }

  if (normalizedPath === '/settings') {
    return {
      title: 'Настройки',
      description: 'Общие настройки аккаунта и параметров системы.'
    }
  }

  if (normalizedPath === '/settings/team') {
    return {
      title: 'Команда',
      description: 'Управление участниками команды и ролями доступа.'
    }
  }

  if (normalizedPath === '/agents') {
    return {
      title: 'Агенты',
      description: 'Список AI-агентов и управление их состоянием.'
    }
  }

  if (normalizedPath === '/agents/new') {
    return {
      title: 'Новый агент',
      description: 'Создание нового AI-агента и первичная настройка.'
    }
  }

  if (/^\/agents\/[^/]+\/chat$/.test(normalizedPath)) {
    return {
      title: 'Чат агента',
      description: 'Диалоговый интерфейс для проверки и работы с агентом.'
    }
  }

  if (/^\/agents\/[^/]+\/model$/.test(normalizedPath)) {
    return {
      title: 'Модель агента',
      description: 'Настройка модели, параметров и провайдера для агента.'
    }
  }

  if (/^\/agents\/[^/]+\/prompt$/.test(normalizedPath)) {
    return {
      title: 'Промпт агента',
      description: 'Редактирование системного промпта и поведения агента.'
    }
  }

  if (/^\/agents\/[^/]+\/knowledge$/.test(normalizedPath)) {
    return {
      title: 'База знаний агента',
      description: 'Управление источниками знаний и контентом агента.'
    }
  }

  if (/^\/agents\/[^/]+\/channels$/.test(normalizedPath)) {
    return {
      title: 'Каналы агента',
      description: 'Настройка каналов подключения и доставки сообщений.'
    }
  }

  if (/^\/agents\/[^/]+\/connections$/.test(normalizedPath)) {
    return {
      title: 'Интеграции агента',
      description: 'Подключение внешних сервисов и параметров интеграций.'
    }
  }

  if (/^\/agents\/[^/]+\/functions$/.test(normalizedPath)) {
    return {
      title: 'Функции агента',
      description: 'Управление функциями, инструментами и их параметрами.'
    }
  }

  if (/^\/agents\/[^/]+$/.test(normalizedPath)) {
    return {
      title: 'Профиль агента',
      description: 'Общая карточка и ключевые настройки выбранного агента.'
    }
  }

  return DEFAULT_META
}

const route = useRoute()

useHead(() => {
  const pageMeta = resolvePageMeta(route.path)
  const fullTitle = `${pageMeta.title} | ${APP_NAME}`

  return {
    title: fullTitle,
    meta: [
      {
        key: 'description',
        name: 'description',
        content: pageMeta.description
      },
      {
        key: 'og:title',
        property: 'og:title',
        content: fullTitle
      },
      {
        key: 'og:description',
        property: 'og:description',
        content: pageMeta.description
      }
    ]
  }
})
</script>