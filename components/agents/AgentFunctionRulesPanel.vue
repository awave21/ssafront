<template>
  <div class="min-w-0 space-y-4">
    <div class="flex min-h-[72vh] gap-4">
      <div class="w-[280px] shrink-0 overflow-hidden rounded-xl border border-slate-200 bg-slate-50">
        <FunctionsList
          :functions="rulesAsTools"
          :selected-id="editingRule?.id || null"
          :unsaved-changes="sidebarUnsavedChanges"
          :show-import="false"
          :show-method="false"
          title="Функции"
          @select="onSelectSidebarItem"
          @create="startCreateRule"
        />
      </div>

      <div class="min-w-0 flex-1">
        <div v-if="editingRule" class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <FunctionRuleForm
            :model="editingRule"
            :tools="tools"
            :actions="editingActions"
            :can-edit="canEditAgents"
            @update:model="onRuleModelUpdate"
            @cancel="cancelEditing"
            @add-action="openActionDialog(null)"
            @edit-action="openActionDialogById"
            @remove-action="removeAction"
            @move-action-up="moveActionUp"
            @move-action-down="moveActionDown"
          />
        </div>
        <div v-else class="flex h-full min-h-[240px] items-center justify-center rounded-xl border border-dashed border-slate-300 bg-white text-sm text-slate-500">
          Выберите функцию в списке слева или создайте новую.
        </div>
      </div>
    </div>

    <div ref="testSectionRef" class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h3 class="mb-3 text-sm font-semibold text-slate-900">Тест сценария</h3>
      <div class="min-w-0">
        <FunctionRuleTestPanel :loading="testLoading" :result="testResult" @submit="runRuleTest" />
      </div>
    </div>

    <div class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h3 class="mb-3 text-sm font-semibold text-slate-900">Теги диалога</h3>
      <div class="min-w-0">
        <DialogTagsPanel :loading="tagsLoading" :tags="tags" @load="loadDialogTags" />
      </div>
    </div>

    <div class="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <h3 class="mb-3 text-sm font-semibold text-slate-900">Настройки</h3>
      <RulesKillSwitchCard :loading="rulesLoading || rulesSaving" :can-edit="canEditAgents" @kill-switch="runKillSwitch" />
    </div>

    <RuleActionFormDialog
      :open="isActionDialogOpen"
      :model="editingAction"
      @update:open="isActionDialogOpen = $event"
      @submit="saveAction"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useApiFetch } from '~/composables/useApiFetch'
import { useDialogTags } from '~/composables/useDialogTags'
import { useFunctionRules } from '~/composables/useFunctionRules'
import { useFunctionRuleTest } from '~/composables/useFunctionRuleTest'
import { usePermissions } from '~/composables/usePermissions'
import { useRuleActions } from '~/composables/useRuleActions'
import { getReadableErrorMessage } from '~/utils/api-errors'
import FunctionsList from '~/components/agents/functions/FunctionsList.vue'
import FunctionRuleForm from '~/components/agents/function-rules/FunctionRuleForm.vue'
import FunctionRuleTestPanel from '~/components/agents/function-rules/FunctionRuleTestPanel.vue'
import DialogTagsPanel from '~/components/agents/function-rules/DialogTagsPanel.vue'
import RulesKillSwitchCard from '~/components/agents/function-rules/RulesKillSwitchCard.vue'
import RuleActionFormDialog from '~/components/agents/function-rules/RuleActionFormDialog.vue'
import type { Tool } from '~/types/tool'
import type { FunctionRule } from '~/types/functionRule'
import type { FunctionRuleTestRequest } from '~/types/functionRuleTest'
import type { FunctionRuleAction } from '~/types/ruleAction'

const props = defineProps<{
  agentId: string
}>()

const apiFetch = useApiFetch()
const { canEditAgents } = usePermissions()

