<template>
  <nav
    class="rounded-2xl border border-slate-100 bg-white shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] p-1.5"
    aria-label="Разделы агента"
  >
    <ul class="flex flex-wrap gap-1">
      <li v-for="tab in visibleTabs" :key="tab.id" class="min-w-0">
        <NuxtLink
          :to="tab.path"
          class="group flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition-all duration-200 whitespace-nowrap"
          :class="[
            isActive(tab)
              ? 'bg-primary/10 text-primary'
              : 'text-slate-600 hover:bg-slate-50 hover:text-primary'
          ]"
          :aria-current="isActive(tab) ? 'page' : undefined"
        >
          <component
            :is="tab.icon"
            class="h-4 w-4 shrink-0 transition-transform duration-300"
            :class="isActive(tab) ? 'text-primary' : 'text-slate-500 group-hover:text-primary'"
          />
          <span>{{ tab.label }}</span>
        </NuxtLink>
      </li>
    </ul>
  </nav>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  FileText,
  Sliders,
  BookOpen,
  Zap,
  GitBranch,
  Plug,
  MessageCircle,
} from 'lucide-vue-next'

type TabDef = {
  id: string
  label: string
  path: string
  icon: unknown
  /** Список префиксов роутов, при попадании в которые вкладка считается активной */
  match: string[]
}

const props = defineProps<{
  agentId: string
}>()

const route = useRoute()

const tabs = computed<TabDef[]>(() => {
  const id = props.agentId
  return [
    {
      id: 'prompt',
      label: 'Инструкция',
      path: `/agents/${id}/prompt`,
      icon: FileText,
      match: [`/agents/${id}/prompt`],
    },
    {
      id: 'settings',
      label: 'Настройки',
      path: `/agents/${id}/settings`,
      icon: Sliders,
      match: [
        `/agents/${id}/settings`,
        `/agents/${id}/model`,
        `/agents/${id}/api-keys`,
      ],
    },
    {
      id: 'knowledge',
      label: 'Источники знаний',
      path: `/agents/${id}/knowledge`,
      icon: BookOpen,
      // Навыки (/skills) сюда не входят — они внутри раздела «Эксперт»
      // (пункт под-навигации «Источники знаний»), а не в источниках знаний напрямую.
      match: [
        `/agents/${id}/knowledge`,
      ],
    },
    {
      id: 'functions',
      label: 'Функции',
      path: `/agents/${id}/functions`,
      icon: Zap,
      match: [
        `/agents/${id}/functions`,
        `/agents/${id}/function-rules`,
        `/agents/${id}/webhook`,
      ],
    },
    {
      id: 'scenarios',
      label: 'Сценарии',
      path: `/agents/${id}/scenarios`,
      icon: GitBranch,
      match: [
        `/agents/${id}/scenarios`,
      ],
    },
    {
      id: 'channels',
      label: 'Каналы и интеграции',
      path: `/agents/${id}/channels`,
      icon: Plug,
      match: [
        `/agents/${id}/channels`,
        `/agents/${id}/connections`,
      ],
    },
    {
      id: 'testing',
      label: 'Тестирование',
      path: `/agents/${id}/chat`,
      icon: MessageCircle,
      match: [
        `/agents/${id}/chat`,
      ],
    },
  ]
})

const visibleTabs = computed(() => tabs.value)

const isActive = (tab: TabDef): boolean => {
  const currentPath = (route.path || '').replace(/\/+$/, '')
  return tab.match.some(prefix => {
    const normalized = prefix.replace(/\/+$/, '')
    return currentPath === normalized || currentPath.startsWith(`${normalized}/`)
  })
}
</script>
