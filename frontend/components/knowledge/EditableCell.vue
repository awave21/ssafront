<template>
  <!-- Editing Mode -->
  <div v-if="editing" class="relative">
    <textarea
      v-if="column.type === 'text' && isLongField"
      ref="inputRef"
      :value="modelValue"
      @input="$emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
      :placeholder="column.label"
      rows="3"
      class="w-full px-2 py-1.5 text-sm border-2 border-indigo-500 rounded bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-100 resize-none"
      @blur="$emit('blur')"
      @keydown="$emit('keydown', $event)"
    />
    <input
      v-else-if="column.type === 'number'"
      ref="inputRef"
      :value="modelValue"
      @input="$emit('update:modelValue', Number(($event.target as HTMLInputElement).value))"
      type="number"
      step="any"
      :placeholder="column.label"
      class="w-full px-2 py-1.5 text-sm border-2 border-indigo-500 rounded bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-100 font-mono"
      @blur="$emit('blur')"
      @keydown="$emit('keydown', $event)"
    />
    <input
      v-else-if="column.type === 'date'"
      ref="inputRef"
      :value="modelValue"
      @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
      type="date"
      class="w-full px-2 py-1.5 text-sm border-2 border-indigo-500 rounded bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-100"
      @blur="$emit('blur')"
      @keydown="$emit('keydown', $event)"
    />
    <label
      v-else-if="column.type === 'bool'"
      class="flex items-center gap-2 px-2 py-1.5 cursor-pointer bg-indigo-50/50 rounded"
    >
      <input
        ref="inputRef"
        :checked="!!modelValue"
        @change="$emit('update:modelValue', ($event.target as HTMLInputElement).checked); $emit('save')"
        type="checkbox"
        class="w-4 h-4 rounded border-indigo-400 text-indigo-600 focus:ring-indigo-500"
      />
      <span class="text-xs font-medium text-indigo-700">{{ modelValue ? 'Да' : 'Нет' }}</span>
    </label>
    <input
      v-else
      ref="inputRef"
      :value="modelValue"
      @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
      type="text"
      :placeholder="column.label"
      class="w-full px-2 py-1.5 text-sm border-2 border-indigo-500 rounded bg-white shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-100"
      @blur="$emit('blur')"
      @keydown="$emit('keydown', $event)"
    />
    <!-- Saving indicator -->
    <div v-if="saving" class="absolute right-2 top-1/2 -translate-y-1/2">
      <Loader2 class="w-4 h-4 animate-spin text-indigo-500" />
    </div>
  </div>

  <!-- Display Mode -->
  <div 
    v-else
    @click="$emit('startEdit')"
    class="px-2 py-1.5 text-sm text-slate-700 rounded cursor-pointer hover:bg-slate-100/80 transition-colors min-h-[32px] flex items-center"
    :class="{ 
      'font-mono': column.type === 'number',
      'text-slate-400 italic': displayValue === null || displayValue === undefined || displayValue === ''
    }"
  >
    <!-- Bool display -->
    <span v-if="column.type === 'bool'" class="flex items-center gap-1.5">
      <span 
        class="w-3.5 h-3.5 rounded flex items-center justify-center text-white text-[10px]"
        :class="displayValue ? 'bg-green-500' : 'bg-slate-200'"
      >
        {{ displayValue ? '✓' : '' }}
      </span>
      <span class="text-xs" :class="displayValue ? 'text-green-700 font-medium' : 'text-slate-400'">
        {{ displayValue ? 'Да' : 'Нет' }}
      </span>
    </span>
    <!-- Other types -->
    <span v-else class="line-clamp-2 leading-tight">
      {{ formattedValue || 'Пусто' }}
    </span>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import { Loader2 } from 'lucide-vue-next'
import type { DirectoryColumn } from '~/types/directories'
import { isLongTextField, formatCellValue } from '~/utils/directory-helpers'

const props = defineProps<{
  column: DirectoryColumn
  displayValue: any
  modelValue: any
  editing: boolean
  saving?: boolean
}>()

defineEmits<{
  (e: 'update:modelValue', value: any): void
  (e: 'startEdit'): void
  (e: 'blur'): void
  (e: 'keydown', event: KeyboardEvent): void
  (e: 'save'): void
}>()

const inputRef = ref<HTMLInputElement | HTMLTextAreaElement | null>(null)

const isLongField = computed(() => isLongTextField(props.column.name))

const formattedValue = computed(() => formatCellValue(props.displayValue, props.column.type))

// Focus input when entering edit mode
watch(() => props.editing, (editing) => {
  if (editing) {
    nextTick(() => {
      const el = inputRef.value
      if (el) {
        if (Array.isArray(el)) {
          el[0]?.focus()
          ;(el[0] as HTMLInputElement)?.select?.()
        } else {
          el.focus()
          ;(el as HTMLInputElement).select?.()
        }
      }
    })
  }
})

defineExpose({ inputRef })
</script>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
</style>
