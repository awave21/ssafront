<template>
  <div class="min-w-0 space-y-4" :class="!canEdit ? 'opacity-80' : ''">
    <div :class="!canEdit ? 'pointer-events-none' : ''">
    <div class="space-y-3">
      <h3 class="mb-3 text-sm font-semibold text-slate-900">Функция</h3>
      <div class="grid gap-3 lg:grid-cols-2">
        <div class="grid gap-1.5 md:col-span-2">
          <label class="text-sm font-medium text-slate-900">Название функции (англ)</label>
          <Input
            :model-value="local.name"
            placeholder="check_order_status"
            @update:model-value="onNameInput"
            @blur="emitModelUpdate"
          />
        </div>
        <div class="grid gap-1.5 md:col-span-2">
          <label class="text-sm font-medium text-slate-900">Описание (когда агенту вызывать)</label>
          <Textarea v-model="functionDescription" placeholder="Вызывай, когда пользователь спрашивает статус заказа" />
        </div>
        <div class="grid gap-1.5">
          <label class="text-sm font-medium text-slate-900">Приоритет</label>
          <Input v-model.number="local.priority" type="number" min="1" />
        </div>
        <div class="flex items-center justify-between py-1">
          <div class="text-sm text-slate-700">Dry-run</div>
          <Switch :model-value="local.dry_run" @update:model-value="local.dry_run = !!$event" />
        </div>
        <div class="flex items-center justify-between py-1">
          <div class="text-sm text-slate-700">Остановить дальнейшие правила</div>
          <Switch :model-value="local.stop_on_match" @update:model-value="local.stop_on_match = !!$event" />
        </div>
      </div>
      <div v-if="local.dry_run" class="mt-3 rounded-md border border-indigo-200 bg-indigo-50 p-2 text-xs text-indigo-700">
        Dry-run включен: действия логируются, но не применяются полноценно.
      </div>
    </div>

    <div class="space-y-3 pt-2">
      <h3 class="mb-3 text-sm font-semibold text-slate-900">Параметры функции (опционально)</h3>
      <p class="text-xs text-slate-500">
        Поле описания нужно для LLM: объясните, какое значение модель должна извлечь из сообщения пользователя.
      </p>
      <div class="space-y-2">
        <div class="hidden lg:grid lg:grid-cols-[1fr_140px_1fr_auto] gap-2 px-1 text-xs font-medium uppercase tracking-wide text-slate-500">
          <span>Имя</span>
          <span>Тип</span>
          <span>Описание для LLM</span>
          <span></span>
        </div>
        <div v-for="(parameter, index) in functionParameters" :key="`param_${index}`" class="grid gap-2 rounded-lg border border-border bg-muted/20 p-3 lg:grid-cols-[1fr_140px_1fr_auto]">
          <Input
            :model-value="parameter.name"
            placeholder="order_id"
            @update:model-value="updateParameter(index, 'name', $event)"
          />
          <Select :model-value="parameter.type" @update:model-value="updateParameter(index, 'type', $event)">
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="string">Текст</SelectItem>
              <SelectItem value="number">Число</SelectItem>
              <SelectItem value="boolean">Логический (Да/Нет)</SelectItem>
            </SelectContent>
          </Select>
          <Input
            :model-value="parameter.description"
            placeholder="Например: ID заказа, который пользователь назвал в сообщении"
            @update:model-value="updateParameter(index, 'description', $event)"
          />
          <Button variant="outline" size="sm" @click="removeParameter(index)">Удалить</Button>
        </div>
        <div class="flex justify-start">
          <Button variant="outline" size="sm" @click="addParameter">Добавить параметр</Button>
        </div>
      </div>
    </div>

    <div class="space-y-3 pt-2">
      <h3 class="mb-3 text-sm font-semibold text-slate-900">Реакция на выполнение функции</h3>
      <div class="grid gap-2">
        <label v-for="item in reactionOptions" :key="item.value" class="flex cursor-pointer items-center gap-2 text-sm text-slate-800">
          <input v-model="local.reaction_mode" type="radio" :value="item.value" />
          <span>{{ item.label }}</span>
        </label>
      </div>
      <div v-if="local.reaction_mode === 'send_message'" class="mt-3 grid gap-1.5">
        <label class="text-sm font-medium text-slate-900">Текст сообщения</label>
        <Textarea v-model="local.reaction_message" />
      </div>
      <div v-if="local.reaction_mode === 'ai_instruction'" class="mt-3 grid gap-1.5">
        <label class="text-sm font-medium text-slate-900">Инструкция для AI</label>
        <Textarea v-model="local.reaction_instruction" />
      </div>
    </div>

    <div class="space-y-3 pt-2">
      <h3 class="mb-3 text-sm font-semibold text-slate-900">Сценарий после выполнения</h3>
      <div class="grid gap-2">
        <label v-for="item in postScenarioOptions" :key="item.value" class="flex cursor-pointer items-center gap-2 text-sm text-slate-800">
          <input v-model="local.post_scenario" type="radio" :value="item.value" />
          <span>{{ item.label }}</span>
        </label>
      </div>
      <div v-if="local.post_scenario === 'augment_prompt'" class="mt-3 grid gap-1.5">
        <label class="text-sm font-medium text-slate-900">Что добавить в промпт</label>
        <Textarea v-model="local.post_scenario_prompt" />
      </div>
      <p v-if="local.post_scenario === 'pause'" class="mt-3 text-xs text-slate-500">
        Диалог будет приостановлен до отдельного события возобновления.
      </p>
    </div>

    <RuleActionsTable
      :actions="actions"
      :can-edit="canEdit"
      @add="$emit('add-action')"
      @edit="$emit('edit-action', $event)"
      @remove="$emit('remove-action', $event)"
      @move-up="$emit('move-action-up', $event)"
      @move-down="$emit('move-action-down', $event)"
    />
    </div>

    <div v-if="showCancel" class="flex justify-end gap-2">
      <Button variant="outline" @click="$emit('cancel')">Отмена</Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { Button } from '~/components/ui/button'
