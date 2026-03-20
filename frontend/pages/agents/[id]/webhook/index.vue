<template>
  <div class="h-full px-5 py-5">
    <div class="space-y-4">
      <div v-if="loading" class="flex items-center justify-center py-12">
        <Loader2 class="w-8 h-8 animate-spin text-slate-400" />
      </div>

      <div v-else-if="functions.length === 0" class="rounded-xl border border-dashed border-slate-300 bg-white p-12 text-center">
        <div class="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-100">
          <Webhook class="h-8 w-8 text-slate-400" />
        </div>
        <p class="mb-2 text-sm font-medium text-slate-700">Webhook не созданы</p>
        <p class="mb-6 text-sm text-slate-500">Создайте первый webhook и перейдите к его настройкам</p>
        <Button @click="createFunction" class="mx-auto flex items-center gap-2">
          <Plus class="w-4 h-4" />
          Создать webhook
        </Button>
      </div>

      <div v-else class="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Webhook</TableHead>
              <TableHead>Метод</TableHead>
              <TableHead class="w-[280px]">URL</TableHead>
              <TableHead>Тип</TableHead>
              <TableHead>Статус</TableHead>
              <TableHead class="w-[200px]">Действия</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow
              v-for="tool in functions"
              :key="tool.id"
              class="cursor-pointer hover:bg-slate-50"
              @click="openFunction(tool)"
            >
              <TableCell>
                <div class="font-medium text-slate-900">{{ tool.input_schema?._displayName || tool.name }}</div>
                <div class="text-xs text-slate-500 font-mono">{{ tool.name }}</div>
              </TableCell>
              <TableCell>{{ tool.http_method || 'POST' }}</TableCell>
              <TableCell class="max-w-[280px] truncate">{{ tool.endpoint || '—' }}</TableCell>
              <TableCell>
                <span class="text-xs rounded px-2 py-1 bg-slate-100 text-slate-700">
                  {{ getTypeLabel(tool) }}
                </span>
              </TableCell>
              <TableCell>
                <div class="flex items-center gap-2">
                  <span class="inline-block h-2 w-2 rounded-full" :class="tool.status === 'active' ? 'bg-emerald-500' : 'bg-slate-300'" />
                  <span class="text-sm">{{ tool.status === 'active' ? 'Включен' : 'Выключен' }}</span>
                </div>
              </TableCell>
              <TableCell @click.stop>
                <div class="flex items-center gap-2 min-w-[120px]">
                  <div class="w-11 flex items-center justify-center">
                  <Switch
                    v-if="canEditAgents"
                    :model-value="tool.status === 'active'"
                    @update:model-value="toggleStatus(tool)"
                  />
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    class="h-8 w-8 p-0"
                    @click.stop="openFunction(tool)"
                  >
                    <Pencil class="h-4 w-4" />
                  </Button>
                  <Button
                    v-if="canEditAgents"
                    variant="ghost"
                    size="sm"
                    class="h-8 w-8 p-0 text-red-500 hover:text-red-600"
                    @click.stop="deleteWebhook(tool)"
                  >
                    <Trash2 class="h-4 w-4" />
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Loader2, Pencil, Plus, Trash2, Webhook } from 'lucide-vue-next'
import { Button } from '~/components/ui/button'
import { Switch } from '~/components/ui/switch'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '~/components/ui/table'
import type { Tool, ToolBinding } from '~/types/tool'
import type { FunctionRule } from '~/types/functionRule'
import { useApiFetch } from '~/composables/useApiFetch'
import { useAgentEditorStore } from '~/composables/useAgentEditorStore'
import { usePermissions } from '~/composables/usePermissions'

const route = useRoute()
const router = useRouter()
let isCreateNavigating = false
const createActionOwner = 'webhook-list-page'
const apiFetch = useApiFetch()
const store = useAgentEditorStore()
const { canEditAgents } = usePermissions()
const functions = ref<Tool[]>([])
const loading = ref(false)
const usageByToolId = ref<Record<string, { asRuleTool: number; asActionTool: number }>>({})

const {
  setFunctionsCreateAction,
  clearFunctionsCreateAction,
  hideTopBarActions,
  breadcrumbTitle,
  breadcrumbAgentName,
  breadcrumbBackPath,
} = useLayoutState()

const syncBreadcrumb = () => {
  breadcrumbTitle.value = 'Webhook'
  breadcrumbAgentName.value = store.agent?.name || ''
  breadcrumbBackPath.value = null
}

watch(() => store.agent?.name, () => {
  syncBreadcrumb()
}, { immediate: true })

// List page should not show generic "Cancel/Save" actions in header.
const applyListTopbarActions = () => {
  hideTopBarActions.value = true
  setFunctionsCreateAction(createActionOwner, () => createFunction())
}

const resolveAgentId = (value: string | string[] | undefined) =>
  Array.isArray(value) ? value[0] : value

watch(
  () => route.params.id,
  (id) => {
    const resolved = resolveAgentId(id as string | string[] | undefined)
    if (resolved) {
      store.ensureAgentLoaded(resolved)
      loadFunctions(resolved)
    }
  },
  { immediate: true },
)

