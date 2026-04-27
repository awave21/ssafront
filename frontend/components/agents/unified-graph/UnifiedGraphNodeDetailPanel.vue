<template>
  <KnowledgeSheetShell
    :open="!!node"
    title="Детали узла графа"
    :subtitle="node?.title || node?.graph_node_id || ''"
    size="md"
    @close="$emit('close')"
    @update:open="(v) => !v && $emit('close')"
  >
    <div v-if="node" class="space-y-4 p-4">
      <div class="flex flex-wrap gap-1.5">
        <Badge variant="secondary">{{ originLabel(node.origin_slice) }}</Badge>
        <Badge variant="outline">{{ node.entity_type }}</Badge>
        <Badge v-if="node.provenance_tier" variant="outline" class="font-normal">
          {{ node.provenance_tier }}
        </Badge>
      </div>

      <p v-if="plainDescription" class="text-sm leading-relaxed text-muted-foreground">
        {{ plainDescription }}
      </p>

      <div v-if="node.domain_entity_id" class="space-y-1">
        <p class="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Domain entity</p>
        <code class="block break-all rounded-md bg-muted px-2 py-1.5 text-xs">{{ node.domain_entity_id }}</code>
      </div>

      <div class="space-y-1">
        <p class="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">graph_node_id</p>
        <code class="block break-all rounded-md bg-muted px-2 py-1.5 text-xs">{{ node.graph_node_id }}</code>
      </div>

      <div v-if="hasProperties" class="space-y-1">
        <p class="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Свойства</p>
        <pre class="max-h-48 overflow-auto rounded-md border border-border bg-muted/40 p-2 text-[11px] leading-relaxed">{{ propertiesJson }}</pre>
      </div>

      <div v-if="outgoing.length" class="space-y-2">
        <p class="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Исходящие связи</p>
        <ul class="space-y-2 text-sm">
          <li v-for="(r, idx) in outgoing" :key="`out-${idx}-${r.target_graph_node_id}-${r.relation_type}`">
            <button
              type="button"
              class="block w-full cursor-pointer rounded-md border border-border bg-muted/30 px-2.5 py-2 text-left transition-all hover:border-slate-300 hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/60"
              @click="openRelatedNode(r.target_graph_node_id)"
            >
              <span class="font-medium text-foreground">{{ r.relation_type }}</span>
              <span class="text-muted-foreground"> → </span>
              <span class="text-sm font-medium text-foreground">
                {{ titleFor(r.target_graph_node_id) }}
                <span aria-hidden="true">›</span>
              </span>
              <span v-if="r.origin_slice" class="mt-0.5 block text-[10px] text-muted-foreground">
                {{ originLabel(r.origin_slice) }}
                <span v-if="r.weight != null"> · вес {{ r.weight }}</span>
              </span>
            </button>
          </li>
        </ul>
      </div>

      <div v-if="incoming.length" class="space-y-2">
        <p class="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Входящие связи</p>
        <ul class="space-y-2 text-sm">
          <li v-for="(r, idx) in incoming" :key="`in-${idx}-${r.source_graph_node_id}-${r.relation_type}`">
            <button
              type="button"
              class="block w-full cursor-pointer rounded-md border border-border bg-muted/30 px-2.5 py-2 text-left transition-all hover:border-slate-300 hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500/60"
              @click="openRelatedNode(r.source_graph_node_id)"
            >
              <span class="text-sm font-medium text-foreground">
                {{ titleFor(r.source_graph_node_id) }}
                <span aria-hidden="true">›</span>
              </span>
              <span class="text-muted-foreground"> —{{ r.relation_type }}→ </span>
              <span class="text-foreground">этот узел</span>
              <span v-if="r.origin_slice" class="mt-0.5 block text-[10px] text-muted-foreground">
                {{ originLabel(r.origin_slice) }}
              </span>
            </button>
          </li>
        </ul>
      </div>
    </div>

    <template #footer>
      <div class="w-full" />
    </template>
  </KnowledgeSheetShell>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import Badge from '~/components/ui/badge/Badge.vue'
import KnowledgeSheetShell from '~/components/knowledge/KnowledgeSheetShell.vue'
import type { UnifiedGraphNodeDto, UnifiedGraphPreview } from '../../../types/unifiedGraph'

const props = defineProps<{
  node: UnifiedGraphNodeDto | null
  preview: UnifiedGraphPreview | null
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'select-node', node: UnifiedGraphNodeDto): void
}>()

const titleById = computed(() => {
  const m = new Map<string, string>()
  for (const n of props.preview?.nodes ?? [])
    m.set(n.graph_node_id, (n.title || n.graph_node_id).trim() || n.graph_node_id)
  return m
})

const titleFor = (id: string) => titleById.value.get(id) ?? id
const nodeById = computed(() => new Map((props.preview?.nodes ?? []).map((n) => [n.graph_node_id, n])))
const HTML_TAG_RE = /<[^>]+>/g
const toPlainText = (value: string | null | undefined) =>
  (value || '').replace(HTML_TAG_RE, ' ').replace(/\s+/g, ' ').trim()

const outgoing = computed(() => {
  if (!props.node || !props.preview) return []
  return props.preview.relations.filter((r) => r.source_graph_node_id === props.node!.graph_node_id)
})

const incoming = computed(() => {
  if (!props.node || !props.preview) return []
  return props.preview.relations.filter((r) => r.target_graph_node_id === props.node!.graph_node_id)
})

const hasProperties = computed(() => {
  const p = props.node?.properties
  return p != null && Object.keys(p).length > 0
})

const propertiesJson = computed(() => {
  try {
    return JSON.stringify(props.node?.properties ?? {}, null, 2)
  }
  catch {
    return String(props.node?.properties)
  }
})
const plainDescription = computed(() => toPlainText(props.node?.description))

const originLabel = (k: string) => {
  const m: Record<string, string> = {
    sqns: 'SQNS',
    knowledge: 'Файлы',
    directory: 'Справочники',
    script_bridge: 'Сценарии',
  }
  return m[k] ?? k
}

const openRelatedNode = (graphNodeId: string) => {
  const next = nodeById.value.get(graphNodeId)
  if (next) emit('select-node', next)
}
</script>