const {
  rules,
  sortedRules,
  loading: rulesLoading,
  saving: rulesSaving,
  fetchRules,
  createRule,
  updateRule,
  removeRule,
  toggleRule,
  killSwitch,
} = useFunctionRules(props.agentId)

const {
  getActions,
  addAction,
  updateAction,
  removeAction: removeActionFromApi,
} = useRuleActions(props.agentId)

const {
  loading: testLoading,
  result: testResult,
  runTest,
} = useFunctionRuleTest(props.agentId)

const {
  loading: tagsLoading,
  tags,
  fetchTags,
} = useDialogTags(props.agentId)

const tools = ref<Tool[]>([])
const testSectionRef = ref<HTMLElement | null>(null)

const editingRule = ref<FunctionRule | null>(null)
const editingActions = ref<FunctionRuleAction[]>([])
const editingAction = ref<FunctionRuleAction | null>(null)
const isActionDialogOpen = ref(false)
const sidebarUnsavedChanges = ref<Set<string>>(new Set())
const selectedRuleForLayout = computed(() =>
  editingRule.value
    ? {
        ...editingRule.value,
        status: editingRule.value.enabled ? 'active' : 'deprecated',
      }
    : null,
)
const canSaveRef = computed(() => Boolean(editingRule.value))
const testingRef = computed(() => testLoading.value)

const createEmptyRule = (): FunctionRule => ({
  id: '',
  agent_id: props.agentId,
  name: '',
  enabled: true,
  allow_semantic: true,
  priority: 100,
  trigger_mode: 'pre_run',
  condition_type: 'always',
  condition_config: {},
  tool_id: null,
  dry_run: false,
  stop_on_match: false,
  reaction_mode: 'ai_self_reply',
  reaction_message: '',
  reaction_instruction: '',
  post_scenario: 'continue',
  post_scenario_prompt: '',
})

const rulesAsTools = computed<Tool[]>(() =>
  {
    const byId = new Map<string, FunctionRule>()
    sortedRules.value.forEach(rule => byId.set(rule.id, rule))

    if (editingRule.value?.id && !editingRule.value.id.startsWith('new_')) {
      byId.set(editingRule.value.id, editingRule.value)
    }

    const merged = Array.from(byId.values()).sort((left, right) => right.priority - left.priority)
    if (editingRule.value?.id && editingRule.value.id.startsWith('new_')) {
      merged.unshift(editingRule.value)
    }

    return merged.map(rule => ({
      id: rule.id,
      name: rule.name,
      description: `${String((rule.condition_config as any)?.function_description || '').trim() || rule.condition_type} • priority=${rule.priority}`,
      endpoint: '',
      http_method: 'POST',
      execution_type: 'internal',
      auth_type: 'none',
      input_schema: { _displayName: rule.name || 'Новая функция' },
      parameter_mapping: null,
      response_transform: null,
      status: rule.enabled ? 'active' : 'deprecated',
    }))
  },
)

const loadTools = async () => {
  try {
    const bindings = await apiFetch<any[]>(`/agents/${props.agentId}/tools/details`)
    tools.value = bindings
      .map(binding => binding.tool)
      .filter((tool): tool is Tool => Boolean(tool))
  } catch (err) {
    console.error('Failed to load tools for function-rules:', err)
  }
}

const isValidHttpUrl = (value: string) => {
  try {
    const parsed = new URL(value)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:'
  } catch {
    return false
  }
}

