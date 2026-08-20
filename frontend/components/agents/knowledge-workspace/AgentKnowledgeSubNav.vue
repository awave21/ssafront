<template>
  <nav class="w-full lg:w-64 shrink-0" aria-label="Разделы источников знаний">
    <ul class="flex flex-col gap-1.5">
      <li v-for="item in items" :key="item.id">
        <NuxtLink
          :to="item.to"
          replace
          class="group flex items-start gap-3 rounded-2xl border border-transparent px-3 py-2.5 transition-all duration-200"
          :class="[
            isActive(item)
              ? 'border-primary/20 bg-primary/10 text-primary shadow-[0_2px_8px_-4px_rgba(59,130,246,0.15)]'
              : 'text-slate-600 hover:border-slate-100 hover:bg-slate-50 hover:text-primary'
          ]"
          :aria-current="isActive(item) ? 'page' : undefined"
        >
          <div
            class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl transition-colors"
            :class="[
              isActive(item)
                ? 'bg-white text-primary shadow-[0_1px_3px_-1px_rgba(0,0,0,0.08)]'
                : 'bg-slate-100 text-slate-500 group-hover:bg-white group-hover:text-primary'
            ]"
          >
            <component :is="item.icon" class="h-4 w-4" />
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-1.5">
              <span class="text-sm font-semibold leading-tight">{{ item.label }}</span>
              <span
                v-if="typeof item.count === 'number'"
                class="rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-500"
              >{{ item.count }}</span>
            </div>
            <div class="mt-0.5 text-xs leading-tight text-slate-400">{{ item.hint }}</div>
          </div>
        </NuxtLink>
      </li>
    </ul>
  </nav>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import type { RouteLocationRaw } from 'vue-router'
import {
  LayoutDashboard,
  MessageCircle,
  FileText,
  BookOpen,
  Table2,
  Database,
  GraduationCap,
} from 'lucide-vue-next'

type SubNavItem = {
  id: string
  label: string
  hint: string
  icon: unknown
  to: RouteLocationRaw
  count?: number
  /** Абсолютный роут: пункт активен если совпадает route.path (и опционально query.knowledgeTab). */
  matchPath?: string
  /** knowledgeTab, при котором пункт активен на странице /knowledge */
  matchTab?: string
}

const props = defineProps<{
  agentId: string
  counts?: {
    directQuestions?: number
    directories?: number
    tables?: number
    sqns?: number
  }
  showSqns?: boolean
}>()

const route = useRoute()

const items = computed<SubNavItem[]>(() => {
  const id = props.agentId
  const knowledgePath = `/agents/${id}/knowledge`
  const skillsPath = `/agents/${id}/skills`

  const list: SubNavItem[] = [
    {
      id: 'dashboard',
      label: 'Обзор',
      hint: 'Сводка по всем источникам',
      icon: LayoutDashboard,
      to: { path: knowledgePath, query: { knowledgeTab: 'dashboard' } },
      matchPath: knowledgePath,
      matchTab: 'dashboard',
    },
    {
      id: 'direct_questions',
      label: 'Прямые вопросы',
      hint: 'Готовые ответы на типовые фразы',
      icon: MessageCircle,
      to: { path: knowledgePath, query: { knowledgeTab: 'direct_questions' } },
      matchPath: knowledgePath,
      matchTab: 'direct_questions',
      count: props.counts?.directQuestions,
    },
    {
      id: 'file_uploads',
      label: 'Файлы',
      hint: 'Загруженные документы с чанками',
      icon: FileText,
      to: { path: knowledgePath, query: { knowledgeTab: 'file_uploads' } },
      matchPath: knowledgePath,
      matchTab: 'file_uploads',
    },
    {
      id: 'directories',
      label: 'Справочники',
      hint: 'Табличные знания с поиском',
      icon: BookOpen,
      to: { path: knowledgePath, query: { knowledgeTab: 'directories' } },
      matchPath: knowledgePath,
      matchTab: 'directories',
      count: props.counts?.directories,
    },
    {
      id: 'tables',
      label: 'Таблицы',
      hint: 'Данные в структуре колонок',
      icon: Table2,
      to: { path: knowledgePath, query: { knowledgeTab: 'tables' } },
      matchPath: knowledgePath,
      matchTab: 'tables',
      count: props.counts?.tables,
    },
  ]

  if (props.showSqns !== false) {
    list.push({
      id: 'sqns',
      label: 'SQNS',
      hint: 'База знаний из CRM клиники',
      icon: Database,
      to: { path: knowledgePath, query: { knowledgeTab: 'sqns' } },
      matchPath: knowledgePath,
      matchTab: 'sqns',
      count: props.counts?.sqns,
    })
  }

  list.push({
    id: 'skills',
    label: 'Навыки эксперта',
    hint: 'Расширения поведения агента',
    icon: GraduationCap,
    to: skillsPath,
    matchPath: skillsPath,
  })

  return list
})

const isActive = (item: SubNavItem): boolean => {
  if (!item.matchPath) return false
  const currentPath = (route.path || '').replace(/\/+$/, '')
  const normalized = item.matchPath.replace(/\/+$/, '')
  const pathMatches = currentPath === normalized || currentPath.startsWith(`${normalized}/`)
  if (!pathMatches) return false
  // Для страницы /knowledge — сравниваем ещё и knowledgeTab query.
  if (item.matchTab) {
    const currentTab = String(route.query.knowledgeTab || 'dashboard')
    return currentTab === item.matchTab
  }
  return true
}
</script>
