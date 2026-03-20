<template>
  <div class="h-full px-5 py-5">
    <div class="space-y-4">
      <!-- Header -->
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <Button variant="ghost" size="sm" class="gap-2" @click="$emit('back')">
            <ArrowLeft class="h-4 w-4" />
            Назад к списку
          </Button>
          <span class="text-muted-foreground">/</span>
          <h2 class="text-lg font-semibold text-slate-900">
            {{ isNew ? 'Новая функция' : (editingRule?.name || 'Редактирование') }}
          </h2>
        </div>
      </div>

      <!-- Loading -->
      <div v-if="loading && !editingRule" class="flex items-center justify-center py-12">
        <Loader2 class="w-8 h-8 animate-spin text-slate-400" />
      </div>

      <!-- Form -->
      <div v-else-if="editingRule" class="space-y-4">
        <div class="bg-white p-2">
          <FunctionRuleForm
            :model="editingRule"
            :tools="tools"
            :actions="editingActions"
            :can-edit="canEditAgents"
            :show-cancel="false"
            @update:model="onRuleModelUpdate"
            @cancel="$emit('back')"
            @add-action="openActionDialog(null)"
            @edit-action="openActionDialogById"
            @remove-action="removeAction"
            @move-action-up="moveActionUp"
            @move-action-down="moveActionDown"
          />
        </div>
      </div>

      <div v-else class="rounded-xl border border-slate-200 bg-white p-8 text-center text-slate-500">
        Функция не найдена
      </div>
    </div>

    <RuleActionFormDialog
      :open="isActionDialogOpen"
      :model="editingAction"
      :tools="tools"
      :rule-variables="ruleVariables"
      @update:open="isActionDialogOpen = $event"
      @add-rule-variable="onAddRuleVariable"
      @submit="saveAction"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, watchEffect } from 'vue'
import { ArrowLeft, Loader2 } from 'lucide-vue-next'
import { Button } from '~/components/ui/button'
import { useApiFetch } from '~/composables/useApiFetch'
import { useFunctionRules } from '~/composables/useFunctionRules'
import { useRuleActions } from '~/composables/useRuleActions'
import { usePermissions } from '~/composables/usePermissions'
import { useAuth } from '~/composables/useAuth'
import { useLayoutState } from '~/composables/useLayoutState'
import { useAgentEditorStore } from '~/composables/useAgentEditorStore'
import { getReadableErrorMessage } from '~/utils/api-errors'
import FunctionRuleForm from '~/components/agents/function-rules/FunctionRuleForm.vue'
import RuleActionFormDialog from '~/components/agents/function-rules/RuleActionFormDialog.vue'
import type { Tool } from '~/types/tool'
import type { FunctionRule } from '~/types/functionRule'
import type { FunctionRuleAction } from '~/types/ruleAction'

const props = defineProps<{
  agentId: string
  ruleId: string | null
}>()

const emit = defineEmits<{
  back: []
}>()

const apiFetch = useApiFetch()
const store = useAgentEditorStore()
const { canEditAgents } = usePermissions()
const { user } = useAuth()
const {
  breadcrumbTitle,
  breadcrumbAgentName,
  hideTopBarActions,
  functionsRunAction,
  functionsDeleteAction,
  functionsToggleStatusAction,
  functionsSaveAction,
  functionsDuplicateAction,
  setFunctionsCreateAction,
  clearFunctionsCreateAction,
  functionsSelectedFunction,
  functionsTesting,
  functionsCanSave,
  resetFunctionsTopbarState,
} = useLayoutState()
const createActionOwner = 'functions-editor-page'

const {
  rules,
  loading: rulesLoading,
  saving: rulesSaving,
  fetchRules,
  createRule,
  updateRule,
  removeRule: removeRuleFromApi,
} = useFunctionRules(props.agentId)

const {
  getActions,
  addAction,
  updateAction,
  removeAction: removeActionFromApi,
} = useRuleActions(props.agentId)

const tools = ref<Tool[]>([])
const editingRule = ref<FunctionRule | null>(null)
const editingActions = ref<FunctionRuleAction[]>([])
const editingAction = ref<FunctionRuleAction | null>(null)
const isActionDialogOpen = ref(false)

const loading = computed(() => rulesLoading.value)
const saving = computed(() => rulesSaving.value)
const isNew = computed(() => !props.ruleId || props.ruleId.startsWith('new_'))

breadcrumbTitle.value = 'Функции'
hideTopBarActions.value = true