const validateRulePayload = (payload: FunctionRule): string | null => {
  if (!payload.name.trim()) return 'Укажите название сценария'

  if (payload.condition_type === 'keywords') {
    const keywords = Array.isArray((payload.condition_config as any)?.keywords)
      ? (payload.condition_config as any).keywords.map((item: any) => String(item).trim()).filter(Boolean)
      : []
    if (keywords.length === 0) {
      return 'Добавьте хотя бы одно ключевое слово'
    }
  }

  if (payload.condition_type === 'regex') {
    if (!String((payload.condition_config as any)?.pattern || '').trim()) {
      return 'Заполните регулярное выражение'
    }
  }

  if (payload.condition_type === 'json_context') {
    const field = String((payload.condition_config as any)?.field || '').trim()
    const equals = String((payload.condition_config as any)?.equals || '').trim()
    const contains = String((payload.condition_config as any)?.contains || '').trim()
    if (!field) {
      return 'Укажите поле контекста для json_context'
    }
    if (!equals && !contains) {
      return 'Укажите equals или contains для json_context'
    }
  }

  if (payload.condition_type === 'semantic') {
    const semantic = payload.condition_config as any
    const threshold = Number(semantic.semantic_threshold)
    if (!Number.isFinite(threshold) || threshold < 0 || threshold > 1) return 'Порог semantic должен быть в диапазоне 0..1'
    if (!String(semantic.intent || '').trim()) return 'Укажите intent для semantic условия'
  }

  if (payload.reaction_mode === 'send_message' && !String(payload.reaction_message || '').trim()) {
    return 'Заполните текст сообщения для реакции send_message'
  }
  if (payload.reaction_mode === 'ai_instruction' && !String(payload.reaction_instruction || '').trim()) {
    return 'Заполните инструкцию для реакции ai_instruction'
  }
  if (payload.post_scenario === 'augment_prompt' && !String(payload.post_scenario_prompt || '').trim()) {
    return 'Заполните текст для дополнения промпта'
  }

  return null
}

const validateActions = (actions: FunctionRuleAction[]): string | null => {
  for (const action of actions) {
    if (action.action_type === 'webhook') {
      const url = String(action.config?.url || '')
      if (!url || !isValidHttpUrl(url)) return 'Для действия webhook укажите валидный URL'
    }
  }
  return null
}

const startCreateRule = () => {
  if (!canEditAgents.value) return
  editingRule.value = {
    ...createEmptyRule(),
    id: `new_${Date.now()}`,
  }
  editingActions.value = []
  if (editingRule.value.id) sidebarUnsavedChanges.value.add(editingRule.value.id)
}

const startEditRule = async (ruleId: string) => {
  if (!canEditAgents.value) return
  const existing = rules.value.find(rule => rule.id === ruleId)
  if (!existing) return
  editingRule.value = {
    ...existing,
    condition_config: { ...(existing.condition_config as Record<string, any>) } as any,
  }
  const serverActions = (existing as any).actions as FunctionRuleAction[] | undefined
  editingActions.value = serverActions ? [...serverActions].sort((a, b) => a.order_index - b.order_index) : getActions(ruleId)
  sidebarUnsavedChanges.value.delete(ruleId)
}

const cancelEditing = () => {
  if (editingRule.value?.id) sidebarUnsavedChanges.value.delete(editingRule.value.id)
  editingRule.value = null
  editingActions.value = []
}

const onRuleModelUpdate = (payload: FunctionRule) => {
  if (!editingRule.value || editingRule.value.id !== payload.id) {
    editingRule.value = payload
  } else {
    Object.assign(editingRule.value, payload, {
      condition_config: { ...(payload.condition_config as Record<string, any>) } as any,
    })
  }
  if (payload.id) sidebarUnsavedChanges.value.add(payload.id)
}

const onSelectSidebarItem = (item: Tool) => {
  if (!item.id) return
  startEditRule(item.id)
}

const normalizeReactionFields = (payload: FunctionRule) => {
  const reactionMessage = String(payload.reaction_message || '').trim()
  const reactionInstruction = String(payload.reaction_instruction || '').trim()

  if (payload.reaction_mode === 'send_message') {
    return {
      reaction_message: reactionMessage || null,
      reaction_instruction: null,
    }
  }

  if (payload.reaction_mode === 'ai_instruction') {
    return {
      reaction_message: null,
      reaction_instruction: reactionInstruction || null,
    }
  }

  return {
    reaction_message: null,
    reaction_instruction: null,
  }
}

