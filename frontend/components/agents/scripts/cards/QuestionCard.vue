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
      minWidth: isCondition ? '236px' : '208px',
      maxWidth: isCondition ? '336px' : '296px',
    }"
  >
    <FlowN8nConnector
      :node-id="id"
      handle-type="target"
      handle-id="target"
      :connect-position="Position.Left"
      :accent="accent"
      :highlight-line="isSelected"
      side="left"
    />

    <div
      class="flex items-center gap-2 px-3.5 py-2.5 rounded-t-[24px] border-b border-white/60"
      :style="{ background: `linear-gradient(180deg, ${accent}1f, ${accent}10)` }"
    >
      <span class="text-sm leading-none">{{ typeEmoji }}</span>
      <div class="flex-1 min-w-0">
        <span class="block truncate text-[12px] font-semibold text-foreground">{{ cardTitle }}</span>
        <span class="text-[10px] text-muted-foreground">{{ typeLabel }}{{ stageBadge ? ` · ${stageBadge}` : '' }}</span>
      </div>
      <KgReadinessBadge :count="kgLinkCount" :needs="needsKgLinks && kgLinkCount === 0" />
    </div>

    <template v-if="isCondition">
      <div class="space-y-2.5 px-3.5 py-3.5 rounded-b-[24px]">
        <RuntimeUsageBadge :usage="props.runtimeUsage" />
        <p v-if="situationLine" class="mb-1 text-[10px] leading-relaxed text-muted-foreground line-clamp-2">{{ situationLine }}</p>
        <div
          v-for="(br, i) in branchList"
          :key="br.id"
          class="group relative flex min-h-[38px] items-center gap-1.5 rounded-2xl px-3 pr-2 shadow-[0_8px_20px_rgba(15,23,42,0.05)]"
          :style="{ background: `${accent}10`, boxShadow: `inset 2px 0 0 ${accent}88` }"
        >
          <span class="min-w-0 flex-1 text-[10px] font-medium leading-snug text-foreground/90 line-clamp-1">{{ String(br.label).trim() || `Ветка ${i + 1}` }}</span>
          <FlowN8nConnector
            :node-id="id"
            variant="inline"
            handle-type="source"
            :handle-id="branchHandleId(br.id)"
            :connect-position="Position.Right"
            :accent="accent"
            :highlight-line="isSelected"
            line-width-class="w-3"
            compact
          />
        </div>
        <div class="relative flex min-h-[38px] items-center gap-1.5 rounded-2xl bg-muted/35 px-3 pr-2 shadow-[0_8px_20px_rgba(15,23,42,0.04)]" style="box-shadow: inset 2px 0 0 hsl(var(--border));">
          <span class="min-w-0 flex-1 text-[10px] italic text-muted-foreground">По умолчанию</span>
          <FlowN8nConnector
            :node-id="id"
            variant="inline"
            handle-type="source"
            handle-id="cond-default"
            :connect-position="Position.Right"
            accent="hsl(var(--muted-foreground) / 0.85)"
            :highlight-line="isSelected"
            line-width-class="w-3"
            compact
          />
        </div>
      </div>
    </template>

    <template v-else>
      <div class="space-y-2.5 px-3.5 py-3.5 rounded-b-[24px]">
        <RuntimeUsageBadge :usage="props.runtimeUsage" />
        <p class="text-[10px] leading-relaxed text-foreground/85 line-clamp-3">{{ bodyPreview }}</p>
        <p v-if="questionLine" class="text-[10px] text-amber-700 dark:text-amber-400 line-clamp-2">❓ {{ questionLine }}</p>
      </div>
      <div class="flex items-center justify-between gap-1 border-t border-white/60 px-3.5 py-2.5 rounded-b-[24px]" :style="{ background: `linear-gradient(180deg, ${accent}08, rgba(255,255,255,0.72))` }">
        <ReadinessTone :tone="readinessTone" />
      </div>
      <FlowN8nConnector
        :node-id="id"
        handle-type="source"
        handle-id="source"
        :connect-position="Position.Right"
        :accent="accent"
        :highlight-line="isSelected"
        side="right"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, ref, type Ref } from 'vue'
