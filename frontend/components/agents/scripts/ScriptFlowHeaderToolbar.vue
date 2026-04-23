<template>
  <div
    class="flex min-w-0 flex-1 items-center gap-2 overflow-x-auto overflow-y-hidden py-0.5 [scrollbar-width:thin]"
    role="toolbar"
    aria-label="Поток эксперта"
  >
    <div class="flex min-w-0 flex-nowrap items-center gap-1.5">
      <span v-if="flow.flow_status === 'published'" class="shrink-0 text-[11px] text-muted-foreground">
        v{{ flow.published_version }}
      </span>
      <span v-if="dirtyLabel" class="max-w-[14rem] shrink-0 truncate text-[11px] text-amber-700 dark:text-amber-400">
        {{ dirtyLabel }}
      </span>
    </div>

    <div class="ml-auto flex shrink-0 flex-nowrap items-center gap-1.5 border-l border-border pl-2">
      <div
        v-if="toolUsageDisplay"
        class="flex max-w-[min(100vw-14rem,28rem)] shrink items-center gap-1.5"
      >
        <div
          class="flex min-w-0 items-center gap-1.5 rounded border border-sky-200 bg-sky-50/80 px-2 py-1 text-[11px] text-sky-950 dark:border-sky-900/50 dark:bg-sky-950/30 dark:text-sky-100"
          :title="toolUsageDisplay.disclaimer"
        >
          <span class="shrink-0 font-semibold">
            В рантайме: {{ toolUsageDisplay.calls }}
          </span>
          <span class="truncate text-sky-900/80 dark:text-sky-100/80">
            {{ toolUsageDisplay.summary }}
          </span>
        </div>
      </div>

      <div
        v-if="riskSummary"
        class="flex max-w-[min(100vw-12rem,20rem)] shrink items-center gap-1.5"
      >
        <span
          class="shrink-0 rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-tight"
          :class="riskPillClass"
          :title="riskTitle"
        >
          {{ riskBadgeText }}
        </span>
        <button
          type="button"
          class="shrink-0 rounded border border-border bg-background px-2 py-1 text-[11px] font-medium leading-none text-foreground hover:bg-muted"
          :title="riskTitle"
          @click="onReadiness"
        >
          Готовность
        </button>
      </div>

      <button
        v-if="flow.index_status === 'failed'"
        type="button"
        class="rounded border border-amber-300 bg-amber-50 px-2 py-1 text-[11px] font-medium leading-none text-amber-900 hover:bg-amber-100 disabled:opacity-50"
        :disabled="retrying"
        @click="onRetryIndex"
      >
        Повторить обучение
      </button>

      <button
        v-if="dirtyRepublish"
        type="button"
        class="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
        title="Переопубликовать черновик"
        @click="onPublish"
      >
        <RefreshCw class="h-3.5 w-3.5" />
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RefreshCw } from 'lucide-vue-next'
import type { ScriptFlowToolbarPayload } from '~/composables/useLayoutState'
import { coverageRiskBadgeLabel } from '~/utils/scriptFlowCoverageRisk'

const props = defineProps<ScriptFlowToolbarPayload>()

const flow = computed(() => props.flow)

const indexLabel = computed(() => {
  const s = props.flow?.index_status
  const labels: Record<string, string> = {
    idle: 'не начато',
    pending: 'в очереди',
    indexing: 'обновление',
    indexed: 'готово',
    failed: 'ошибка',
  }
  return labels[s ?? 'idle'] ?? s ?? '—'
})

const statusClass = computed(() => {
  switch (props.flow?.index_status) {
    case 'indexed':
      return 'border-emerald-200 bg-emerald-50 text-emerald-800'
    case 'pending':
    case 'indexing':
      return 'border-sky-200 bg-sky-50 text-sky-800'
    case 'failed':
      return 'border-destructive/40 bg-destructive/10 text-destructive'
    default:
      return 'border-border bg-muted/40 text-muted-foreground'
  }
})

const riskBadgeText = computed(() =>
  props.riskSummary ? coverageRiskBadgeLabel(props.riskSummary) : '',
)

const riskTitle = computed(() => {
  const s = props.riskSummary
  if (!s) return ''
  if (s.level === 'ok') return 'Критических проблем в таблице покрытия нет'
  return s.level === 'critical'
    ? `Критично: ${s.criticalCount} · публикация будет заблокирована`
    : `Предупреждения: ${s.warningCount} — публикация возможна`
})

const riskPillClass = computed(() => {
  switch (props.riskSummary?.level) {
    case 'ok':
      return 'border-emerald-200/80 bg-emerald-50 text-emerald-900 dark:border-emerald-900/40 dark:bg-emerald-950/40 dark:text-emerald-100'
    case 'warn':
      return 'border-amber-300 bg-amber-50 text-amber-950 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-100'
    case 'critical':
      return 'border-destructive/50 bg-destructive/15 text-destructive'
    default:
      return 'border-border'
  }
})

const toolUsageDisplay = computed(() => {
  const u = props.toolUsage
  if (!u || typeof u.approximate_flow_tool_calls !== 'number') return null
  let peakNote = ''
  const ds = u.daily_series
  if (Array.isArray(ds) && ds.length) {
    const mx = ds.reduce((a, b) => (b.count > a.count ? b : a), ds[0]!)
    peakNote = `Пик за период: ${mx.count} (${mx.date})`
  }
  const disclaimer = [u.disclaimer ?? '', peakNote].filter(Boolean).join(' · ')
  const topNodes = Array.isArray(u.top_node_refs) ? u.top_node_refs.filter(Boolean) : []
  const topNode = topNodes[0]
  const summary = topNode
    ? `${topNode.tactic_title || topNode.node_ref} · ${topNode.count}x${topNodes.length > 1 ? ` · top ${topNodes.length} узл.` : ''}`
    : `За ${typeof u.days === 'number' ? u.days : 7} дн.`
  return {
    calls: u.approximate_flow_tool_calls,
    days: typeof u.days === 'number' ? u.days : 7,
    disclaimer: disclaimer || undefined,
    summary,
  }
})

const dirtyLabel = computed(() => {
  if (props.flow?.flow_status !== 'published') return ''
  const meta = props.flow?.flow_metadata as Record<string, unknown> | undefined
  const snap = meta?.published_flow_definition
  if (!snap || typeof snap !== 'object') return ''
  try {
    const cur = JSON.stringify(props.flow?.flow_definition ?? {})
    const pub = JSON.stringify(snap)
    return cur !== pub ? 'Черновик отличается от опубликованного — переопубликуйте, чтобы обновить память ассистента' : ''
  }
  catch {
    return ''
  }
})

const dirtyRepublish = computed(
  () => Boolean(dirtyLabel.value && props.flow?.flow_status === 'published'),
)

</script>