async function loadFunctions(agentId: string) {
  loading.value = true
  const webhookById = new Map<string, Tool>()
  const upsertWebhook = (tool: Tool | null | undefined) => {
    if (!tool?.id) return
    if ((tool.execution_type || 'http_webhook') !== 'http_webhook') return
    webhookById.set(tool.id, tool)
  }
  const loadToolById = async (toolId: string) => {
    try {
      const tool = await apiFetch<Tool>(`/tools/${toolId}`)
      upsertWebhook(tool)
    } catch (toolErr) {
      console.warn(`Failed to load tool ${toolId}`, toolErr)
    }
  }

  try {
    const bindings = await apiFetch<ToolBinding[]>(`/agents/${agentId}/tools/details`)
    bindings.forEach((binding) => upsertWebhook(binding.tool))
  } catch (err) {
    console.warn('Failed to load detailed webhook list, trying fallback', err)
    try {
      const bindings = await apiFetch<ToolBinding[]>(`/agents/${agentId}/tools`)
      await Promise.all(bindings.map((binding) => loadToolById(binding.tool_id)))
    } catch (fallbackErr) {
      console.error('Failed to load webhooks from bindings', fallbackErr)
    }
  }

  try {
    const rules = await apiFetch<FunctionRule[]>(`/agents/${agentId}/function-rules`)
    const referencedToolIds = new Set<string>()
    const usage: Record<string, { asRuleTool: number; asActionTool: number }> = {}
    const ensureUsage = (toolId: string) => {
      usage[toolId] = usage[toolId] || { asRuleTool: 0, asActionTool: 0 }
      return usage[toolId]
    }
    rules.forEach((rule) => {
      if (rule.tool_id) {
        referencedToolIds.add(rule.tool_id)
        ensureUsage(rule.tool_id).asRuleTool += 1
      }
      ;(rule.actions || []).forEach((action) => {
        if (action.action_type !== 'webhook') return
        const toolId = String(action.config?.tool_id || '').trim()
        if (toolId) {
          referencedToolIds.add(toolId)
          ensureUsage(toolId).asActionTool += 1
        }
      })
    })
    const missingIds = [...referencedToolIds].filter((id) => !webhookById.has(id))
    await Promise.all(missingIds.map((id) => loadToolById(id)))
    usageByToolId.value = usage
  } catch (rulesErr) {
    console.warn('Failed to load webhook ids from function rules', rulesErr)
    usageByToolId.value = {}
  }

  try {
    functions.value = [...webhookById.values()]
  } finally {
    loading.value = false
  }
}

const createFunction = () => {
  const agentId = resolveAgentId(route.params.id as string | string[] | undefined)
  const target = `/agents/${agentId}/webhook/new`
  if (!agentId || route.path === target || isCreateNavigating) return
  isCreateNavigating = true
  router.push(target).finally(() => {
    isCreateNavigating = false
  })
}

const openFunction = (func: Tool) => {
  const agentId = resolveAgentId(route.params.id as string | string[] | undefined)
  if (!agentId || !func.id) return
  router.push(`/agents/${agentId}/webhook/${func.id}`)
}

const getTypeLabel = (tool: Tool) => {
  const toolId = tool.id
  if (toolId) {
    const usage = usageByToolId.value[toolId]
    if (usage && (usage.asRuleTool > 0 || usage.asActionTool > 0)) return 'Через функции'
  }
  return 'Прямой вызов'
}

const toggleStatus = async (tool: Tool) => {
  if (!tool.id) return
  const nextStatus = tool.status === 'active' ? 'deprecated' : 'active'
  try {
    const updated = await apiFetch<Tool>(`/tools/${tool.id}`, {
      method: 'PUT',
      body: { status: nextStatus },
    })
    const index = functions.value.findIndex((item) => item.id === tool.id)
    if (index >= 0) functions.value.splice(index, 1, updated)
  } catch (err) {
    console.error('Failed to toggle webhook status', err)
  }
}

const deleteWebhook = async (tool: Tool) => {
  if (!tool.id) return
  const confirmed = confirm(`Удалить webhook "${tool.input_schema?._displayName || tool.name}"?`)
  if (!confirmed) return
  const agentId = resolveAgentId(route.params.id as string | string[] | undefined)
  try {
    if (agentId) {
      try {
        await apiFetch(`/agents/${agentId}/tools/${tool.id}`, { method: 'DELETE' })
      } catch {
        // Webhook can be function-only without binding; ignore and continue.
      }
    }
    await apiFetch(`/tools/${tool.id}`, { method: 'DELETE' })
    functions.value = functions.value.filter((item) => item.id !== tool.id)
  } catch (err) {
    console.error('Failed to delete webhook', err)
  }
}

onMounted(() => {
  applyListTopbarActions()
  syncBreadcrumb()
})

onUnmounted(() => {
  clearFunctionsCreateAction(createActionOwner)
  hideTopBarActions.value = false
})

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth',
})
</script>