import { Input } from '~/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '~/components/ui/select'
import { Switch } from '~/components/ui/switch'
import { Textarea } from '~/components/ui/textarea'
import RuleActionsTable from '~/components/agents/function-rules/RuleActionsTable.vue'
import type { Tool } from '~/types/tool'
import type { FunctionRule } from '~/types/functionRule'
import type { FunctionRuleAction } from '~/types/ruleAction'

const props = withDefaults(
  defineProps<{
    model: FunctionRule
    tools: Tool[]
    actions: FunctionRuleAction[]
    canEdit: boolean
    showCancel?: boolean
  }>(),
  { showCancel: true },
)

const emit = defineEmits<{
  (e: 'update:model', payload: FunctionRule): void
  (e: 'cancel'): void
  (e: 'add-action'): void
  (e: 'edit-action', id: string): void
  (e: 'remove-action', id: string): void
  (e: 'move-action-up', id: string): void
  (e: 'move-action-down', id: string): void
}>()

const local = reactive<FunctionRule>({
  ...props.model,
  condition_config: { ...(props.model.condition_config as Record<string, any>) } as any,
})
let isSyncingFromParent = false
let syncToken = 0

const reactionOptions = [
  { value: 'send_message', label: 'Отправить сообщение' },
  { value: 'ai_instruction', label: 'Инструкция для AI' },
  { value: 'ai_self_reply', label: 'Позволить AI ответить самому' },
  { value: 'silent', label: 'Промолчать' },
]

const postScenarioOptions = [
  { value: 'continue', label: 'Продолжить диалог' },
  { value: 'pause', label: 'Поставить на паузу' },
  { value: 'augment_prompt', label: 'Дополнить промпт' },
]

type FunctionParameterUi = {
  name: string
  type: 'string' | 'number' | 'boolean'
  description: string
}

const functionParameters = ref<FunctionParameterUi[]>([])

const syncFromModel = (model: FunctionRule) => {
    isSyncingFromParent = true
    const token = ++syncToken
    Object.assign(local, {
      ...model,
      condition_config: { ...(model.condition_config as Record<string, any>) },
    })
    ensureConditionSchemaInitialized(model.tool_id || null)
    void nextTick(() => {
      if (token === syncToken) {
        isSyncingFromParent = false
      }
    })
}

const emitModelUpdate = () => {
  if (isSyncingFromParent) return
  emit('update:model', {
    ...local,
    trigger_mode: 'post_tool',
    condition_type: 'always',
    condition_config: { ...(local.condition_config as Record<string, any>) } as any,
  })
}

watch(
  () => ({
    id: props.model.id,
    tool_id: props.model.tool_id,
    condition_config_ref: props.model.condition_config,
    updated_at: props.model.updated_at,
  }),
  () => {
    syncFromModel(props.model)
  },
  { immediate: true },
)

watch(
  () => ({
    id: local.id,
    agent_id: local.agent_id,
    enabled: local.enabled,
    priority: local.priority,
    trigger_mode: local.trigger_mode,
    condition_type: local.condition_type,
    condition_config_ref: local.condition_config,
    tool_id: local.tool_id,
    dry_run: local.dry_run,
    stop_on_match: local.stop_on_match,
    reaction_mode: local.reaction_mode,
    reaction_message: local.reaction_message,
    reaction_instruction: local.reaction_instruction,
    post_scenario: local.post_scenario,
    post_scenario_prompt: local.post_scenario_prompt,
  }),
  () => {
    emitModelUpdate()
  },
)

