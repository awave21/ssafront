<template>
  <div
    class="relative flex flex-col overflow-visible rounded-[24px] border bg-card/98 shadow-[0_10px_30px_rgba(15,23,42,0.08)] transition-all duration-200"
    :class="[
      isSelected ? 'ring-2 ring-primary/30 shadow-[0_22px_46px_rgba(79,70,229,0.18)] -translate-y-1 scale-[1.01]' : 'hover:-translate-y-1 hover:shadow-[0_18px_36px_rgba(15,23,42,0.12)]',
      props.warnOrphan ? 'ring-2 ring-amber-500/45' : '',
      props.warnCoverage ? 'ring-2 ring-destructive/50' : '',
    ]"
    :style="{
      borderColor: isSelected ? accent : 'hsl(var(--border))',
      minWidth: '208px',
      maxWidth: '296px',
    }"
  >
    <Handle
      type="target"
      :position="Position.Left"
      id="target"
      class="!w-2.5 !h-2.5 !border-2 !border-background"
      :style="{ backgroundColor: accent }"
    />

    <div
      class="flex items-center gap-2 px-3.5 py-2.5 rounded-t-[24px] border-b border-white/60"
      :style="{ background: `linear-gradient(180deg, ${accent}1f, ${accent}10)` }"
    >
      <span class="text-sm leading-none select-none shrink-0">{{ typeEmoji }}</span>
      <div class="flex-1 min-w-0">
        <span class="block truncate text-[12px] font-semibold text-foreground">{{ cardTitle }}</span>
        <span class="text-[10px] text-muted-foreground">{{ typeLabel }}{{ stageBadge ? ` · ${stageBadge}` : '' }}{{ levelBadge }}</span>
      </div>
      <KgReadinessBadge
        :count="kgLinkCount"
        :needs="needsKgLinks && kgLinkCount === 0"
      />
    </div>

    <div class="space-y-2.5 px-3.5 py-3.5 rounded-b-[24px]">
      <RuntimeUsageBadge :usage="props.runtimeUsage" />

      <!-- Примеры реплик — главный блок для тактики -->
      <template v-if="phraseLines.length">
        <p class="text-[9px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">Как может звучать</p>
        <ul class="space-y-1">
          <li v-for="(line, i) in phraseLines" :key="i" class="rounded-2xl bg-white/75 px-3 py-2.5 text-[10px] leading-snug text-foreground/90 line-clamp-2 shadow-[inset_2px_0_0_var(--tw-shadow-color),0_6px_18px_rgba(15,23,42,0.04)]" :style="{ '--tw-shadow-color': accent }">
            «{{ line }}»
          </li>
        </ul>
      </template>
      <p v-else-if="hintMissingExamples" class="text-[10px] text-destructive/90">
        Добавьте хотя бы один пример реплики
      </p>
      <p class="text-[10px] leading-relaxed text-foreground/85 line-clamp-3">{{ bodySecondary }}</p>
      <div v-if="chipSummary.length" class="flex flex-wrap gap-1 pt-1">
        <span
          v-for="(c, i) in chipSummary"
          :key="i"
          class="inline-flex rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-[9px] font-medium text-indigo-800"
        >{{ c }}</span>
      </div>
      <p v-if="questionLine" class="text-[9px] text-amber-700 dark:text-amber-400 line-clamp-1">
        ❓ {{ questionLine }}
      </p>
    </div>
    <div
      class="flex items-center justify-between gap-1 border-t border-white/60 px-3.5 py-2.5 rounded-b-[24px]"
      :style="{ background: `linear-gradient(180deg, ${accent}08, rgba(255,255,255,0.72))` }"
    >
      <ReadinessTone :tone="readinessTone" />
      <span v-if="isEntry" class="text-[9px] text-muted-foreground flex items-center gap-0.5">
        <span class="w-1 h-1 rounded-full" :style="{ backgroundColor: accent }" />
        вход
      </span>
    </div>

    <Handle
      type="source"
      :position="Position.Right"
      id="source"
      class="!w-2.5 !h-2.5 !border-2 !border-background"
      :style="{ backgroundColor: accent }"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, inject, ref, type Ref } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import type { ScriptNodeData, NodeType, ConversationStage, ScriptFlowToolUsageNode } from '~/types/scriptFlow'
import { NODE_TYPE_COLORS, CONVERSATION_STAGES } from '~/types/scriptFlow'
import KgReadinessBadge from './KgReadinessBadge.vue'
import ReadinessTone from './ReadinessTone.vue'
import RuntimeUsageBadge from './RuntimeUsageBadge.vue'

const NODE_EMOJIS: Record<string, string> = {
  trigger: '⚡',
  expertise: '🧠',
  goto: '➡️',
  end: '🔴',
}

