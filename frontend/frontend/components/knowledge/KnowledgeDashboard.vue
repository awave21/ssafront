<template>
  <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
    <!-- Прямые вопросы -->
    <div
      class="group relative cursor-pointer overflow-hidden rounded-3xl border border-slate-100 bg-white p-6 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-all duration-500 hover:-translate-y-1 hover:shadow-[0_20px_40px_-12px_rgba(0,0,0,0.08)]"
      @click="$emit('select', 'direct_questions')"
    >
      <div class="absolute -right-8 -top-8 h-24 w-24 rounded-full bg-indigo-500/5 transition-transform duration-700 group-hover:scale-150" />

      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-3">
          <div class="h-10 w-10 rounded-xl bg-indigo-50 flex items-center justify-center text-indigo-600 group-hover:bg-indigo-100 transition-colors">
            <MessageSquare class="w-5 h-5" />
          </div>
          <h3 class="font-bold text-slate-900">Прямые вопросы</h3>
        </div>
        <span class="text-xs font-bold text-slate-400 bg-slate-50 px-2.5 py-1 rounded-lg">
          {{ directQuestions.length }}
        </span>
      </div>

      <p class="text-xs text-slate-500 mb-4 leading-relaxed">
        Частые вопросы с возможностью настроить фоллоуапы — автоматическую отправку сообщения через заданное время, если пользователь не ответил.
      </p>

      <div class="space-y-2">
        <div
          v-for="q in directQuestions.slice(0, 3)"
          :key="q.id"
          class="p-3 rounded-2xl border border-slate-50 bg-slate-50/50 text-xs text-slate-600 truncate"
        >
          {{ q.title }}
        </div>
        <div v-if="directQuestions.length === 0" class="py-3 text-center text-xs text-slate-400 italic">
          Нет вопросов
        </div>
      </div>
    </div>

    <!-- Справочники -->
    <div
      class="group relative cursor-pointer overflow-hidden rounded-3xl border border-slate-100 bg-white p-6 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-all duration-500 hover:-translate-y-1 hover:shadow-[0_20px_40px_-12px_rgba(0,0,0,0.08)]"
      @click="$emit('select', 'directories')"
    >
      <div class="absolute -right-8 -top-8 h-24 w-24 rounded-full bg-indigo-500/5 transition-transform duration-700 group-hover:scale-150" />

      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-3">
          <div class="h-10 w-10 rounded-xl bg-indigo-50 flex items-center justify-center text-indigo-600 group-hover:bg-indigo-100 transition-colors">
            <BookOpen class="w-5 h-5" />
          </div>
          <h3 class="font-bold text-slate-900">Справочники</h3>
        </div>
        <span class="text-xs font-bold text-slate-400 bg-slate-50 px-2.5 py-1 rounded-lg">
          {{ directories.length }}
        </span>
      </div>

      <p class="text-xs text-slate-500 mb-4 leading-relaxed">
        Частые вопросы в формате «вопрос / ответ», разбитые по категориям.
      </p>

      <div class="space-y-2">
        <div
          v-for="dir in directories.slice(0, 3)"
          :key="dir.id"
          class="p-3 rounded-2xl border border-slate-50 bg-slate-50/50 text-xs text-slate-600 flex items-center justify-between"
        >
          <span class="truncate">{{ dir.name }}</span>
          <span class="text-[10px] text-slate-400 ml-2 shrink-0">{{ dir.items_count }}</span>
        </div>
        <div v-if="directories.length === 0" class="py-3 text-center text-xs text-slate-400 italic">
          Нет справочников
        </div>
      </div>
    </div>

    <!-- Таблицы -->
    <div
      class="group relative cursor-pointer overflow-hidden rounded-3xl border border-slate-100 bg-white p-6 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-all duration-500 hover:-translate-y-1 hover:shadow-[0_20px_40px_-12px_rgba(0,0,0,0.08)]"
      @click="$emit('select', 'tables')"
    >
      <div class="absolute -right-8 -top-8 h-24 w-24 rounded-full bg-indigo-500/5 transition-transform duration-700 group-hover:scale-150" />

      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-3">
          <div class="h-10 w-10 rounded-xl bg-indigo-50 flex items-center justify-center text-indigo-600 group-hover:bg-indigo-100 transition-colors">
            <Table2 class="w-5 h-5" />
          </div>
          <h3 class="font-bold text-slate-900">Таблицы</h3>
        </div>
        <span class="text-xs font-bold text-slate-400 bg-slate-50 px-2.5 py-1 rounded-lg">
          {{ tables.length }}
        </span>
      </div>

      <p class="text-xs text-slate-500 mb-4 leading-relaxed">
        Произвольные таблицы со своей структурой столбцов. Используйте для хранения любых табличных данных: расписаний, сотрудников, товаров — когда нужна гибкая схема.
      </p>

      <div class="space-y-2">
        <div
          v-for="table in tables.slice(0, 3)"
          :key="table.id"
          class="p-3 rounded-2xl border border-slate-50 bg-slate-50/50 text-xs text-slate-600 flex items-center justify-between"
        >
          <span class="truncate">{{ table.name }}</span>
          <span class="text-[10px] text-slate-400 ml-2 shrink-0">{{ table.items_count }}</span>
        </div>
        <div v-if="tables.length === 0" class="py-3 text-center text-xs text-slate-400 italic">
          Нет таблиц
        </div>
      </div>
    </div>

    <!-- Файлы -->
    <div
      class="group relative cursor-pointer overflow-hidden rounded-3xl border border-slate-100 bg-white p-6 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-all duration-500 hover:-translate-y-1 hover:shadow-[0_20px_40px_-12px_rgba(0,0,0,0.08)]"
      @click="$emit('select', 'file_uploads')"
    >
      <div class="absolute -right-8 -top-8 h-24 w-24 rounded-full bg-indigo-500/5 transition-transform duration-700 group-hover:scale-150" />

      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-3">
          <div class="h-10 w-10 rounded-xl bg-indigo-50 flex items-center justify-center text-indigo-600 group-hover:bg-indigo-100 transition-colors">
            <FileText class="w-5 h-5" />
          </div>
          <h3 class="font-bold text-slate-900">Файлы</h3>
        </div>
        <span class="text-xs font-bold text-slate-400 bg-slate-50 px-2.5 py-1 rounded-lg">
          {{ files.length }}
        </span>
      </div>

      <p class="text-xs text-slate-500 mb-4 leading-relaxed">
        Документы и файлы с семантическим поиском по содержимому. Используйте для инструкций, регламентов, PDF-документов — когда нужно находить информацию внутри длинных текстов.
      </p>

      <div class="space-y-2">
        <div
          v-for="file in files.slice(0, 3)"
          :key="file.id"
          class="p-3 rounded-2xl border border-slate-50 bg-slate-50/50 text-xs text-slate-600 truncate flex items-center gap-2"
        >
          <Folder v-if="file.type === 'folder'" class="w-3 h-3 text-indigo-400" />
          <FileText v-else class="w-3 h-3 text-slate-400" />
          {{ file.title }}
        </div>
        <div v-if="files.length === 0" class="py-3 text-center text-xs text-slate-400 italic">
          Нет файлов
        </div>
      </div>
    </div>

    <!-- SQNS -->
    <div
      v-if="isSqnsEnabled"
      class="group relative cursor-pointer overflow-hidden rounded-3xl border border-slate-100 bg-white p-6 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-all duration-500 hover:-translate-y-1 hover:shadow-[0_20px_40px_-12px_rgba(0,0,0,0.08)]"
      @click="$emit('select', 'sqns')"
    >
      <div class="absolute -right-8 -top-8 h-24 w-24 rounded-full bg-indigo-500/5 transition-transform duration-700 group-hover:scale-150" />

      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-3">
          <div class="h-10 w-10 rounded-xl bg-indigo-50 flex items-center justify-center text-indigo-600 group-hover:bg-indigo-100 transition-colors">
            <Database class="w-5 h-5" />
          </div>
          <h3 class="font-bold text-slate-900">SQNS</h3>
        </div>
        <span class="text-xs font-bold text-slate-400 bg-slate-50 px-2.5 py-1 rounded-lg">
          {{ sqnsTools.length }}
        </span>
      </div>

      <p class="text-xs text-slate-500 mb-4 leading-relaxed">
        Синхронизация с внешней базой услуг и категорий SQNS. Используйте когда услуги управляются в сторонней системе и нужно автоматически подтягивать актуальные данные.
      </p>

      <div class="space-y-2">
        <div
          v-for="tool in sqnsTools.slice(0, 3)"
          :key="tool.name"
          class="p-3 rounded-2xl border border-slate-50 bg-slate-50/50 text-xs text-slate-600 truncate"
        >
          {{ tool.displayName || tool.name }}
        </div>
        <div v-if="sqnsTools.length === 0" class="py-3 text-center text-xs text-slate-400 italic">
          Инструменты не настроены
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { MessageSquare, BookOpen, Table2, FileText, Folder, Database } from 'lucide-vue-next'
import type { DirectQuestion, KnowledgeFileItem } from '~/types/knowledge'
import type { Directory } from '~/types/directories'

defineProps<{
  directQuestions: DirectQuestion[]
  directories: Directory[]
  tables: Directory[]
  files: KnowledgeFileItem[]
  sqnsTools: any[]
  isSqnsEnabled: boolean
}>()

defineEmits<{
  (e: 'select', tab: string): void
}>()
</script>
