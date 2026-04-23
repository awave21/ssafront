<template>
  <TacticCard v-if="role === 'tactic'" v-bind="passthrough" />
  <QuestionCard v-else-if="role === 'question'" v-bind="passthrough" />
  <CatalogRuleCard v-else v-bind="passthrough" />
</template>

<script setup lang="ts">
import { computed, inject, type ComputedRef } from 'vue'
import type { ScriptFlowCoverageIssue, ScriptFlowToolUsageNode, ScriptNodeData } from '~/types/scriptFlow'
import { inferNodeRole } from '~/utils/scriptFlowNodeRole'
import TacticCard from './cards/TacticCard.vue'
import QuestionCard from './cards/QuestionCard.vue'
import CatalogRuleCard from './cards/CatalogRuleCard.vue'

const props = defineProps<{
  id: string
  data: ScriptNodeData & { content?: string }
  selected?: boolean
}>()

const role = computed(() => inferNodeRole(props.data))

const orphanIds = inject<ComputedRef<Set<string>>>(
  'flowOrphanNodeIds',
  computed(() => new Set<string>()),
)

const covByNode = inject<ComputedRef<Record<string, ScriptFlowCoverageIssue[]>>>(
  'flowCoverageNodeIssues',
  computed(() => ({})),
)

const runtimeUsageByNode = inject<ComputedRef<Record<string, ScriptFlowToolUsageNode>>>(
  'flowRuntimeUsageByNode',
  computed(() => ({})),
)

const warnOrphan = computed(() => orphanIds.value.has(props.id))

const warnCoverage = computed(() => (covByNode.value[props.id]?.length ?? 0) > 0)

const runtimeUsage = computed(() => runtimeUsageByNode.value[props.id] ?? null)

const passthrough = computed(() => ({
  id: props.id,
  data: props.data,
  selected: props.selected,
  warnOrphan: warnOrphan.value,
  warnCoverage: warnCoverage.value,
  runtimeUsage: runtimeUsage.value,
}))
</script>
