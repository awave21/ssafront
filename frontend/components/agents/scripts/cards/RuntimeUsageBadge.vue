<template>
  <div
    v-if="usage"
    class="inline-flex max-w-full items-center gap-1 rounded-md border border-sky-200 bg-sky-50/90 px-1.5 py-0.5 text-[9px] font-medium text-sky-900 dark:border-sky-900/50 dark:bg-sky-950/40 dark:text-sky-100"
    :title="tooltip"
  >
    <span class="shrink-0">runtime</span>
    <span class="shrink-0">{{ usage.count }}x</span>
    <span v-if="lastSeenLabel" class="truncate text-sky-900/75 dark:text-sky-100/75">
      · {{ lastSeenLabel }}
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ScriptFlowToolUsageNode } from '~/types/scriptFlow'

const props = defineProps<{
  usage?: ScriptFlowToolUsageNode | null
}>()

const usage = computed(() => props.usage ?? null)

const lastSeenLabel = computed(() => {
  const raw = usage.value?.last_invoked_at
  if (!raw) return ''
  const iso = String(raw).trim()
  if (!iso) return ''
  const dt = new Date(iso)
  if (Number.isNaN(dt.getTime())) return ''
  return dt.toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
  })
})

const tooltip = computed(() => {
  if (!usage.value) return ''
  const parts = [`Применялось в рантайме: ${usage.value.count} раз`]
  if (usage.value.tactic_title)
    parts.push(String(usage.value.tactic_title))
  if (usage.value.last_invoked_at)
    parts.push(`Последний раз: ${usage.value.last_invoked_at}`)
  return parts.join(' · ')
})
</script>
