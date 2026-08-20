<template>
  <div class="grid grid-cols-1 gap-2.5 sm:grid-cols-2" :class="wideClass">
    <button
      v-for="item in items"
      :key="item.value"
      type="button"
      :disabled="disabled || item.disabled"
      class="group relative flex items-start gap-3 rounded-2xl border p-3 text-left transition-all duration-300 disabled:cursor-not-allowed disabled:opacity-55"
      :class="item.value === modelValue
        ? 'border-primary/40 bg-primary/[0.06] shadow-[0_2px_12px_-4px_rgba(59,130,246,0.15)]'
        : 'border-slate-200 bg-white hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-[0_10px_24px_-14px_rgba(0,0,0,0.08)] disabled:hover:translate-y-0 disabled:hover:border-slate-200 disabled:hover:shadow-none'"
      @click="select(item)"
    >
      <div
        class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl transition-colors"
        :class="item.value === modelValue
          ? 'bg-primary/15 text-primary'
          : 'bg-slate-100 text-slate-500 group-hover:bg-primary/10 group-hover:text-primary'"
      >
        <component :is="item.icon" class="h-4 w-4" />
      </div>

      <div class="min-w-0 flex-1">
        <div class="flex items-center gap-1.5">
          <span
            class="text-sm font-semibold leading-snug"
            :class="item.value === modelValue ? 'text-primary' : 'text-slate-900'"
          >{{ item.label }}</span>
          <span
            v-if="item.badge"
            class="shrink-0 rounded-full bg-slate-200 px-1.5 py-0.5 text-[9px] font-black uppercase tracking-wider text-slate-500"
          >{{ item.badge }}</span>
        </div>
        <div class="mt-0.5 text-xs leading-snug text-slate-500">{{ item.description }}</div>
      </div>
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Component } from 'vue'

export type OptionCardItem = {
  /** Значение, которое уйдёт наверх: тип действия или пресет (webhook_api_call). */
  value: string
  label: string
  description: string
  icon: Component
  /** Недоступные варианты остаются видимыми, но кликнуть нельзя. */
  disabled?: boolean
  /** Короткая метка в углу карточки, например «Скоро». */
  badge?: string
}

const props = defineProps<{
  items: OptionCardItem[]
  modelValue: string
  /** Общая блокировка — например, нет прав на редактирование. */
  disabled?: boolean
  /** Сколько колонок на широком экране. По умолчанию три. */
  columns?: 2 | 3 | 4
}>()

// Классы перечислены целиком, а не собраны из кусков: Tailwind вычищает всё,
// чего нет в исходниках дословно, и `lg:grid-cols-${n}` просто не попал бы в сборку.
const wideClass = computed(() => {
  if (props.columns === 2) return ''
  if (props.columns === 4) return 'lg:grid-cols-4'
  return 'lg:grid-cols-3'
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const select = (item: OptionCardItem) => {
  if (props.disabled || item.disabled || item.value === props.modelValue) return
  emit('update:modelValue', item.value)
}
</script>
