<template>
  <aside class="flex flex-col gap-2 rounded-lg border border-border bg-card/95 p-3 shadow-xl backdrop-blur-md w-80">
    <div class="flex items-center justify-between gap-2">
      <h4 class="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
        Покрытие: Возражения × Услуги
      </h4>
      <button
        type="button"
        class="text-[10px] text-muted-foreground hover:text-foreground"
        @click="$emit('close')"
      >
        ✕
      </button>
    </div>

    <p class="text-[10px] leading-snug text-muted-foreground">
      Пустые ячейки — экспертные дыры: добавьте тактику для этого возражения и услуги.
    </p>

    <div v-if="loading" class="text-[11px] text-muted-foreground">Загрузка…</div>
    <div v-else-if="error" class="rounded-md border border-destructive/40 bg-destructive/10 px-2 py-1.5 text-[10px]">
      {{ error }}
    </div>
    <div v-else-if="!data?.objections.length" class="rounded-md border border-dashed border-border p-2 text-[11px] text-muted-foreground">
      Сначала добавьте Objection-сущности в
      <a :href="libraryHref" target="_blank" class="underline">библиотеку</a>.
    </div>
    <div v-else-if="!data.services.length" class="rounded-md border border-dashed border-border p-2 text-[11px] text-muted-foreground">
      В узлах пока нет ссылок на услуги.
    </div>
    <div v-else class="max-h-[50vh] overflow-auto rounded-md border border-border">
      <table class="w-full border-collapse text-[10px]">
        <thead class="sticky top-0 bg-muted">
          <tr>
            <th class="border border-border px-1.5 py-1 text-left font-medium">Возражение</th>
            <th
              v-for="s in data.services"
              :key="s"
              class="border border-border px-1.5 py-1 text-left font-medium"
            >
              {{ serviceLabel(s) }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="o in data.objections" :key="o.id">
            <td class="border border-border px-1.5 py-1 font-medium">
              {{ o.name }}
            </td>
            <td
              v-for="s in data.services"
              :key="s"
              class="border border-border px-1.5 py-1 text-center"
              :class="cellClass(o.id, s)"
            >
              {{ cellCount(o.id, s) || '—' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useScriptFlows } from '~/composables/useScriptFlows'
import { getReadableErrorMessage } from '~/utils/api-errors'
import type { ScriptFlowKgCoverageResult } from '~/types/scriptFlow'

const props = defineProps<{
  agentId: string
  /** Названия услуг, чтобы показать вместо id. */
  serviceLabels?: Record<string, string>
}>()

defineEmits<{ close: [] }>()

const { getKgCoverage } = useScriptFlows(props.agentId)

const data = ref<ScriptFlowKgCoverageResult | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

const load = async () => {
  loading.value = true
  error.value = null
  try {
    data.value = await getKgCoverage()
  } catch (e: unknown) {
    error.value = getReadableErrorMessage(e, 'Не удалось загрузить покрытие')
  } finally {
    loading.value = false
  }
}

const cellMap = computed<Record<string, number>>(() => {
  const acc: Record<string, number> = {}
  for (const c of data.value?.cells ?? []) {
    acc[`${c.objection_id}|${c.service_id}`] = c.tactic_count
  }
  return acc
})

const cellCount = (objectionId: string, serviceId: string): number =>
  cellMap.value[`${objectionId}|${serviceId}`] || 0

const cellClass = (objectionId: string, serviceId: string): string => {
  const n = cellCount(objectionId, serviceId)
  if (n === 0) return 'bg-destructive/10 text-destructive'
  if (n < 2) return 'bg-amber-500/10 text-amber-700 dark:text-amber-400'
  return 'bg-primary/10 text-primary'
}

const serviceLabel = (id: string): string => {
  if (id === '__any__') return 'Любая'
  return props.serviceLabels?.[id] || id.slice(0, 6)
}

const libraryHref = computed(() => `/agents/${props.agentId}/scripts/library`)

onMounted(load)
watch(() => props.agentId, load)
</script>
