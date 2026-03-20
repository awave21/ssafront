<template>
  <TableRow class="bg-green-50/50 border-l-4 border-green-400">
    <TableCell class-name="px-4 py-2">
      <div class="w-4 h-4 rounded bg-green-400 flex items-center justify-center">
        <Plus class="w-3 h-3 text-white" />
      </div>
    </TableCell>
    <TableCell 
      v-for="(col, colIndex) in columns" 
      :key="col.name"
      class-name="px-1 py-1"
      :style="{ minWidth: getColWidth(col) }"
    >
      <textarea
        v-if="col.type === 'text' && isLongField(col.name)"
        :ref="(el) => { if (colIndex === 0) firstInputRef = el as HTMLTextAreaElement }"
        :value="rowData[col.name]"
        @input="updateField(col.name, ($event.target as HTMLTextAreaElement).value)"
        :placeholder="col.label"
        rows="2"
        class="w-full px-3 py-2 text-sm border-2 border-green-300 rounded-lg bg-white focus:outline-none focus:border-green-500 focus:ring-2 focus:ring-green-100 resize-none"
        @keydown="handleKeydown($event, colIndex)"
      />
      <input
        v-else-if="col.type === 'number'"
        :ref="(el) => { if (colIndex === 0) firstInputRef = el as HTMLInputElement }"
        :value="rowData[col.name]"
        @input="updateField(col.name, Number(($event.target as HTMLInputElement).value))"
        type="number"
        step="any"
        :placeholder="col.label"
        class="w-full px-3 py-2 text-sm border-2 border-green-300 rounded-lg bg-white focus:outline-none focus:border-green-500 focus:ring-2 focus:ring-green-100 font-mono"
        @keydown="handleKeydown($event, colIndex)"
      />
      <input
        v-else-if="col.type === 'date'"
        :ref="(el) => { if (colIndex === 0) firstInputRef = el as HTMLInputElement }"
        :value="rowData[col.name]"
        @input="updateField(col.name, ($event.target as HTMLInputElement).value)"
        type="date"
        class="w-full px-3 py-2 text-sm border-2 border-green-300 rounded-lg bg-white focus:outline-none focus:border-green-500 focus:ring-2 focus:ring-green-100"
        @keydown="handleKeydown($event, colIndex)"
      />
      <label
        v-else-if="col.type === 'bool'"
        class="flex items-center gap-2 px-3 py-2 cursor-pointer"
      >
        <input
          :checked="!!rowData[col.name]"
          @change="updateField(col.name, ($event.target as HTMLInputElement).checked)"
          type="checkbox"
          class="w-5 h-5 rounded border-green-400 text-green-600 focus:ring-green-500"
        />
        <span class="text-sm">{{ rowData[col.name] ? 'Да' : 'Нет' }}</span>
      </label>
      <input
        v-else
        :ref="(el) => { if (colIndex === 0) firstInputRef = el as HTMLInputElement }"
        :value="rowData[col.name]"
        @input="updateField(col.name, ($event.target as HTMLInputElement).value)"
        type="text"
        :placeholder="col.label"
        class="w-full px-3 py-2 text-sm border-2 border-green-300 rounded-lg bg-white focus:outline-none focus:border-green-500 focus:ring-2 focus:ring-green-100"
        @keydown="handleKeydown($event, colIndex)"
      />
    </TableCell>
    <!-- Empty cell for add column -->
    <TableCell class-name="px-2 py-2 w-40"></TableCell>
    <TableCell class-name="px-4 py-2 w-16">
      <div class="flex items-center justify-end gap-1">
        <button
          @click="$emit('save')"
          :disabled="!hasData || saving"
          class="p-2 text-green-600 hover:text-green-700 hover:bg-green-100 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          title="Сохранить (Enter)"
        >
          <Loader2 v-if="saving" class="w-4 h-4 animate-spin" />
          <Check v-else class="w-4 h-4" />
        </button>
        <button
          @click="$emit('cancel')"
          class="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
          title="Отмена (Esc)"
        >
          <X class="w-4 h-4" />
        </button>
      </div>
    </TableCell>
  </TableRow>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from 'vue'
import { Plus, Loader2, Check, X } from 'lucide-vue-next'
import type { DirectoryColumn } from '~/types/directories'
import { TableRow, TableCell } from '~/components/ui/table'
import { isLongTextField, getColumnWidth } from '~/utils/directory-helpers'

const props = defineProps<{
  columns: DirectoryColumn[]
  rowData: Record<string, any>
  saving?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:field', name: string, value: any): void
  (e: 'save'): void
  (e: 'cancel'): void
}>()

const firstInputRef = ref<HTMLInputElement | HTMLTextAreaElement | null>(null)

const hasData = computed(() =>
  Object.values(props.rowData).some(v => v !== null && v !== undefined && v !== '')
)

const isLongField = (name: string) => isLongTextField(name)
const getColWidth = (col: DirectoryColumn) => getColumnWidth(col.type, col.name)

const updateField = (name: string, value: any) => {
  emit('update:field', name, value)
}

const handleKeydown = (event: KeyboardEvent, _colIndex: number) => {
  if (event.key === 'Escape') {
    event.preventDefault()
    emit('cancel')
    return
  }
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    emit('save')
  }
}

const focus = () => {
  nextTick(() => {
    firstInputRef.value?.focus()
  })
}

onMounted(() => {
  focus()
})

defineExpose({ focus })
</script>
