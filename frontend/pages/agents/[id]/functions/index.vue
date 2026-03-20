<template>
  <div class="h-full px-5 py-5">
    <div class="space-y-4">
      <div v-if="loading" class="flex items-center justify-center py-12">
        <Loader2 class="w-8 h-8 animate-spin text-slate-400" />
      </div>

      <div v-else-if="sortedRules.length === 0" class="rounded-xl border border-dashed border-slate-300 bg-white p-12 text-center">
        <div class="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-100">
          <Code class="h-8 w-8 text-slate-400" />
        </div>
        <p class="mb-2 text-sm font-medium text-slate-700">Функции не созданы</p>
        <p class="mb-6 text-sm text-slate-500">Создайте функцию и настройте действия</p>
        <Button v-if="canEditAgents" @click="navigateToCreate" class="flex items-center gap-2 mx-auto">
          <Plus class="w-4 h-4" />
          Создать функцию
        </Button>
      </div>

      <div v-else class="overflow-hidden rounded-xl border border-slate-200 bg-white">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Название</TableHead>
              <TableHead>Приоритет</TableHead>
              <TableHead>Статус</TableHead>
              <TableHead class="w-[200px]">Действия</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow
              v-for="rule in sortedRules"
              :key="rule.id"
              class="cursor-pointer hover:bg-slate-50"
              @click="navigateToEdit(rule.id)"
            >
              <TableCell>
                <div class="font-medium text-slate-900">{{ rule.name || 'Без названия' }}</div>
                <div class="text-xs text-slate-500">
                  {{ getConditionDescription(rule) }}
                </div>
              </TableCell>
              <TableCell>
                <span class="text-sm text-slate-700">{{ rule.priority }}</span>
              </TableCell>
              <TableCell>
                <div class="flex items-center gap-2">
                  <span
                    class="inline-block h-2 w-2 rounded-full"
                    :class="rule.enabled ? 'bg-emerald-500' : 'bg-slate-300'"
                  />
                  <span class="text-sm">{{ rule.enabled ? 'Включена' : 'Выключена' }}</span>
                </div>
              </TableCell>
              <TableCell @click.stop>
                <div class="flex items-center gap-2">
                  <Switch
                    v-if="canEditAgents"
                    :model-value="rule.enabled"
                    @update:model-value="toggleRuleStatus(rule.id, $event)"
                  />
                  <Button
                    v-if="canEditAgents"
                    variant="ghost"
                    size="sm"
                    class="h-8 w-8 p-0"
                    @click="navigateToEdit(rule.id)"
                  >
                    <Pencil class="h-4 w-4" />
                  </Button>
                  <Button
                    v-if="canEditAgents"
                    variant="ghost"
                    size="sm"
                    class="h-8 w-8 p-0 text-red-500 hover:text-red-600"
                    @click="deleteRule(rule.id)"
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
import { onMounted, onUnmounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Plus, Code, Loader2, Pencil, Trash2 } from 'lucide-vue-next'
import { Button } from '~/components/ui/button'
import { Switch } from '~/components/ui/switch'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '~/components/ui/table'
import { useFunctionRules } from '~/composables/useFunctionRules'
import { usePermissions } from '~/composables/usePermissions'
import { useAgentEditorStore } from '~/composables/useAgentEditorStore'
import { useLayoutState } from '~/composables/useLayoutState'
import { getReadableErrorMessage } from '~/utils/api-errors'
import type { FunctionRule } from '~/types/functionRule'

const route = useRoute()
const router = useRouter()
let isCreateNavigating = false
const createActionOwner = 'functions-list-page'
const store = useAgentEditorStore()
const {
  breadcrumbTitle,
  breadcrumbAgentName,
  hideTopBarActions,
  setFunctionsCreateAction,
  clearFunctionsCreateAction,
  resetFunctionsTopbarState,
} = useLayoutState()
const { canEditAgents } = usePermissions()

const agentId = computed(() => (route.params.id as string) || '')
const {
  rules,
  sortedRules,
  loading,
  fetchRules,
  removeRule,
  toggleRule,
} = useFunctionRules(agentId.value)

breadcrumbTitle.value = 'Функции'
const agentName = computed(() => store.agent?.name || '')
breadcrumbAgentName.value = agentName.value

const applyListTopbarActions = () => {
  hideTopBarActions.value = true
  setFunctionsCreateAction(createActionOwner, async () => {
    await navigateToCreate()
  })
}

const getConditionDescription = (rule: FunctionRule) => {
  const cfg = rule.condition_config as Record<string, any> | undefined
  const desc = cfg?.function_description
  if (desc) return desc
  const ct = rule.condition_type as string
  if (ct === 'keywords' || ct === 'keyword') {
    const kw = Array.isArray(cfg?.keywords) ? cfg.keywords : []
    return kw.length ? kw.slice(0, 3).join(', ') + (kw.length > 3 ? '...' : '') : '—'
  }
  if (rule.condition_type === 'regex') return cfg?.pattern || '—'
  if (rule.condition_type === 'semantic') return cfg?.intent || '—'
  return '—'
}

const navigateToCreate = async () => {
  const target = `/agents/${agentId.value}/functions/new`
  if (!agentId.value || route.path === target || isCreateNavigating) return
  isCreateNavigating = true
  try {
    await router.push(target)
  } finally {
    isCreateNavigating = false
  }
}

const navigateToEdit = (ruleId: string) => {
  router.push(`/agents/${agentId.value}/functions/${ruleId}`)
}

const toggleRuleStatus = async (ruleId: string, enabled: boolean) => {
  const rule = rules.value.find((r) => r.id === ruleId)
  if (!rule) return
  try {
    await toggleRule(rule, enabled)
  } catch (err: any) {
    alert(getReadableErrorMessage(err, 'Не удалось изменить статус'))
  }
}

const deleteRule = async (ruleId: string) => {
  if (!confirm('Удалить функцию?')) return
  try {
    await removeRule(ruleId)
  } catch (err: any) {
    alert(getReadableErrorMessage(err, 'Не удалось удалить функцию'))
  }
}

onMounted(async () => {
  // Ensure no stale editor actions leak into list header.
  resetFunctionsTopbarState()
  applyListTopbarActions()

  await store.ensureAgentLoaded(agentId.value)
  breadcrumbAgentName.value = store.agent?.name || ''
  await fetchRules()
})

onUnmounted(() => {
  hideTopBarActions.value = false
  clearFunctionsCreateAction(createActionOwner)
})

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth',
})
</script>
