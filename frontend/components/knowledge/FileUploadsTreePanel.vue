<template>
  <div class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
    <div class="mb-3 flex items-center justify-between gap-3">
      <h3 class="text-sm font-bold text-slate-900">Папки</h3>
      <button
        type="button"
        class="inline-flex h-8 items-center gap-1 rounded-md border border-slate-200 bg-white px-2.5 text-xs font-semibold text-slate-700 transition-colors hover:bg-slate-50"
        @click="requestCreateRoot"
      >
        <Plus class="h-3.5 w-3.5" />
        Новая папка
      </button>
    </div>

    <div v-if="loading" class="flex justify-center py-8">
      <Loader2 class="h-5 w-5 animate-spin text-indigo-600" />
    </div>

    <div v-else-if="rows.length === 0" class="rounded-lg border border-dashed border-slate-200 bg-slate-50 p-5 text-center">
      <p class="text-sm font-medium text-slate-700">Папок пока нет</p>
      <button
        type="button"
        class="mt-3 inline-flex h-9 items-center rounded-md bg-indigo-600 px-4 text-sm font-bold text-white transition-colors hover:bg-indigo-700"
        @click="requestCreateRoot"
      >
        Создать первую папку
      </button>
    </div>

    <div v-else class="space-y-1">
      <button
        v-for="row in rows"
        :key="row.node.id"
        type="button"
        class="group flex w-full items-center gap-2 rounded-md px-2 py-2 text-left transition-colors"
        :class="selectedNodeId === row.node.id ? 'bg-indigo-50 text-indigo-700' : 'hover:bg-slate-50 text-slate-700'"
        :style="{ paddingLeft: `${row.depth * 18 + 8}px` }"
        @click="$emit('select', row.node.id)"
      >
        <Folder class="h-4 w-4 shrink-0" />
        <span class="truncate text-sm font-medium">{{ row.node.title }}</span>
        <span class="ml-auto shrink-0 text-[11px] text-slate-400">
          {{ row.childrenCount }}
        </span>
      </button>
    </div>

    <div v-if="selectedNode" class="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3">
      <p class="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Управление папкой</p>
      <div class="flex flex-wrap gap-1.5">
        <button
          type="button"
          class="inline-flex h-8 items-center gap-1 rounded-md border border-slate-200 bg-white px-2 text-xs font-medium text-slate-700 hover:bg-slate-50"
          @click="requestCreateChild"
        >
          <FolderPlus class="h-3.5 w-3.5" />
          Внутрь
        </button>
        <button
          type="button"
          class="inline-flex h-8 items-center gap-1 rounded-md border border-slate-200 bg-white px-2 text-xs font-medium text-slate-700 hover:bg-slate-50"
          @click="requestRename"
        >
          <Pencil class="h-3.5 w-3.5" />
          Переименовать
        </button>
        <button
          type="button"
          class="inline-flex h-8 items-center gap-1 rounded-md border border-slate-200 bg-white px-2 text-xs font-medium text-slate-700 hover:bg-slate-50"
          @click="$emit('move-up', selectedNode.id)"
        >
          <ArrowUp class="h-3.5 w-3.5" />
          Выше
        </button>
        <button
          type="button"
          class="inline-flex h-8 items-center gap-1 rounded-md border border-slate-200 bg-white px-2 text-xs font-medium text-slate-700 hover:bg-slate-50"
          @click="$emit('move-down', selectedNode.id)"
        >
          <ArrowDown class="h-3.5 w-3.5" />
          Ниже
        </button>
        <button
          type="button"
          class="inline-flex h-8 items-center gap-1 rounded-md border border-slate-200 bg-white px-2 text-xs font-medium text-slate-700 hover:bg-slate-50"
          @click="$emit('indent', selectedNode.id)"
        >
          <Indent class="h-3.5 w-3.5" />
          Вложить
        </button>
        <button
          type="button"
          class="inline-flex h-8 items-center gap-1 rounded-md border border-slate-200 bg-white px-2 text-xs font-medium text-slate-700 hover:bg-slate-50"
          @click="$emit('dedent', selectedNode.id)"
        >
          <Outdent class="h-3.5 w-3.5" />
          На уровень выше
        </button>
        <button
          type="button"
          class="inline-flex h-8 items-center gap-1 rounded-md border border-rose-200 bg-rose-50 px-2 text-xs font-medium text-rose-700 hover:bg-rose-100"
          @click="requestDelete"
        >
          <Trash2 class="h-3.5 w-3.5" />
          Удалить
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  ArrowDown,
  ArrowUp,
  Folder,
  FolderPlus,
  Indent,
  Loader2,
  Outdent,
  Pencil,
  Plus,
  Trash2
} from 'lucide-vue-next'
import type { KnowledgeTreeNode } from '~/types/knowledge'

type TreeRow = {
  node: KnowledgeTreeNode
  depth: number
  childrenCount: number
}

const props = defineProps<{
  nodes: KnowledgeTreeNode[]
  selectedNodeId: string | null
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'select', id: string): void
  (e: 'create-root', title: string): void
  (e: 'create-child', parentId: string, title: string): void
  (e: 'rename', id: string, title: string): void
  (e: 'delete', id: string): void
  (e: 'move-up', id: string): void
  (e: 'move-down', id: string): void
  (e: 'indent', id: string): void
  (e: 'dedent', id: string): void
}>()

const nodesByParent = computed(() => {
  const map = new Map<string | null, KnowledgeTreeNode[]>()
  props.nodes.forEach((node) => {
    const current = map.get(node.parent_id) ?? []
    current.push(node)
    map.set(node.parent_id, current)
  })
  map.forEach((list) => list.sort((left, right) => left.order_index - right.order_index))
  return map
})

const rows = computed<TreeRow[]>(() => {
  const output: TreeRow[] = []

  const walk = (parentId: string | null, depth: number) => {
    const children = nodesByParent.value.get(parentId) ?? []
    children.forEach((node) => {
      output.push({
        node,
        depth,
        childrenCount: nodesByParent.value.get(node.id)?.length ?? 0
      })
      walk(node.id, depth + 1)
    })
  }

  walk(null, 0)
  return output
})

const selectedNode = computed(() =>
  props.nodes.find((node) => node.id === props.selectedNodeId) ?? null
)

const requestCreateRoot = () => {
  const title = window.prompt('Название новой папки')
  if (!title?.trim()) return
  emit('create-root', title.trim())
}

const requestCreateChild = () => {
  if (!selectedNode.value) return
  const title = window.prompt('Название вложенной папки')
  if (!title?.trim()) return
  emit('create-child', selectedNode.value.id, title.trim())
}

const requestRename = () => {
  if (!selectedNode.value) return
  const title = window.prompt('Новое название папки', selectedNode.value.title)
  if (!title?.trim()) return
  emit('rename', selectedNode.value.id, title.trim())
}

const requestDelete = () => {
  if (!selectedNode.value) return
  const ok = window.confirm('Удалить папку вместе со всеми вложенными папками и записями?')
  if (!ok) return
  emit('delete', selectedNode.value.id)
}
</script>
