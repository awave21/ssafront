<template>
  <div class="flex flex-wrap items-center gap-1.5">
    <button
      type="button"
      class="rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors"
      :class="
        allActive
          ? 'border-primary bg-primary/10 text-foreground'
          : 'border-border bg-background text-muted-foreground hover:bg-muted'
      "
      :title="allActive ? 'Все типы видны' : 'Показать все типы'"
      @click="$emit('reset')"
    >
      Все · {{ totalCount }}
    </button>
    <button
      v-for="entry in entries"
      :key="entry.type"
      type="button"
      class="group inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] transition-all"
      :class="
        entry.active
          ? 'border-transparent text-foreground shadow-sm'
          : 'border-border bg-background text-muted-foreground opacity-60 hover:opacity-100'
      "
      :style="entry.active ? { backgroundColor: hexWithAlpha(entry.color, 0.18), borderColor: entry.color } : {}"
      :title="entry.active ? `Скрыть: ${entry.label}` : `Показать только: ${entry.label}`"
      @click="$emit('toggle', entry.type)"
    >
      <span
        class="h-2 w-2 rounded-full"
        :style="{ backgroundColor: entry.color }"
      />
      <span class="font-medium">{{ entry.label }}</span>
      <span class="rounded bg-muted/70 px-1 text-[10px] tabular-nums text-muted-foreground">
        {{ entry.count }}
      </span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { colorForType, labelForType } from './colors'

const props = defineProps<{
  /** Счётчики узлов по entity_type. */
  counts: Record<string, number>
  /** Текущий набор видимых типов. null/empty = все видны. */
  selected: string[] | null
}>()

defineEmits<{
  (e: 'toggle', type: string): void
  (e: 'reset'): void
}>()

const allActive = computed(() => !props.selected || props.selected.length === 0)

const totalCount = computed(() =>
  Object.values(props.counts).reduce((a, b) => a + b, 0),
)

const entries = computed(() => {
  const sel = new Set(props.selected ?? [])
  return Object.entries(props.counts)
    .map(([type, count]) => ({
      type,
      count,
      label: labelForType(type),
      color: colorForType(type),
      active: allActive.value || sel.has(type),
    }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label))
})

const hexWithAlpha = (color: string, alpha: number): string => {
  if (color.startsWith('hsl')) {
    return color.replace(')', ` / ${alpha})`).replace('hsl(', 'hsla(')
  }
  if (color.startsWith('rgb')) return color
  const h = color.replace('#', '')
  const full = h.length === 3 ? h.split('').map((c) => c + c).join('') : h
  const r = parseInt(full.slice(0, 2), 16)
  const g = parseInt(full.slice(2, 4), 16)
  const b = parseInt(full.slice(4, 6), 16)
  return `rgba(${r},${g},${b},${alpha})`
}
</script>