const saveRule = async (payload: FunctionRule) => {
  if (!canEditAgents.value) return
  const ruleValidationError = validateRulePayload(payload)
  if (ruleValidationError) {
    alert(ruleValidationError)
    return
  }
  const actionsValidationError = validateActions(editingActions.value)
  if (actionsValidationError) {
    alert(actionsValidationError)
    return
  }
  try {
    const normalizedReaction = normalizeReactionFields(payload)
    let persisted: FunctionRule
    if (!payload.id || payload.id.startsWith('new_')) {
      persisted = await createRule({
        name: payload.name,
        enabled: payload.enabled,
        allow_semantic: payload.allow_semantic,
        priority: payload.priority,
        trigger_mode: payload.trigger_mode,
        condition_type: payload.condition_type,
        condition_config: payload.condition_config as any,
        tool_id: payload.tool_id || null,
        dry_run: payload.dry_run,
        stop_on_match: payload.stop_on_match,
        reaction_mode: payload.reaction_mode,
        reaction_message: normalizedReaction.reaction_message,
        reaction_instruction: normalizedReaction.reaction_instruction,
        post_scenario: payload.post_scenario,
        post_scenario_prompt: payload.post_scenario_prompt || null,
      })
    } else {
      persisted = await updateRule(payload.id, {
        name: payload.name,
        enabled: payload.enabled,
        allow_semantic: payload.allow_semantic,
        priority: payload.priority,
        trigger_mode: payload.trigger_mode,
        condition_type: payload.condition_type,
        condition_config: payload.condition_config as any,
        tool_id: payload.tool_id || null,
        dry_run: payload.dry_run,
        stop_on_match: payload.stop_on_match,
        reaction_mode: payload.reaction_mode,
        reaction_message: normalizedReaction.reaction_message,
        reaction_instruction: normalizedReaction.reaction_instruction,
        post_scenario: payload.post_scenario,
        post_scenario_prompt: payload.post_scenario_prompt || null,
      })
    }

    for (const [index, action] of editingActions.value.entries()) {
      const actionPayload = {
        action_type: action.action_type,
        on_status: action.on_status,
        enabled: action.enabled,
        order_index: index + 1,
        config: action.config,
      }
      if (!action.id) {
        await addAction(persisted.id, actionPayload)
      } else {
        await updateAction(persisted.id, action.id, actionPayload)
      }
    }
    cancelEditing()
    await fetchRules()
  } catch (err: any) {
    alert(getReadableErrorMessage(err, 'Не удалось сохранить сценарий'))
  }
}

const deleteRule = async (ruleId: string) => {
  if (!canEditAgents.value) return
  if (ruleId.startsWith('new_')) {
    if (editingRule.value?.id === ruleId) cancelEditing()
    return
  }
  if (!confirm('Удалить сценарий?')) return
  try {
    await removeRule(ruleId)
    if (editingRule.value?.id === ruleId) cancelEditing()
  } catch (err: any) {
    alert(getReadableErrorMessage(err, 'Не удалось удалить сценарий'))
  }
}

const toggleRuleStatus = async (ruleId: string, enabled: boolean) => {
  if (!canEditAgents.value) return
  const rule = rules.value.find(item => item.id === ruleId)
  if (!rule) return
  try {
    await toggleRule(rule, enabled)
  } catch (err: any) {
    alert(getReadableErrorMessage(err, 'Не удалось изменить статус сценария'))
  }
}

const runKillSwitch = async () => {
  if (!canEditAgents.value) return
  if (!confirm('Отключить все правила агента?')) return
  try {
    await killSwitch()
  } catch (err: any) {
    alert(getReadableErrorMessage(err, 'Не удалось отключить правила'))
  }
}

const openActionDialog = (action: FunctionRuleAction | null) => {
  if (!canEditAgents.value) return
  editingAction.value = action
  isActionDialogOpen.value = true
}

const openActionDialogById = (actionId: string) => {
  const action = editingActions.value.find(item => item.id === actionId)
  if (!action) return
  openActionDialog(action)
}

