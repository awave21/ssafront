<template>
  <Sheet :open="open" @update:open="(v) => !v && close()">
    <SheetContent side="right" class-name="max-w-4xl flex flex-col">
      <!-- Header -->
      <SheetHeader>
        <div class="flex items-center justify-between">
          <SheetTitle>Новая запись</SheetTitle>
          <SheetClose />
        </div>
        <p class="text-sm text-slate-500 mt-1">
          Заполните поля и нажмите «Сохранить». Форма останется открытой для добавления следующей записи.
        </p>
      </SheetHeader>

      <!-- Content (scrollable) -->
      <div class="flex-1 overflow-y-auto p-6 space-y-6">
        <div v-for="col in columns" :key="col.name">
          <label class="flex items-center gap-1.5 text-sm font-medium text-slate-700">
            {{ col.label }}
            <span v-if="col.required" class="text-red-500 text-xs">*</span>
            <span class="text-xs text-slate-400 font-mono ml-auto">{{ col.name }}</span>
          </label>

          <!-- Boolean -->
          <label
            v-if="col.type === 'bool'"
            class="mt-1 flex items-center gap-3 cursor-pointer px-3 py-2 rounded-md border border-slate-200 hover:border-slate-300 transition-all"
          >
            <input
              :checked="!!formData[col.name]"
              @change="formData[col.name] = ($event.target as HTMLInputElement).checked"
              type="checkbox"
              class="w-5 h-5 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
            />
            <span class="text-sm text-slate-700">{{ formData[col.name] ? 'Да' : 'Нет' }}</span>
          </label>

          <!-- Text -->
          <textarea
            v-else-if="col.type === 'text'"
            :ref="(el) => setRef(col.name, el)"
            v-model="formData[col.name]"
            :placeholder="getPlaceholder(col.name, col.label)"
            rows="4"
            class="mt-1 w-full min-h-[96px] rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 whitespace-pre-wrap break-words focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 focus:bg-white transition-all resize-y"
          />

          <!-- Number -->
          <input
            v-else-if="col.type === 'number'"
            :ref="(el) => setRef(col.name, el)"
            v-model.number="formData[col.name]"
            type="number"
            step="any"
            :placeholder="getPlaceholder(col.name, col.label)"
            class="mt-1 w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 font-mono focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 focus:bg-white transition-all"
          />

          <!-- Date -->
          <input
            v-else-if="col.type === 'date'"
            :ref="(el) => setRef(col.name, el)"
            v-model="formData[col.name]"
            type="date"
            class="mt-1 w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 focus:bg-white transition-all"
          />

          <!-- Default text -->
          <input
            v-else
            :ref="(el) => setRef(col.name, el)"
            v-model="formData[col.name]"
            type="text"
            :placeholder="getPlaceholder(col.name, col.label)"
            class="mt-1 w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 focus:bg-white transition-all"
            @keydown.enter="handleEnter"
          />
        </div>

        <!-- Empty columns notice -->
        <div v-if="columns.length === 0" class="text-center py-8 text-slate-400 text-sm">
          Нет столбцов. Сначала добавьте столбцы в справочник.
        </div>
      </div>

      <!-- Sticky Footer -->
      <div class="flex-shrink-0 border-t border-slate-200 bg-white px-6 py-3">
        <div class="flex items-center justify-between">
          <p v-if="savedCount > 0" class="text-xs text-green-600">
            Добавлено записей за сессию: {{ savedCount }}
          </p>
          <span v-else></span>
          <div class="flex items-center gap-2">
            <button
              @click="close"
              class="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-md transition-colors"
            >
              Закрыть
            </button>
            <button
              @click="save"
              class="px-5 py-2 bg-indigo-600 text-white rounded-md text-sm font-bold hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5"
              :disabled="!hasData || saving"
            >
              <Loader2 v-if="saving" class="w-3.5 h-3.5 animate-spin" />
              {{ saving ? 'Сохранение...' : 'Сохранить' }}
            </button>
          </div>
        </div>
      </div>
    </SheetContent>
  </Sheet>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { Loader2 } from 'lucide-vue-next'
import type { DirectoryColumn } from '~/types/directories'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetClose,
} from '~/components/ui/sheet'
import { getFieldPlaceholder } from '~/utils/directory-helpers'

const props = defineProps<{
  open: boolean
  columns: DirectoryColumn[]
  saving?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'save', data: Record<string, any>): void
}>()

const formData = ref<Record<string, any>>({})
const savedCount = ref(0)
const inputRefs = ref<Record<string, HTMLInputElement | HTMLTextAreaElement | null>>({})

const hasData = computed(() =>
  Object.values(formData.value).some(v => v !== null && v !== undefined && v !== '' && v !== false)
)

const getPlaceholder = (name: string, label: string) => getFieldPlaceholder(name, label)

const setRef = (name: string, el: any) => {
  inputRefs.value[name] = el as HTMLInputElement | HTMLTextAreaElement | null
}

const resetForm = () => {
  const data: Record<string, any> = {}
  props.columns.forEach(col => {
    data[col.name] = col.type === 'bool' ? false : ''
  })
  formData.value = data
}

const focusFirst = () => {
  nextTick(() => {
    const firstCol = props.columns.find(c => c.type !== 'bool')
    if (firstCol && inputRefs.value[firstCol.name]) {
      inputRefs.value[firstCol.name]?.focus()
    }
  })
}

const save = () => {
  if (!hasData.value || props.saving) return

  const cleanData: Record<string, any> = {}
  Object.entries(formData.value).forEach(([key, value]) => {
    if (value !== '' && value !== null && value !== undefined) {
      cleanData[key] = value
    }
  })

  emit('save', cleanData)
  savedCount.value++
  resetForm()
  focusFirst()
}

const close = () => {
  emit('update:open', false)
}

const handleEnter = (e: KeyboardEvent) => {
  if (!e.shiftKey) {
    e.preventDefault()
    save()
  }
}

// Initialize form when sheet opens
watch(() => props.open, (val) => {
  if (val) {
    savedCount.value = 0
    resetForm()
    focusFirst()
  }
})
</script>