watch(
  () => local.reaction_mode,
  (mode) => {
    if (mode === 'send_message') {
      local.reaction_instruction = ''
      return
    }
    if (mode === 'ai_instruction') {
      local.reaction_message = ''
      return
    }
    local.reaction_message = ''
    local.reaction_instruction = ''
  },
)

const onNameInput = (value: string | number) => {
  local.name = String(value ?? '')
}

function hasSchemaProperties(schema: any) {
  return Boolean(
    schema &&
    typeof schema === 'object' &&
    schema.type === 'object' &&
    schema.properties &&
    typeof schema.properties === 'object' &&
    Object.keys(schema.properties).length > 0,
  )
}

function getToolSchema(toolId?: string | null) {
  const linkedTool = props.tools.find((item) => item.id === toolId)
  const schemaFromTool = linkedTool?.input_schema
  return hasSchemaProperties(schemaFromTool) ? schemaFromTool : null
}

function readToolArgsFromConfig(
  config: Record<string, any> | null | undefined,
): FunctionParameterUi[] {
  const schema = config?.tool_args_schema
  const raw = (schema as any)?.properties
  if (!raw || typeof raw !== 'object') return []
  return Object.entries(raw)
    .filter(([name, property]: [string, any]) => {
      if (!name) return false
      if (String(name).startsWith('_')) return false
      if (property?.['x-variable'] === true) return false
      return true
    })
    .map(([name, property]: [string, any]) => ({
      name,
      type:
        property?.type === 'number' ||
        property?.type === 'integer' ||
        property?.type === 'boolean'
          ? (property.type === 'integer' ? 'number' : property.type)
          : 'string',
      description: String(property?.description || ''),
    }))
}

function ensureConditionSchemaInitialized(toolId?: string | null) {
  const cfg = (local.condition_config as Record<string, any>) || {}
  const schemaFromConfig = cfg.tool_args_schema
  if (hasSchemaProperties(schemaFromConfig)) {
    functionParameters.value = readToolArgsFromConfig(cfg)
    return
  }
  const schemaFromTool = getToolSchema(toolId)
  if (!schemaFromTool) {
    functionParameters.value = []
    return
  }
  local.condition_config = {
    ...cfg,
    tool_args_schema: {
      type: 'object',
      properties: { ...(schemaFromTool.properties || {}) },
    },
  } as any
  functionParameters.value = readToolArgsFromConfig(local.condition_config as Record<string, any>)
}

watch(
  () => props.tools,
  () => {
    ensureConditionSchemaInitialized(local.tool_id || null)
  },
  { deep: true },
)

const rebuildToolArgsSchemaFromDraft = () => {
  const properties = functionParameters.value.reduce<Record<string, any>>((acc, item) => {
    const key = String(item.name || '').trim()
    if (!key) return acc
    acc[key] = {
      type: item.type,
      description: item.description,
    }
    return acc
  }, {})

  local.condition_config = {
    ...(local.condition_config as Record<string, any>),
    tool_args_schema: {
      type: 'object',
      properties,
    },
  } as any
}

const functionDescription = computed({
  get: () => String((local.condition_config as any)?.function_description || ''),
  set: (value: string) => {
    local.condition_config = {
      ...(local.condition_config as Record<string, any>),
      function_description: value,
    } as any
  },
})

const getNextParameterName = () => {
  const existing = new Set(
    functionParameters.value
      .map((item) => String(item.name || '').trim())
      .filter(Boolean),
  )
  let index = 1
  let candidate = `param_${index}`
  while (existing.has(candidate)) {
    index += 1
    candidate = `param_${index}`
  }
  return candidate
}

const addParameter = () => {
  functionParameters.value = [
    ...functionParameters.value,
    { name: getNextParameterName(), type: 'string', description: '' },
  ]
  rebuildToolArgsSchemaFromDraft()
}

const removeParameter = (index: number) => {
  functionParameters.value = functionParameters.value.filter((_, itemIndex) => itemIndex !== index)
  rebuildToolArgsSchemaFromDraft()
}

const updateParameter = (index: number, field: keyof FunctionParameterUi, value: string | number) => {
  const next = [...functionParameters.value]
  if (!next[index]) return
  if (field === 'type') {
    const normalized = String(value)
    next[index] = {
      ...next[index],
      type: normalized === 'number' || normalized === 'boolean' ? normalized : 'string',
    }
  } else {
    next[index] = {
      ...next[index],
      [field]: String(value ?? ''),
    }
  }
  functionParameters.value = next
  rebuildToolArgsSchemaFromDraft()
}

</script>
