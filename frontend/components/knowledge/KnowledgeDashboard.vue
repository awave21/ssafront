<template>
  <div class="w-full">
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-5 lg:gap-5">
      <!-- Прямые вопросы -->
      <button
        type="button"
        class="group relative flex w-full cursor-pointer flex-col overflow-hidden rounded-3xl border border-slate-100 bg-white p-5 text-left shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-all duration-500 sm:p-6 hover:-translate-y-1 hover:shadow-[0_20px_40px_-12px_rgba(0,0,0,0.08)]"
        @click="$emit('select', 'direct_questions')"
      >
        <div
          class="pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full bg-indigo-500/5 transition-transform duration-700 group-hover:scale-150"
        />
        <div class="relative z-10 mb-4 flex items-center justify-between">
          <p
            class="text-xs font-normal text-slate-600 transition-colors sm:text-sm group-hover:text-primary"
          >
            Прямые вопросы
          </p>
          <div class="flex items-center gap-2">
            <ChevronRight
              class="h-4 w-4 text-slate-400 opacity-0 transition-all duration-300 group-hover:translate-x-0.5 group-hover:opacity-100"
            />
            <div
              class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-indigo-50 transition-colors group-hover:bg-indigo-100 sm:h-10 sm:w-10"
            >
              <MessageSquare class="h-4 w-4 text-indigo-600 sm:h-5 sm:w-5" />
            </div>
          </div>
        </div>
        <p class="relative z-10 mb-2 text-3xl font-bold text-slate-900 sm:text-4xl">
          {{ directQuestions.length }}
        </p>
        <p class="relative z-10 mb-3 text-xs text-slate-500 sm:text-sm">
          {{ activeDirectQuestions }} активных
        </p>
        <p class="relative z-10 text-xs leading-relaxed text-slate-500 sm:text-sm">
          Частые вопросы с возможностью настроить фоллоуапы — автоматическую отправку сообщения через заданное время, если пользователь не ответил.
        </p>
      </button>

      <!-- Справочники -->
      <button
        type="button"
        class="group relative flex w-full cursor-pointer flex-col overflow-hidden rounded-3xl border border-slate-100 bg-white p-5 text-left shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-all duration-500 sm:p-6 hover:-translate-y-1 hover:shadow-[0_20px_40px_-12px_rgba(0,0,0,0.08)]"
        @click="$emit('select', 'directories')"
      >
        <div
          class="pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full bg-emerald-500/5 transition-transform duration-700 group-hover:scale-150"
        />
        <div class="relative z-10 mb-4 flex items-center justify-between">
          <p
            class="text-xs font-normal text-slate-600 transition-colors sm:text-sm group-hover:text-primary"
          >
            Справочники
          </p>
          <div class="flex items-center gap-2">
            <ChevronRight
              class="h-4 w-4 text-slate-400 opacity-0 transition-all duration-300 group-hover:translate-x-0.5 group-hover:opacity-100"
            />
            <div
              class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-50 transition-colors group-hover:bg-emerald-100 sm:h-10 sm:w-10"
            >
              <BookOpen class="h-4 w-4 text-emerald-600 sm:h-5 sm:w-5" />
            </div>
          </div>
        </div>
        <p class="relative z-10 mb-2 text-3xl font-bold text-slate-900 sm:text-4xl">
          {{ directories.length }}
        </p>
        <p class="relative z-10 mb-3 text-xs text-slate-500 sm:text-sm">
          {{ totalDirectoryItems }} {{ itemsLabel(totalDirectoryItems) }}
        </p>
        <p class="relative z-10 text-xs leading-relaxed text-slate-500 sm:text-sm">
          Частые вопросы в формате «вопрос / ответ», разбитые по категориям.
        </p>
      </button>

      <!-- Загрузка файлов -->
      <button
        type="button"
        class="group relative flex w-full cursor-pointer flex-col overflow-hidden rounded-3xl border border-slate-100 bg-white p-5 text-left shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-all duration-500 sm:p-6 hover:-translate-y-1 hover:shadow-[0_20px_40px_-12px_rgba(0,0,0,0.08)]"
        @click="$emit('select', 'file_uploads')"
      >
        <div
          class="pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full bg-violet-500/5 transition-transform duration-700 group-hover:scale-150"
        />
        <div class="relative z-10 mb-4 flex items-center justify-between">
          <p
            class="text-xs font-normal text-slate-600 transition-colors sm:text-sm group-hover:text-primary"
          >
            Загрузка файлов
          </p>
          <div class="flex items-center gap-2">
            <ChevronRight
              class="h-4 w-4 text-slate-400 opacity-0 transition-all duration-300 group-hover:translate-x-0.5 group-hover:opacity-100"
            />
            <div
              class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-violet-50 transition-colors group-hover:bg-violet-100 sm:h-10 sm:w-10"
            >
              <FileText class="h-4 w-4 text-violet-600 sm:h-5 sm:w-5" />
            </div>
          </div>
        </div>
        <p class="relative z-10 mb-2 text-3xl font-bold text-slate-900 sm:text-4xl">
          {{ uploadedFiles.length }}
        </p>
        <p class="relative z-10 mb-3 text-xs text-slate-500 sm:text-sm">
          {{ indexedFiles }} проиндексировано
        </p>
      </button>

      <!-- SQNS -->
      <button
        type="button"
        class="group relative flex w-full cursor-pointer flex-col overflow-hidden rounded-3xl border border-slate-100 bg-white p-5 text-left shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-all duration-500 sm:p-6 hover:-translate-y-1 hover:shadow-[0_20px_40px_-12px_rgba(0,0,0,0.08)]"
        :class="isSqnsEnabled ? '' : 'opacity-60'"
        @click="$emit('select', 'sqns')"
      >
        <div
          class="pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full bg-amber-500/5 transition-transform duration-700 group-hover:scale-150"
        />
        <div class="relative z-10 mb-4 flex items-center justify-between">
          <p
            class="text-xs font-normal text-slate-600 transition-colors sm:text-sm group-hover:text-primary"
          >
            SQNS
          </p>
          <div class="flex items-center gap-2">
            <ChevronRight
              class="h-4 w-4 text-slate-400 opacity-0 transition-all duration-300 group-hover:translate-x-0.5 group-hover:opacity-100"
            />
            <div
              class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-amber-50 transition-colors group-hover:bg-amber-100 sm:h-10 sm:w-10"
            >
              <Database class="h-4 w-4 text-amber-600 sm:h-5 sm:w-5" />
            </div>
          </div>
        </div>
        <p class="relative z-10 mb-2 text-3xl font-bold text-slate-900 sm:text-4xl">
          {{ sqnsTools.length }}
        </p>
        <p class="relative z-10 text-xs text-slate-500 sm:text-sm">
          {{ isSqnsEnabled ? 'подключено' : 'не подключено' }}
        </p>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { BookOpen, ChevronRight, Database, FileText, MessageSquare } from 'lucide-vue-next'
import type { Directory } from '~/types/directories'
import type { DirectQuestion, KnowledgeFileItem } from '~/types/knowledge'
import type { SqnsTool } from '~/composables/useAgents'

const props = defineProps<{
  directQuestions: DirectQuestion[]
  directories: Directory[]
  files: KnowledgeFileItem[]
  sqnsTools: SqnsTool[]
  isSqnsEnabled: boolean
}>()

defineEmits<{
  (e: 'select', tab: string): void
}>()

const activeDirectQuestions = computed(() => props.directQuestions.filter((q) => q.is_enabled).length)
const totalDirectoryItems = computed(() => props.directories.reduce((acc, d) => acc + (d.items_count ?? 0), 0))
const uploadedFiles = computed(() => props.files.filter((f) => f.type === 'file'))
const indexedFiles = computed(() => uploadedFiles.value.filter((f) => f.vector_status === 'indexed').length)

const itemsLabel = (count: number) => {
  if (count % 10 === 1 && count % 100 !== 11) return 'запись'
  if (count % 10 >= 2 && count % 10 <= 4 && (count % 100 < 10 || count % 100 >= 20)) return 'записи'
  return 'записей'
}
</script>
