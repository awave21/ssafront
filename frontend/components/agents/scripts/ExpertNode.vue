<template>
  <UniformNode
    :id="props.id"
    :data="props.data"
    :selected="props.selected"
    :warn-orphan="warnOrphan"
    :warn-coverage="warnCoverage"
    :runtime-usage="runtimeUsage"
  />
</template>

<script setup lang="ts">
import { computed, inject, type Ref } from 'vue'
import type { ScriptFlowCoverageIssue, ScriptFlowToolUsageNode, ScriptNodeData } from '~/types/scriptFlow'
import UniformNode from './cards/UniformNode.vue'

const props = defineProps<{
  id: string
  data: ScriptNodeData & { content?: string }
  selected?: boolean
}>()

const orphanIds = inject<Ref<Set<string>>>(
  'flowOrphanNodeIds',
  computed(() => new Set<string>()),
)

const covByNode = inject<Ref<Record<string, ScriptFlowCoverageIssue[]>>>(
  'flowCoverageNodeIssues',
  computed(() => ({})),
)

const runtimeUsageByNode = inject<Ref<Record<string, ScriptFlowToolUsageNode>>>(
  'flowRuntimeUsageByNode',
  computed(() => ({})),
)

const warnOrphan = computed(() => orphanIds.value.has(props.id))
const warnCoverage = computed(() => (covByNode.value[props.id]?.length ?? 0) > 0)
const runtimeUsage = computed(() => runtimeUsageByNode.value[props.id] ?? null)
</script>
