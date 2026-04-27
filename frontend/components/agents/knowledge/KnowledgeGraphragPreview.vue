<template>
  <div class="relative h-[min(70vh,560px)] w-full min-h-[320px] rounded-lg border border-border bg-muted/20">
    <VueFlow
      :id="FLOW_ID"
      :nodes="flowNodes"
      :edges="flowEdges"
      :nodes-draggable="true"
      :nodes-connectable="false"
      :elements-selectable="true"
      :default-edge-options="{ type: 'smoothstep', animated: false }"
      :connection-line-type="ConnectionLineType.Bezier"
      class="knowledge-graphrag-canvas h-full w-full bg-background/80"
    >
      <Background :gap="20" pattern-color="#cbd5e1" :size="1" />
      <Controls position="bottom-right" />
      <MiniMap
        class="!m-3 rounded border border-border bg-card/90"
        style="width: 140px; height: 100px;"
        pannable
        zoomable
        :mask-color="'rgba(0,0,0,0.08)'"
      />
    </VueFlow>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, watch } from 'vue'
import { ConnectionLineType, useVueFlow, VueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/controls/dist/style.css'
import '@vue-flow/minimap/dist/style.css'

const FLOW_ID = 'knowledge-graphrag-preview'

export type GraphPreviewNode = {
  id: string
  label: string
  type: string
  description: string
}

export type GraphPreviewRelation = {
  id: string
  source: string
  target: string
  label: string
}

const props = defineProps<{
  nodes: GraphPreviewNode[]
  relations: GraphPreviewRelation[]
}>()

const flowNodes = computed(() => {
  const list = props.nodes
  const n = list.length || 1
  const r = Math.max(200, 36 + n * 10)
  return list.map((node, i) => {
    const angle = (2 * Math.PI * i) / n
    return {
      id: node.id,
      label: node.label,
      position: {
        x: 60 + r + r * 0.8 * Math.cos(angle),
        y: 60 + r + r * 0.8 * Math.sin(angle),
      },
      style: { width: '148px', fontSize: '11px' },
    }
  })
})

const flowEdges = computed(() =>
  props.relations.map((e) => ({
    id: e.id || `rel-${e.source}-${e.target}`,
    source: e.source,
    target: e.target,
    label: e.label || undefined,
  })),
)

const { fitView } = useVueFlow(FLOW_ID)

watch(
  () => [props.nodes.length, props.relations.length],
  async () => {
    if (!props.nodes.length) return
    await nextTick()
    fitView({ padding: 0.18, duration: 280 })
  },
  { immediate: true },
)
</script>
