<template>
  <div
    class="dashed-border-card relative flex flex-col overflow-visible rounded-[24px] border border-sky-300/80 bg-card/98 shadow-[0_10px_30px_rgba(14,165,233,0.08)] transition-all duration-200"
    :class="[
      isSelected ? 'ring-2 ring-sky-400/35 shadow-[0_22px_46px_rgba(14,165,233,0.16)] -translate-y-1 scale-[1.01]' : 'hover:-translate-y-1 hover:shadow-[0_18px_36px_rgba(14,165,233,0.12)]',
      props.warnOrphan ? 'ring-2 ring-amber-500/45' : '',
      props.warnCoverage ? 'ring-2 ring-destructive/50' : '',
    ]"
    :style="{ minWidth: '224px', maxWidth: '312px' }"
  >
    <FlowN8nConnector
      v-if="!standalone"
      :node-id="id"
      handle-type="target"
      handle-id="target"
      :connect-position="Position.Left"
      accent="#0ea5e9"
      :highlight-line="isSelected"
      side="left"
    />

    <div class="flex items-center gap-2 rounded-t-[24px] border-b border-white/60 bg-[linear-gradient(180deg,rgba(14,165,233,0.16),rgba(14,165,233,0.08))] px-3.5 py-2.5">
      <span class="text-sm">📋</span>
      <div class="flex-1 min-w-0">
        <span class="block truncate text-[12px] font-semibold text-foreground">{{ cardTitle }}</span>
        <span class="text-[10px] text-muted-foreground">{{ entitySubtitle }}</span>
      </div>
      <KgReadinessBadge :count="kgLinkCount" :needs="false" />
    </div>

    <div class="space-y-2.5 rounded-b-[24px] px-3.5 py-3.5">
      <RuntimeUsageBadge :usage="props.runtimeUsage" />
      <div v-if="rulePreview.condition || rulePreview.action" class="space-y-1">
        <p v-if="rulePreview.condition" class="text-[10px] leading-relaxed text-foreground/90"><span class="text-muted-foreground">Если:</span> {{ rulePreview.condition }}</p>
        <p v-if="rulePreview.action" class="text-[10px] leading-relaxed text-foreground/90"><span class="text-muted-foreground">То:</span> {{ rulePreview.action }}</p>
      </div>
      <p v-if="profilePreview" class="border-t border-border/60 pt-2 text-[10px] leading-relaxed text-muted-foreground line-clamp-4">
        {{ profilePreview }}
      </p>
      <p v-else class="text-[10px] italic text-muted-foreground">Выберите сотрудника или услугу справа</p>
    </div>

    <FlowN8nConnector
      v-if="!standalone"
      :node-id="id"
      handle-type="source"
      handle-id="source"
      :connect-position="Position.Right"
      accent="#0ea5e9"
      :highlight-line="isSelected"
      side="right"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, inject, ref, type Ref } from 'vue'
import { Position } from '@vue-flow/core'
import FlowN8nConnector from './FlowN8nConnector.vue'
import type { ScriptNodeData, ScriptFlowToolUsageNode } from '~/types/scriptFlow'
import { isStandaloneCatalogRule } from '~/utils/scriptFlowNodeRole'
import KgReadinessBadge from './KgReadinessBadge.vue'
import RuntimeUsageBadge from './RuntimeUsageBadge.vue'

const props = defineProps<{
  id: string
  data: ScriptNodeData & { content?: string }
  selected?: boolean
  warnOrphan?: boolean
  warnCoverage?: boolean
  runtimeUsage?: ScriptFlowToolUsageNode | null
}>()

const specialistById = inject<Ref<Record<string, { information?: string | null }>> | undefined>(
  'catalogSpecialistMap',
  undefined,
)
const serviceById = inject<Ref<Record<string, { description?: string | null }>> | undefined>(
  'catalogServiceMap',
  undefined,
)

const inspectorNodeId = inject<Ref<string | null>>('inspectorNodeId', ref(null))
const flowCanvasSelectedId = inject<Ref<string | null>>('flowCanvasSelectedId', ref(null))
const isSelected = computed(() =>
  props.selected
  || inspectorNodeId.value === props.id
  || flowCanvasSelectedId.value === props.id,
)

const standalone = computed(() => isStandaloneCatalogRule(props.data))

const cardTitle = computed(() =>
  String(props.data.title ?? props.data.label ?? 'Правило клиники').trim() || 'Правило клиники',
)

const entitySubtitle = computed(() => {
  const et = String(props.data.entity_type ?? 'employee')
  const label = et === 'service' ? 'Для услуги' : et === 'employee' ? 'Для сотрудника' : 'Для сущности'
  return props.data.entity_id ? `${label} · ${String(props.data.entity_id).slice(0, 8)}…` : label
})

const rulePreview = computed(() => ({
  condition: String(props.data.rule_condition ?? '').trim(),
  action: String(props.data.rule_action ?? '').trim(),
}))

const profilePreview = computed(() => {
  const et = props.data.entity_type
  const eid = props.data.entity_id
  if (!eid || typeof eid !== 'string') return ''
  if (et === 'service') {
    const row = serviceById?.value?.[eid]
    return row?.description ? String(row.description).trim().slice(0, 280) : ''
  }
  const row = specialistById?.value?.[eid]
  return row?.information ? String(row.information).trim().slice(0, 280) : ''
})

const kgLinkCount = computed(() => {
  const kg = props.data.kg_links
  if (!kg || typeof kg !== 'object') return 0
  let n = 0
  if (Array.isArray(kg.motive_ids)) n += kg.motive_ids.length
  if (Array.isArray(kg.argument_ids)) n += kg.argument_ids.length
  if (Array.isArray(kg.objection_ids)) n += kg.objection_ids.length
  return n
})
</script>

<style scoped>
.dashed-border-card {
  border-style: dashed;
}
</style>