const saveAction = (payload: FunctionRuleAction) => {
  if (!canEditAgents.value) return
  const index = editingActions.value.findIndex(item => item.id === payload.id)
  if (index === -1) {
    editingActions.value = [
      ...editingActions.value,
      {
        ...payload,
        id: payload.id || `local_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
        order_index: editingActions.value.length + 1,
      },
    ]
    return
  }
  editingActions.value[index] = { ...payload }
}

const removeAction = async (actionId: string) => {
  if (!canEditAgents.value) return
  if (!confirm('Удалить действие?')) return
  const action = editingActions.value.find(item => item.id === actionId)
  if (!action) return
  if (editingRule.value?.id && action.id && !action.id.startsWith('local_')) {
    try {
      await removeActionFromApi(editingRule.value.id, action.id)
    } catch (err: any) {
      alert(getReadableErrorMessage(err, 'Не удалось удалить действие'))
      return
    }
  }
  editingActions.value = editingActions.value.filter(item => item.id !== actionId)
}

const moveActionUp = (actionId: string) => {
  if (!canEditAgents.value) return
  const index = editingActions.value.findIndex(item => item.id === actionId)
  if (index <= 0) return
  const next = [...editingActions.value]
  const [current] = next.splice(index, 1)
  next.splice(index - 1, 0, current)
  editingActions.value = next.map((action, orderIndex) => ({ ...action, order_index: orderIndex + 1 }))
}

const moveActionDown = (actionId: string) => {
  if (!canEditAgents.value) return
  const index = editingActions.value.findIndex(item => item.id === actionId)
  if (index === -1 || index >= editingActions.value.length - 1) return
  const next = [...editingActions.value]
  const [current] = next.splice(index, 1)
  next.splice(index + 1, 0, current)
  editingActions.value = next.map((action, orderIndex) => ({ ...action, order_index: orderIndex + 1 }))
}

const runRuleTest = async (payload: FunctionRuleTestRequest) => {
  try {
    await runTest(payload)
  } catch (err: any) {
    alert(getReadableErrorMessage(err, 'Ошибка теста сценария'))
  }
}

const loadDialogTags = async (sessionId: string) => {
  try {
    await fetchTags(sessionId)
  } catch (err: any) {
    alert(getReadableErrorMessage(err, 'Не удалось загрузить теги'))
  }
}

onMounted(async () => {
  await Promise.all([fetchRules(), loadTools()])
  if (sortedRules.value.length === 0 && canEditAgents.value) {
    startCreateRule()
  }
})

const runCurrentRuleTest = () => {
  testSectionRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const duplicateCurrentRule = () => {
  if (!editingRule.value) return
  const clonedRule: FunctionRule = {
    ...editingRule.value,
    id: '',
    name: `${editingRule.value.name} (копия)`,
    condition_config: { ...(editingRule.value.condition_config as Record<string, any>) } as any,
  }
  const clonedActions = editingActions.value.map((action, index) => ({
    ...action,
    id: '',
    order_index: index + 1,
    config: { ...action.config },
  }))
  editingRule.value = clonedRule
  editingActions.value = clonedActions
}

const saveCurrentRule = async () => {
  if (!editingRule.value) return
  await saveRule(editingRule.value)
}

const deleteCurrentRule = async () => {
  if (!editingRule.value?.id) return
  await deleteRule(editingRule.value.id)
}

const toggleCurrentRuleStatus = async (isActive: boolean) => {
  if (!editingRule.value) return
  editingRule.value.enabled = isActive
  if (editingRule.value.id) {
    await toggleRuleStatus(editingRule.value.id, isActive)
  }
}

defineExpose({
  runCurrentRuleTest,
  saveCurrentRule,
  deleteCurrentRule,
  duplicateCurrentRule,
  toggleCurrentRuleStatus,
  selectedRuleRef: selectedRuleForLayout,
  canSaveRef,
  testingRef,
})
</script>