const NODE_LABELS: Record<string, string> = {
  trigger: 'Начало разговора',
  expertise: 'Что сказать',
  goto: 'Переход к теме',
  end: 'Итог разговора',
}

const props = defineProps<{
  id: string
  data: ScriptNodeData & { content?: string }
  selected?: boolean
  warnOrphan?: boolean
  warnCoverage?: boolean
  runtimeUsage?: ScriptFlowToolUsageNode | null
}>()

const inspectorNodeId = inject<Ref<string | null>>('inspectorNodeId', ref(null))
const isSelected = computed(() => props.selected || inspectorNodeId.value === props.id)

const nodeType = computed(() => (props.data.node_type as NodeType) || 'expertise')
const accent = computed(() => NODE_TYPE_COLORS[nodeType.value] || '#10b981')
const typeEmoji = computed(() => NODE_EMOJIS[nodeType.value] || '🎯')
const typeLabel = computed(() => NODE_LABELS[nodeType.value] || 'Что сказать')

const stageBadge = computed(() => {
  const s = props.data.stage as ConversationStage | null | undefined
  if (!s) return null
  return CONVERSATION_STAGES.find((st) => st.value === s)?.label ?? s
})

const levelBadge = computed(() => {
  const lv = props.data.level
  return typeof lv === 'number' && lv > 1 ? ` · L${lv}` : ''
})

const cardTitle = computed(() => {
  const t = String(props.data.title ?? props.data.label ?? '').trim()
  return t || typeLabel.value
})

const phraseLines = computed(() => {
  const nt = nodeType.value
  const p = nt === 'trigger' && Array.isArray(props.data.client_phrase_examples)
    ? props.data.client_phrase_examples
    : props.data.example_phrases
  if (!Array.isArray(p)) return []
  return (p as string[]).map((s) => String(s).trim()).filter(Boolean).slice(0, 4)
})

const hintMissingExamples = computed(() =>
  ['expertise', 'trigger'].includes(nodeType.value) && phraseLines.value.length === 0)

const situationLine = computed(() => String(props.data.situation ?? '').trim())

const bodySecondary = computed(() => {
  if (nodeType.value === 'end') {
    const fa = String(props.data.final_action ?? '').trim()
    if (fa) return fa
    return 'Здесь завершается эта ветка разговора'
  }
  if (nodeType.value === 'trigger') {
    const wr = String(props.data.when_relevant ?? props.data.situation ?? '').trim()
    if (wr) return wr
  }
  const s = situationLine.value
  if (s) return s
  const ap = String(props.data.approach ?? '').trim()
  if (ap) return ap
  return 'Добавьте смысл шага справа →'
})

const questionLine = computed(() => String(props.data.good_question ?? '').trim())

const isEntry = computed(() =>
  props.data.node_type === 'trigger'
  && (props.data.is_flow_entry ?? props.data.is_entry_point !== false))

const kgLinks = computed(() => props.data.kg_links ?? {})

const kgLinkCount = computed(() => {
  const kg = kgLinks.value
  if (!kg || typeof kg !== 'object') return 0
  let total = 0
  if (Array.isArray((kg as { motive_ids?: string[] }).motive_ids)) total += kg.motive_ids!.length
  if (Array.isArray((kg as { argument_ids?: string[] }).argument_ids)) total += kg.argument_ids!.length
  if (Array.isArray((kg as { proof_ids?: string[] }).proof_ids)) total += kg.proof_ids!.length
  if (Array.isArray((kg as { objection_ids?: string[] }).objection_ids)) total += kg.objection_ids!.length
  if (Array.isArray((kg as { constraint_ids?: string[] }).constraint_ids)) total += kg.constraint_ids!.length
  if ((kg as { outcome_id?: string | null }).outcome_id) total += 1
  return total
})

const needsKgLinks = computed(() => ['expertise', 'question', 'end'].includes(nodeType.value))

const chipSummary = computed(() => {
  const kg = kgLinks.value as Record<string, unknown>
  const parts: string[] = []
  const n = (x: unknown) => (Array.isArray(x) ? x.length : 0)
  const m = n(kg.motive_ids)
  const a = n(kg.argument_ids)
  const o = n(kg.objection_ids)
  if (m) parts.push(`мотивов: ${m}`)
  if (a) parts.push(`аргументов: ${a}`)
  if (o) parts.push(`возражений: ${o}`)
  return parts
})

const readinessTone = computed(() => {
  if (hintMissingExamples.value) return 'danger' as const
  if (needsKgLinks.value && kgLinkCount.value === 0) return 'warn' as const
  return 'ok' as const
})
</script>
