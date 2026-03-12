<template>
  <Sheet :open="open" @update:open="(v) => !v && close()">
    <SheetContent side="right" class-name="max-w-4xl flex flex-col">
      <!-- Header -->
      <SheetHeader>
        <div class="flex items-center justify-between">
          <SheetTitle>Редактирование записи</SheetTitle>
          <SheetClose />
        </div>
      </SheetHeader>

      <!-- Content (scrollable) -->
      <div class="flex-1 overflow-y-auto p-6 space-y-6">
        <div
          v-for="col in columns"
          :key="col.name"
        >
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
            v-model="formData[col.name]"
            :placeholder="getPlaceholder(col.name, col.label)"
            rows="4"
            class="mt-1 w-full min-h-[96px] rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 whitespace-pre-wrap break-words focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 focus:bg-white transition-all resize-y"
          />

          <!-- Number -->
          <input
            v-else-if="col.type === 'number'"
            v-model.number="formData[col.name]"
            type="number"
            step="any"
            :placeholder="getPlaceholder(col.name, col.label)"
            class="mt-1 w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 font-mono focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 focus:bg-white transition-all"
          />

          <!-- Date -->
          <input
            v-else-if="col.type === 'date'"
            v-model="formData[col.name]"
            type="date"
            class="mt-1 w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 focus:bg-white transition-all"
          />

          <!-- Default text -->
          <input
            v-else
            v-model="formData[col.name]"
            type="text"
            :placeholder="getPlaceholder(col.name, col.label)"
            class="mt-1 w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 focus:bg-white transition-all"
            @keydown.enter="handleEnter"
          />
        </div>

        <div v-if="columns.length === 0" class="text-center py-8 text-slate-400 text-sm">
          Нет столбцов для редактирования.
        </div>

        <p v-if="error" class="text-sm text-red-600">{{ error }}</p>
      </div>

      <!-- Sticky Footer -->
      <div class="flex-shrink-0 border-t border-slate-200 bg-white px-6 py-3">
        <div class="flex items-center justify-end gap-2">
          <button
            @click="close"
            class="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-md transition-colors"
          >
            Отмена
          </button>
          <button
            @click="save"
            class="px-5 py-2 bg-indigo-600 text-white rounded-md text-sm font-bold hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5"
            :disabled="!hasChanges || saving"
          >
            <Loader2 v-if="saving" class="w-3.5 h-3.5 animate-spin" />
            {{ saving ? 'Сохранение...' : 'Сохранить' }}
          </button>
        </div>
      </div>
    </SheetContent>
  </Sheet>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Loader2 } from 'lucide-vue-next'
import type { DirectoryColumn, DirectoryItem } from '~/types/directories'
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
  item: DirectoryItem | null
  saving?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'save', itemId: string, data: Record<string, any>): void
}>()

const formData = ref<Record<string, any>>({})
const initialData = ref<Record<string, any>>({})
const error = ref('')

const hasChanges = computed(() =>
  props.columns.some(col => {
    const current = formData.value[col.name] ?? ''
    const original = initialData.value[col.name] ?? ''
    return String(current) !== String(original)
  })
)

const getPlaceholder = (name: string, label: string) => getFieldPlaceholder(name, label)

const loadItemData = () => {
  if (!props.item) return
  const data: Record<string, any> = {}
  const snapshot: Record<string, any> = {}
  props.columns.forEach(col => {
    const val = props.item!.data[col.name]
    data[col.name] = val ?? (col.type === 'bool' ? false : '')
    snapshot[col.name] = val ?? (col.type === 'bool' ? false : '')
  })
  formData.value = data
  initialData.value = snapshot
}

const save = () => {
  if (!hasChanges.value || props.saving || !props.item) return
  error.value = ''

  const cleanData: Record<string, any> = {}
  props.columns.forEach(col => {
    const val = formData.value[col.name]
    cleanData[col.name] = val === '' ? null : val
  })

  emit('save', props.item.id, cleanData)
}

const close = () => {
  error.value = ''
  emit('update:open', false)
}

const handleEnter = (e: KeyboardEvent) => {
  if (!e.shiftKey) {
    e.preventDefault()
    save()
  }
}

watch(() => props.open, (isOpen) => {
  if (isOpen && props.item) {
    error.value = ''
    loadItemData()
  }
})

defineExpose({
  setError: (err: string) => { error.value = err },
})
</script>