const createEmptyRule = (): FunctionRule => ({
  id: `new_${Date.now()}`,
  agent_id: props.agentId,
  name: '',
  enabled: true,
  allow_semantic: false,
  priority: 100,
  trigger_mode: 'post_tool',
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

const isValidHttpUrl = (value: string) => {
  const raw = String(value || '').trim()
  if (!raw) return false
  if (raw.startsWith('/')) return true
  try {
    const parsed = new URL(raw)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:'
  } catch {
    return false
  }
}

const validateRulePayload = (payload: FunctionRule): string | null => {
  if (!payload.name.trim()) return 'Укажите название функции'
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

const normalizeReactionFields = (rule: FunctionRule) => {
  const reactionMessage = String(rule.reaction_message || '').trim()
  const reactionInstruction = String(rule.reaction_instruction || '').trim()

  if (rule.reaction_mode === 'send_message') {
    return {
      reaction_message: reactionMessage || null,
      reaction_instruction: null,
    }
  }

  if (rule.reaction_mode === 'ai_instruction') {
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

const buildRuleUpsertPayload = (
  rule: FunctionRule,
  overrides: Partial<FunctionRule> = {},
) => {
  const merged = { ...rule, ...overrides }
  const normalizedReaction = normalizeReactionFields(merged)
  return {
    name: merged.name,
    enabled: merged.enabled,
    allow_semantic: merged.allow_semantic,
    priority: merged.priority,
    trigger_mode: merged.trigger_mode,
    condition_type: merged.condition_type,
    condition_config: merged.condition_config as any,
    tool_id: merged.tool_id || null,
    dry_run: merged.dry_run,
    stop_on_match: merged.stop_on_match,
    reaction_mode: merged.reaction_mode,
    reaction_message: normalizedReaction.reaction_message,
    reaction_instruction: normalizedReaction.reaction_instruction,
    post_scenario: merged.post_scenario,
    post_scenario_prompt: merged.post_scenario_prompt || null,
  }
}

const loadTools = async () => {
  try {
    const bindings = await apiFetch<any[]>(`/agents/${props.agentId}/tools/details`)
    tools.value = bindings
      .map((b: any) => b.tool)
      .filter((t: any): t is Tool => Boolean(t))
  } catch (err) {
    console.error('Failed to load agent tools:', err)
  }
}

const ensureToolLoaded = async (toolId?: string | null) => {
  if (!toolId) return
  if (tools.value.some((tool) => tool.id === toolId)) return
  try {
    const tool = await apiFetch<Tool>(`/tools/${toolId}`)
    if (!tool?.id) return
    tools.value = [...tools.value, tool]
  } catch {
    // Ignore: some scopes may not allow direct tool lookup.
  }
}

const buildToolSchemaFromRule = (rule: FunctionRule) => {
  const cfg = (rule.condition_config || {}) as Record<string, any>
  const schema = cfg.tool_args_schema
  if (
    schema &&
    typeof schema === 'object' &&
    schema.type === 'object' &&
    schema.properties &&
    typeof schema.properties === 'object' &&
    Object.keys(schema.properties).length > 0
  ) {
    return schema
  }
  const linkedTool = tools.value.find((tool) => tool.id === rule.tool_id)
  if (
    linkedTool?.input_schema &&
    typeof linkedTool.input_schema === 'object' &&
    linkedTool.input_schema.type === 'object' &&
    linkedTool.input_schema.properties &&
    typeof linkedTool.input_schema.properties === 'object' &&
    Object.keys(linkedTool.input_schema.properties).length > 0
  ) {
    return linkedTool.input_schema
  }
  return { type: 'object', properties: {} }
}

const syncExistingToolFromRule = async (rule: FunctionRule, toolId: string) => {
  const cfg = (rule.condition_config || {}) as Record<string, any>
  const functionDescription = String(cfg.function_description || '').trim()
  await apiFetch<Tool>(`/tools/${toolId}`, {
    method: 'PUT',
    body: {
      name: rule.name.trim(),
      description: functionDescription || `Функция ${rule.name.trim()}`,
      input_schema: buildToolSchemaFromRule(rule),
    },
  })
}

const ensureToolForRule = async (rule: FunctionRule): Promise<string | null> => {
  if (rule.tool_id) {
    await syncExistingToolFromRule(rule, rule.tool_id)
    return rule.tool_id
  }
  if (!rule.name.trim()) return null

  const cfg = (rule.condition_config || {}) as Record<string, any>
  const functionDescription = String(cfg.function_description || '').trim()

  try {
    const createdTool = await apiFetch<Tool>('/tools', {
      method: 'POST',
      body: {
        agent_id: props.agentId,
        name: rule.name.trim(),
        description: functionDescription || `Функция ${rule.name.trim()}`,
        input_schema: buildToolSchemaFromRule(rule),
        execution_type: 'internal',
        auth_type: 'none',
        status: 'active',
        webhook_scope: 'tool',
      },
    })
    await loadTools()
    return createdTool.id || null
  } catch (err: any) {
    const status = Number(err?.status || err?.response?.status || 0)
    if (status === 409) {
      try {
        const bindings = await apiFetch<any[]>(`/agents/${props.agentId}/tools/details`)
        const existing = (bindings || [])
          .map((b: any) => b.tool as Tool | null | undefined)
          .filter((tool): tool is Tool => Boolean(tool))
          .find((tool) => tool.name === rule.name.trim())
        if (existing?.id) return existing.id
      } catch {
        // keep primary error path below
      }
    }
    throw err
  }
}

const startCreateRule = () => {
  editingRule.value = createEmptyRule()
  editingActions.value = []
}

const startEditRule = async (ruleId: string) => {
  const existing = rules.value.find((r) => r.id === ruleId)
  if (!existing) return
  editingRule.value = {
    ...existing,
    condition_config: { ...(existing.condition_config as Record<string, any>) } as any,
  }
  const serverActions = (existing as any).actions as FunctionRuleAction[] | undefined
  editingActions.value = serverActions
    ? [...serverActions].sort((a, b) => a.order_index - b.order_index)
    : getActions(ruleId)
  await ensureToolLoaded(existing.tool_id || null)
}

const onRuleModelUpdate = (payload: FunctionRule) => {
  if (!editingRule.value || editingRule.value.id !== payload.id) {
    editingRule.value = payload
  } else {
    Object.assign(editingRule.value, payload, {
      condition_config: { ...(payload.condition_config as Record<string, any>) } as any,
    })
  }
}

const openActionDialog = (action: FunctionRuleAction | null) => {
  editingAction.value = action
  isActionDialogOpen.value = true
}

const openActionDialogById = (actionId: string) => {
  const action = editingActions.value.find((a) => a.id === actionId)
  if (action) openActionDialog(action)
}

const ruleVariables = computed(() => {
  const cfg = (editingRule.value?.condition_config || {}) as Record<string, any>
  const properties = (cfg.tool_args_schema as any)?.properties
  if (!properties || typeof properties !== 'object') return []
  return Object.entries(properties).map(([name, item]: [string, any]) => ({
    name,
    type: String(item?.type || 'string'),
    description: String(item?.description || ''),
  }))
})

const onAddRuleVariable = (payload: { name: string; type: string; description?: string }) => {
  if (!editingRule.value) return
  const variableName = String(payload.name || '').trim()
  if (!variableName) return
  const cfg = { ...((editingRule.value.condition_config || {}) as Record<string, any>) }
  const schema = { ...(((cfg.tool_args_schema as any) || { type: 'object', properties: {} })) }
  const properties = { ...(schema.properties || {}) }
  if (properties[variableName]) return
  const normalizedType = payload.type === 'number' || payload.type === 'boolean' ? payload.type : 'string'
  properties[variableName] = {
    type: normalizedType,
    description: String(payload.description || ''),
  }
  schema.type = 'object'
  schema.properties = properties
  cfg.tool_args_schema = schema
  editingRule.value.condition_config = cfg as any
}

const saveAction = (payload: FunctionRuleAction) => {
  const index = editingActions.value.findIndex((a) => a.id === payload.id)
  if (index === -1) {
    editingActions.value.push({
      ...payload,
      id: payload.id || `local_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
      order_index: editingActions.value.length + 1,
    })
  } else {
    editingActions.value[index] = { ...payload }
  }
}

const removeAction = async (actionId: string) => {
  const action = editingActions.value.find((a) => a.id === actionId)
  if (!action) return
  if (editingRule.value?.id && action.id && !action.id.startsWith('local_')) {
    try {
      await removeActionFromApi(editingRule.value.id, action.id)
    } catch (err: any) {
      alert(getReadableErrorMessage(err, 'Не удалось удалить действие'))
      return
    }
  }
  editingActions.value = editingActions.value.filter((a) => a.id !== actionId)
}

const moveActionUp = (actionId: string) => {
  const index = editingActions.value.findIndex((a) => a.id === actionId)
  if (index <= 0) return
  const next = [...editingActions.value]
  const [current] = next.splice(index, 1)
  next.splice(index - 1, 0, current)
  editingActions.value = next.map((a, i) => ({ ...a, order_index: i + 1 }))
}

const moveActionDown = (actionId: string) => {
  const index = editingActions.value.findIndex((a) => a.id === actionId)
  if (index === -1 || index >= editingActions.value.length - 1) return
  const next = [...editingActions.value]
  const [current] = next.splice(index, 1)
  next.splice(index + 1, 0, current)
  editingActions.value = next.map((a, i) => ({ ...a, order_index: i + 1 }))
}

const saveRule = async () => {
  if (!canEditAgents.value || !editingRule.value) return
  const payload = editingRule.value
  const ruleErr = validateRulePayload(payload)
  if (ruleErr) {
    alert(ruleErr)
    return
  }
  const actionsErr = validateActions(editingActions.value)
  if (actionsErr) {
    alert(actionsErr)
    return
  }
  try {
    let persisted: FunctionRule
    const ensuredToolId = await ensureToolForRule(payload)
    if (ensuredToolId) {
      payload.tool_id = ensuredToolId
    }
    if (!payload.id || payload.id.startsWith('new_')) {
      persisted = await createRule(buildRuleUpsertPayload(payload))
    } else {
      persisted = await updateRule(payload.id, buildRuleUpsertPayload(payload))
    }

    for (const [index, action] of editingActions.value.entries()) {
      const actionPayload = {
        action_type: action.action_type,
        on_status: action.on_status,
        enabled: action.enabled,
        order_index: index + 1,
        config: action.config,
      }
      if (!action.id || action.id.startsWith('local_')) {
        await addAction(persisted.id, actionPayload)
      } else {
        await updateAction(persisted.id, action.id, actionPayload)
      }
    }
    emit('back')
    await fetchRules()
  } catch (err: any) {
    alert(getReadableErrorMessage(err, 'Не удалось сохранить функцию'))
  }
}

const deleteRule = async () => {
  if (!editingRule.value?.id || editingRule.value.id.startsWith('new_')) {
    emit('back')
    return
  }
  if (!confirm('Удалить функцию?')) return
  try {
    await removeRuleFromApi(editingRule.value.id)
    emit('back')
  } catch (err: any) {
    alert(getReadableErrorMessage(err, 'Не удалось удалить функцию'))
  }
}

const toggleCurrentRuleStatus = async (isActive: boolean) => {
  if (!editingRule.value) return
  editingRule.value.enabled = isActive
  if (editingRule.value.id && !editingRule.value.id.startsWith('new_')) {
    try {
      await updateRule(
        editingRule.value.id,
        buildRuleUpsertPayload(editingRule.value, { enabled: isActive }),
      )
    } catch (err: any) {
      alert(getReadableErrorMessage(err, 'Не удалось изменить статус'))
    }
  }
}

watch(
  () => props.ruleId,
  async (ruleId) => {
    if (!ruleId || ruleId.startsWith('new_')) {
      startCreateRule()
    } else {
      await startEditRule(ruleId)
    }
  },
  { immediate: true },
)

onMounted(async () => {
  resetFunctionsTopbarState()
  setFunctionsCreateAction(createActionOwner, null)
  functionsSaveAction.value = () => {
    void saveRule()
  }
  functionsDeleteAction.value = () => {
    void deleteRule()
  }
  functionsToggleStatusAction.value = (isActive: boolean) => {
    void toggleCurrentRuleStatus(isActive)
  }
  functionsDuplicateAction.value = null

  await store.ensureAgentLoaded(props.agentId)
  breadcrumbAgentName.value = store.agent?.name || ''
  await Promise.all([fetchRules(), loadTools()])
  if (!props.ruleId || props.ruleId.startsWith('new_')) {
    startCreateRule()
  } else {
    await startEditRule(props.ruleId)
  }
})

watchEffect(() => {
  functionsSelectedFunction.value = editingRule.value
    ? { status: editingRule.value.enabled ? 'active' : 'deprecated' }
    : null
  functionsTesting.value = false
  functionsCanSave.value = Boolean(editingRule.value && canEditAgents.value && !saving.value)
})

watch(
  [
    () => canEditAgents.value,
    () => user.value?.role,
    () => user.value?.scopes,
    () => props.ruleId,
  ],
  ([canEdit, role, scopes, ruleId]) => {
    if (!process.client) return
    console.debug('[FunctionEditorPage] permissions state', {
      canEdit,
      role: role || null,
      scopes: Array.isArray(scopes) ? scopes : null,
      ruleId,
      isNew: isNew.value,
    })
  },
  { immediate: true, deep: true },
)

onUnmounted(() => {
  hideTopBarActions.value = false
  clearFunctionsCreateAction(createActionOwner)
  resetFunctionsTopbarState({ keepCreateAction: true })
})
</script>
