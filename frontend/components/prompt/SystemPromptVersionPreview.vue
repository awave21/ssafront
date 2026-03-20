<template>
  <Sheet v-model:open="isOpenModel">
    <SheetContent side="right" class-name="!max-w-[100vw] w-full flex flex-col">
      <!-- Header -->
      <SheetHeader>
        <div class="flex items-center justify-between">
          <SheetTitle>
            Сравнение: версия #{{ version?.version_number }} и активная
          </SheetTitle>
          <SheetClose />
        </div>
        <p v-if="version" class="text-sm text-slate-500 mt-1">
          {{ formatDate(version.created_at) }} · {{ getTriggeredByLabel(version.triggered_by) }}
          <span v-if="version.is_active" class="ml-1 text-indigo-600 font-bold">(активна)</span>
        </p>
      </SheetHeader>

      <!-- Content (scrollable) -->
      <div class="flex-1 overflow-y-auto p-6 space-y-4">
        <div v-if="isLoading" class="flex justify-center py-12">
          <Loader2 class="w-5 h-5 animate-spin text-slate-400" />
        </div>

        <template v-else-if="version">
          <div v-if="version.change_summary" class="space-y-1">
            <label class="text-sm font-medium text-slate-700">Описание изменений</label>
            <p class="text-sm text-slate-500 italic">
              « {{ version.change_summary }} »
            </p>
          </div>

          <!-- Diff view: two columns -->
          <div v-if="version.is_active" class="space-y-1">
            <label class="text-sm font-medium text-slate-700">Системный промпт (активная версия)</label>
            <div class="rounded-md border border-slate-200 bg-slate-50">
              <pre class="text-xs text-slate-900 whitespace-pre-wrap font-mono leading-relaxed p-4">{{ version.system_prompt }}</pre>
            </div>
          </div>

          <div v-else class="grid grid-cols-2 gap-4">
            <!-- Left: selected version -->
            <div class="space-y-2">
              <div class="flex items-center gap-2">
                <span class="text-sm font-medium text-slate-700">Версия #{{ version.version_number }}</span>
                <span class="text-[10px] font-medium text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">{{ formatDate(version.created_at) }}</span>
              </div>
              <div class="rounded-md border border-slate-200 bg-slate-50 overflow-auto">
                <div class="p-4 font-mono text-xs leading-relaxed">
                  <div
                    v-for="(seg, i) in diffLeft"
                    :key="'l' + i"
                    class="whitespace-pre-wrap"
                    :class="{
                      'bg-red-100 text-red-800': seg.type === 'removed',
                      'text-slate-900': seg.type === 'equal',
                    }"
                  >{{ seg.text }}</div>
                </div>
              </div>
            </div>

            <!-- Right: active prompt -->
            <div class="space-y-2">
              <div class="flex items-center gap-2">
                <span class="text-sm font-medium text-slate-700">Активная версия</span>
                <span class="text-[10px] font-bold text-indigo-600 bg-indigo-50 px-1.5 py-0.5 rounded">Текущая</span>
              </div>
              <div class="rounded-md border border-slate-200 bg-slate-50 overflow-auto">
                <div class="p-4 font-mono text-xs leading-relaxed">
                  <div
                    v-for="(seg, i) in diffRight"
                    :key="'r' + i"
                    class="whitespace-pre-wrap"
                    :class="{
                      'bg-green-100 text-green-800': seg.type === 'added',
                      'text-slate-900': seg.type === 'equal',
                    }"
                  >{{ seg.text }}</div>
                </div>
              </div>
            </div>
          </div>
        </template>
      </div>

      <!-- Sticky Footer -->
      <div class="flex-shrink-0 border-t border-slate-200 bg-white px-6 py-3">
        <div class="flex items-center justify-end gap-2">
          <button
            @click="isOpenModel = false"
            class="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-md transition-colors"
          >
            Закрыть
          </button>
          <button
            v-if="version && !version.is_active && canActivate"
            @click="$emit('activate')"
            :disabled="isActivating"
            class="px-5 py-2 bg-indigo-600 text-white rounded-md text-sm font-bold hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5"
          >
            <Loader2 v-if="isActivating" class="w-3.5 h-3.5 animate-spin" />
            <RotateCcw v-else class="w-3.5 h-3.5" />
            Восстановить эту версию
          </button>
        </div>
      </div>
    </SheetContent>
  </Sheet>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Loader2, RotateCcw } from 'lucide-vue-next'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetClose,
} from '~/components/ui/sheet'
import { TRIGGERED_BY_LABELS } from '~/types/systemPromptHistory'
import type { SystemPromptVersionRead } from '~/types/systemPromptHistory'
import { computeLineDiff } from '~/utils/text-diff'

const props = defineProps<{
  open: boolean
  version: SystemPromptVersionRead | null
  activePrompt: string
  isLoading: boolean
  isActivating: boolean
  canActivate?: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  activate: []
}>()

const isOpenModel = computed({
  get: () => props.open,
  set: (value) => emit('update:open', value)
})

const diff = computed(() => {
  if (!props.version || props.version.is_active) return null
  return computeLineDiff(props.version.system_prompt, props.activePrompt)
})

const diffLeft = computed(() => diff.value?.left ?? [])
const diffRight = computed(() => diff.value?.right ?? [])

const getTriggeredByLabel = (key: string) => TRIGGERED_BY_LABELS[key] ?? key

const formatDate = (iso: string) => {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const now = new Date()
  const isToday = d.toDateString() === now.toDateString()
  const yesterday = new Date(now)
  yesterday.setDate(yesterday.getDate() - 1)
  const isYesterday = d.toDateString() === yesterday.toDateString()
  const time = d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  if (isToday) return `Сегодня, ${time}`
  if (isYesterday) return `Вчера, ${time}`
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }) + `, ${time}`
}
</script>