import { Position } from '@vue-flow/core'
import FlowN8nConnector from './FlowN8nConnector.vue'
import type { FlowBranch, ScriptNodeData, NodeType, ConversationStage, ScriptFlowToolUsageNode } from '~/types/scriptFlow'
import { NODE_TYPE_COLORS, CONVERSATION_STAGES } from '~/types/scriptFlow'
import KgReadinessBadge from './KgReadinessBadge.vue'
import ReadinessTone from './ReadinessTone.vue'
import RuntimeUsageBadge from './RuntimeUsageBadge.vue'
import { branchSourceHandleId, normalizeConditionsToBranches } from '~/utils/scriptFlowNodeRole'

const branchHandleId = (id: string) => branchSourceHandleId(id)

const props = defineProps<{
  id: string
  data: ScriptNodeData & { content?: string }
  selected?: boolean
  warnOrphan?: boolean
  warnCoverage?: boolean
  runtimeUsage?: ScriptFlowToolUsageNode | null
}>()

const inspectorNodeId = inject<Ref<string | null>>('inspectorNodeId', ref(null))
const flowCanvasSelectedId = inject<Ref<string | null>>('flowCanvasSelectedId', ref(null))
const isSelected = computed(() =>
  props.selected
  || inspectorNodeId.value === props.id
  || flowCanvasSelectedId.value === props.id,
)

const nodeType = computed(() => (props.data.node_type as NodeType) || 'question')
const isCondition = computed(() => nodeType.value === 'condition')
const accent = computed(() => NODE_TYPE_COLORS[nodeType.value] || '#f59e0b')
const typeEmoji = computed(() => (nodeType.value === 'condition' ? '🔀' : '❓'))
const typeLabel = computed(() =>
  nodeType.value === 'condition' ? 'Если клиент отвечает по-разному' : 'Что спросить дальше')

const stageBadge = computed(() => {
  const s = props.data.stage as ConversationStage | null | undefined
  if (!s) return null
  return CONVERSATION_STAGES.find((st) => st.value === s)?.label ?? s
})

const cardTitle = computed(() => {
  const t = String(props.data.title ?? props.data.label ?? '').trim()
  return t || typeLabel.value
})

const branchList = computed((): FlowBranch[] =>
  normalizeConditionsToBranches(props.data.conditions),
)

const situationLine = computed(() =>
  String(
    props.data.node_type === 'condition'
      ? (props.data.routing_hint ?? props.data.situation ?? '')
      : (props.data.situation ?? ''),
  ).trim())

const bodyPreview = computed(() => {
  const q = String(props.data.good_question ?? '').trim()
  if (q) return q
  const why = String(props.data.why_we_ask ?? '').trim()
  if (why) return why
  const s = situationLine.value
  if (s) return s
  return 'Добавьте вопрос или логику ветки справа →'
})

const questionLine = computed(() => String(props.data.good_question ?? '').trim())

const kgLinkCount = computed(() => {
  const kg = props.data.kg_links
  if (!kg || typeof kg !== 'object') return 0
  let total = 0
  if (Array.isArray(kg.motive_ids)) total += kg.motive_ids.length
  if (Array.isArray(kg.argument_ids)) total += kg.argument_ids.length
  if (Array.isArray(kg.proof_ids)) total += kg.proof_ids.length
  if (Array.isArray(kg.objection_ids)) total += kg.objection_ids.length
  if (Array.isArray(kg.constraint_ids)) total += kg.constraint_ids.length
  if (kg.outcome_id) total += 1
  return total
})

const needsKgLinks = computed(() => true)

const readinessTone = computed(() => {
  if (nodeType.value === 'question' && !String(props.data.good_question ?? '').trim())
    return 'danger' as const
  if (needsKgLinks.value && kgLinkCount.value === 0) return 'warn' as const
  return 'ok' as const
})
</script>
