<template>
  <div class="flex min-h-0 flex-1 flex-col gap-4 overflow-auto p-4 text-xs">
    <div class="rounded-2xl border border-border/80 bg-background px-4 py-3 text-[11px] leading-relaxed text-muted-foreground shadow-sm">
      Это удобный режим для эксперта: шаги сценария видны как playbook.
      Здесь проще описывать, когда использовать ответ, что сказать клиенту и каким вопросом двигать разговор дальше.
    </div>
    <div class="grid gap-3 sm:grid-cols-3">
      <div class="rounded-xl border border-border/80 bg-background px-4 py-3 shadow-sm">
        <p class="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Всего шагов</p>
        <p class="mt-1 text-lg font-semibold text-foreground">{{ tactics.length }}</p>
      </div>
      <div class="rounded-xl border border-border/80 bg-background px-4 py-3 shadow-sm">
        <p class="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Вопросы и ветки</p>
        <p class="mt-1 text-lg font-semibold text-foreground">{{ questionStepCount }}</p>
      </div>
      <div class="rounded-xl border border-border/80 bg-background px-4 py-3 shadow-sm">
        <p class="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Ответы и переходы</p>
        <p class="mt-1 text-lg font-semibold text-foreground">{{ tacticStepCount }}</p>
      </div>
    </div>
    <div class="flex flex-wrap items-center gap-3">
      <input
        v-model="filter"
        type="search"
        placeholder="Поиск по шагу, ситуации или примеру ответа..."
        class="max-w-xs rounded-xl border border-border/80 bg-background px-3 py-2 text-xs shadow-sm"
      >
      <span class="text-muted-foreground">{{ tactics.length }} шагов сценария общения</span>
    </div>
    <div class="overflow-hidden rounded-2xl border border-border/80 bg-background shadow-sm">
      <table class="w-full border-collapse text-left">
        <thead class="bg-muted/40 text-[10px] uppercase tracking-wide text-muted-foreground">
          <tr>
            <th class="px-2 py-2">Тип шага</th>
            <th class="px-2 py-2">Название</th>
            <th class="px-2 py-2">Суть шага</th>
            <th class="px-2 py-2">Этап</th>
            <th class="px-2 py-2">Что дальше</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in filteredTactics" :key="row.id" class="border-t border-border hover:bg-muted/30">
            <td class="px-2 py-2">{{ row.kindLabel }}</td>
            <td class="px-2 py-2 font-medium">{{ row.title }}</td>
            <td class="max-w-[280px] truncate px-2 py-2 text-muted-foreground">{{ row.preview }}</td>
            <td class="px-2 py-2">{{ row.stage }}</td>
            <td class="px-2 py-2 text-muted-foreground">{{ row.outcomeHint }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { CONVERSATION_STAGES, NODE_TYPES } from '~/types/scriptFlow'
import type { ConversationStage } from '~/types/scriptFlow'

const props = defineProps<{
  flowDefinition: Record<string, unknown>
}>()

const filter = ref('')

type Row = {
  id: string
  kind: string
  kindLabel: string
  title: string
  preview: string
  stage: string
   outcomeHint: string
}

const kindLabel = (nt: string) => {
  const labels: Record<string, string> = {
    trigger: 'Начало разговора',
    expertise: 'Что сказать',
    question: 'Что спросить',
    condition: 'Ветка ответа',
    goto: 'Переход к теме',
    end: 'Итог разговора',
  }
  return labels[nt] || NODE_TYPES.find((t) => t.value === nt)?.label || nt
}

const tactics = computed<Row[]>(() => {
  const nodes = props.flowDefinition?.nodes
  if (!Array.isArray(nodes)) return []
  const tacticTypes = new Set(['trigger', 'expertise', 'question', 'condition', 'goto', 'end'])
  const rows: Row[] = []
  for (const raw of nodes) {
    if (typeof raw !== 'object' || raw === null) continue
    const n = raw as { id?: string; data?: Record<string, unknown> }
    const id = typeof n.id === 'string' ? n.id : ''
    const d = (n.data && typeof n.data === 'object') ? n.data : {}
    const nt = String(d.node_type ?? '')
    if (!tacticTypes.has(nt)) continue
    const title = String(d.title ?? d.label ?? id).trim() || id
    const situation = String(d.situation ?? '').trim()
    const approach = String(d.approach ?? '').trim()
    const gq = String(d.good_question ?? '').trim()
    const finalAction = String(d.final_action ?? '').trim()
    const ruleAction = String(d.rule_action ?? '').trim()
    const preview = situation || approach || gq || '—'
    const outcomeHint = gq || finalAction || ruleAction || 'Следующий шаг по ветке'
    const st = d.stage as ConversationStage | undefined
    const stageLabel = st
      ? (CONVERSATION_STAGES.find((s) => s.value === st)?.label ?? st)
      : '—'
    rows.push({
      id,
      kind: nt,
      kindLabel: kindLabel(nt),
      title,
      preview,
      stage: stageLabel,
      outcomeHint,
    })
  }
  return rows
})

const questionStepCount = computed(() =>
  tactics.value.filter(r => r.kind === 'question' || r.kind === 'condition').length,
)

const tacticStepCount = computed(() =>
  tactics.value.filter(r => ['trigger', 'expertise', 'goto', 'end'].includes(r.kind)).length,
)

const filteredTactics = computed(() => {
  const q = filter.value.trim().toLowerCase()
  if (!q) return tactics.value
  return tactics.value.filter(
    (r) =>
      r.title.toLowerCase().includes(q)
      || r.preview.toLowerCase().includes(q)
      || r.kind.includes(q)
      || r.kindLabel.toLowerCase().includes(q),
  )
})
</script>
