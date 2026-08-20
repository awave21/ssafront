<template>
  <Sheet :open="open" @update:open="$emit('update:open', $event)">
    <SheetContent side="right" class-name="w-full sm:max-w-[760px] flex flex-col">
      <SheetHeader>
        <div class="flex items-center justify-between">
          <SheetTitle>{{ model?.id ? 'Редактировать действие' : 'Новое действие' }}</SheetTitle>
          <SheetClose />
        </div>
        <SheetDescription>
          Настройте действие, условия его выполнения и необходимые параметры.
        </SheetDescription>
      </SheetHeader>

      <div class="flex flex-col gap-3 py-3 px-6 flex-1 overflow-y-auto">
        <div class="grid gap-1.5">
          <label class="text-sm font-medium text-slate-900">Действие</label>
          <Select :model-value="actionPreset" @update:model-value="onSelectPreset">
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="webhook_api_call">API вызов (Webhook)</SelectItem>
              <SelectItem value="webhook_delayed_message" disabled>Отправить отложенное сообщение (скоро)</SelectItem>
              <SelectItem value="webhook_admin_message" disabled>Отправить сообщение админу в мессенджер (скоро)</SelectItem>
              <SelectItem value="set_tag" disabled>Установить тег (скоро)</SelectItem>
              <SelectItem value="send_message" disabled>Отправить сообщение (скоро)</SelectItem>
              <SelectItem value="set_result" disabled>Задать результат функции (скоро)</SelectItem>
              <SelectItem value="noop">Ничего не делать</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div class="grid gap-2 md:grid-cols-2">
          <div class="grid gap-1.5">
            <label class="text-sm font-medium text-slate-900">Когда выполнять</label>
            <Select :model-value="local.on_status" @update:model-value="local.on_status = $event as any">
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="success">При успехе</SelectItem>
                <SelectItem value="error">При ошибке</SelectItem>
                <SelectItem value="always">Всегда</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div class="grid gap-1.5">
            <label class="text-sm font-medium text-slate-900">Порядок выполнения</label>
            <Input v-model.number="local.order_index" type="number" min="1" />
          </div>
        </div>

        <div class="flex items-center justify-between rounded-md border border-border bg-muted/30 px-3 py-2">
          <div class="text-sm text-slate-700">Включено</div>
          <Switch :model-value="local.enabled" @update:model-value="local.enabled = !!$event" />
        </div>

        <div v-if="local.action_type === 'send_message'" class="grid gap-1.5">
          <label class="text-sm font-medium text-slate-900">Текст сообщения</label>
          <Textarea v-model="messageText" placeholder="Сообщение пользователю после выполнения функции" />
        </div>

        <div v-else-if="local.action_type === 'set_tag'" class="grid gap-2 md:grid-cols-2">
          <div class="grid gap-1.5">
            <label class="text-sm font-medium text-slate-900">Тег</label>
            <Input v-model="tagName" placeholder="interest_to_service" />
          </div>
          <div class="grid gap-1.5">
            <label class="text-sm font-medium text-slate-900">Уверенность (опц.)</label>
            <Input v-model.number="tagConfidence" type="number" min="0" max="1" step="0.01" />
          </div>
        </div>

        <div v-else-if="isWebhookPreset" class="grid gap-3 rounded-md border border-border bg-muted/20 p-2.5">
          <div class="grid gap-1.5">
            <label class="text-sm font-medium text-slate-900">Выберите созданный webhook</label>
            <Select :model-value="selectedToolId" @update:model-value="onSelectTool">
              <SelectTrigger>
                <SelectValue placeholder="Выберите webhook из списка" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">Не выбрано</SelectItem>
                <SelectItem v-for="tool in availableWebhookTools" :key="tool.id" :value="tool.id || ''">
                  {{ tool.input_schema?._displayName || tool.name }}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div v-if="!selectedWebhookTool" class="rounded-md border border-dashed border-border bg-muted/40 p-3 text-xs text-muted-foreground">
            Выберите webhook, чтобы настроить сопоставление параметров.
          </div>

          <div v-else class="grid gap-2 md:grid-cols-2">
            <div class="grid gap-1.5">
              <label class="text-sm font-medium text-slate-900">URL</label>
              <Input v-model="webhookUrl" placeholder="https://example.com/hook" disabled />
            </div>
            <div class="grid gap-1.5">
              <label class="text-sm font-medium text-slate-900">Метод</label>
              <Select :model-value="webhookMethod" @update:model-value="webhookMethod = String($event)" disabled>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="GET">GET</SelectItem>
                  <SelectItem value="POST">POST</SelectItem>
                  <SelectItem value="PUT">PUT</SelectItem>
                  <SelectItem value="PATCH">PATCH</SelectItem>
                  <SelectItem value="DELETE">DELETE</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div v-if="actionPreset === 'webhook_api_call'" class="grid gap-1.5">
            <div v-if="selectedWebhookTool && toolSchemaParams.length" class="grid gap-2 rounded-md border border-border bg-background p-2.5">
              <div class="text-sm font-medium text-slate-900">Параметры webhook</div>
              <div
                v-for="param in toolSchemaParams"
                :key="param.name"
                class="grid gap-1.5"
              >
                <div class="grid gap-2 md:grid-cols-[1fr_1fr] rounded-md border border-border bg-muted/20 p-2 transition-colors hover:bg-muted/35">
                  <div class="grid gap-1">
                    <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">Webhook</div>
                    <div class="flex items-center gap-2">
                      <span class="text-sm font-medium text-slate-900">{{ param.name }}</span>
                      <span class="text-[10px] rounded bg-slate-100 px-1.5 py-0.5 text-slate-600">{{ getTypeLabel(param.type) }}</span>
                      <span class="text-[10px] rounded bg-indigo-50 px-1.5 py-0.5 text-indigo-700">{{ getMappingLabel(param.mappingTarget) }}</span>
                      <span v-if="param.required" class="text-[10px] text-red-500">обязательный</span>
                    </div>
                    <p v-if="param.description" class="text-xs text-slate-500">{{ param.description }}</p>
                  </div>
                  <div class="grid gap-1">
                    <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">Переменная функции</div>
                    <Select
                      :model-value="getVariableSelectValue(param.name)"
                      @update:model-value="onVariableSelectChange(param, String($event))"
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Выберите переменную функции" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem
                          v-for="variable in functionVariableOptions"
                          :key="`var_${param.name}_${variable.name}`"
                          :value="`var:${variable.name}`"
                        >
                          {{ variable.name }}
                        </SelectItem>
                        <SelectItem value="__none__">Не сопоставлено</SelectItem>
                        <SelectItem value="__create__">Создать новую переменную...</SelectItem>
                      </SelectContent>
                    </Select>

                    <div v-if="isCreatingVariableForParam(param.name)" class="grid gap-1.5">
                      <Input
                        :model-value="newVariableDraft[param.name]?.name || ''"
                        placeholder="Имя переменной"
                        @update:model-value="onNewVariableDraftChange(param.name, 'name', String($event))"
                      />
                      <Select
                        :model-value="newVariableDraft[param.name]?.type || normalizeVariableType(param.type)"
                        @update:model-value="onNewVariableDraftChange(param.name, 'type', String($event))"
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="string">Текст</SelectItem>
                          <SelectItem value="number">Число</SelectItem>
                          <SelectItem value="boolean">Логический (Да/Нет)</SelectItem>
                        </SelectContent>
                      </Select>
                      <Input
                        :model-value="newVariableDraft[param.name]?.description || ''"
                        placeholder="Описание для модели (что сюда подставлять)"
                        @update:model-value="onNewVariableDraftChange(param.name, 'description', String($event))"
                      />
                      <Button variant="outline" size="sm" @click="createVariableAndBind(param)">Создать и связать</Button>
                    </div>

                    <div v-else-if="getVariableSelectValue(param.name) === '__none__'" class="rounded-md border border-amber-300/60 bg-amber-50/70 p-2 text-xs text-amber-800">
                      Переменная функции не выбрана.
                    </div>

                    <div v-else class="rounded-md border border-border bg-muted/40 p-2 text-xs text-muted-foreground">
                      Подставляется: {{ getPayloadFieldValue(param.name, '') }}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-else-if="actionPreset === 'webhook_delayed_message'" class="grid gap-2 md:grid-cols-2">
            <div class="grid gap-1.5 md:col-span-2">
              <label class="text-sm font-medium text-slate-900">Текст сообщения</label>
              <Textarea v-model="delayedMessageText" placeholder="Текст отложенного сообщения" />
            </div>
            <div class="grid gap-1.5">
              <label class="text-sm font-medium text-slate-900">Задержка (сек.)</label>
              <Input v-model.number="delayedSeconds" type="number" min="1" />
            </div>
          </div>

          <div v-else-if="actionPreset === 'webhook_admin_message'" class="grid gap-2 md:grid-cols-2">
            <div class="grid gap-1.5 md:col-span-2">
              <label class="text-sm font-medium text-slate-900">Сообщение админу</label>
              <Textarea v-model="adminMessageText" placeholder="Текст сообщения для администратора" />
            </div>
            <div class="grid gap-1.5">
              <label class="text-sm font-medium text-slate-900">Мессенджер</label>
              <Select :model-value="adminMessenger" @update:model-value="adminMessenger = String($event)">
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="telegram">Telegram</SelectItem>
                  <SelectItem value="whatsapp">WhatsApp</SelectItem>
                  <SelectItem value="max">MAX</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <p class="text-xs text-slate-500">
            Для этих сценариев используется действие webhook c конфигурацией выбранной интеграции.
          </p>
        </div>

        <div v-else-if="local.action_type === 'augment_prompt'" class="grid gap-1.5">
          <label class="text-sm font-medium text-slate-900">Текст дополнения</label>
          <Textarea v-model="promptText" placeholder="Что добавить в промпт..." />
        </div>

        <div v-else-if="local.action_type === 'set_result'" class="grid gap-2 md:grid-cols-2">
          <div class="grid gap-1.5">
            <label class="text-sm font-medium text-slate-900">Ключ</label>
            <Input v-model="resultKey" placeholder="result_key" />
          </div>
          <div class="grid gap-1.5">
            <label class="text-sm font-medium text-slate-900">Значение</label>
            <Input v-model="resultValue" placeholder="value" />
          </div>
        </div>
      </div>

      <SheetFooter class-name="mt-2 flex justify-end gap-2">
        <Button variant="outline" @click="$emit('update:open', false)">Отмена</Button>
        <Button @click="submitAction">Сохранить</Button>
      </SheetFooter>
    </SheetContent>
  </Sheet>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { Button } from '~/components/ui/button'
import { Input } from '~/components/ui/input'
import { Textarea } from '~/components/ui/textarea'
import { Switch } from '~/components/ui/switch'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '~/components/ui/select'
import { Sheet, SheetClose, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from '~/components/ui/sheet'
import type { FunctionRuleAction } from '~/types/ruleAction'
import type { Tool } from '~/types/tool'

const props = defineProps<{
  open: boolean
  model: FunctionRuleAction | null
  tools?: Tool[]
  ruleVariables?: Array<{ name: string; type?: string; description?: string }>
}>()

const emit = defineEmits<{
  'update:open': [open: boolean]
  submit: [payload: FunctionRuleAction]
  'add-rule-variable': [payload: { name: string; type: string; description?: string }]
}>()

const local = reactive<FunctionRuleAction>({
  id: '',
  rule_id: '',
  action_type: 'noop',
  on_status: 'always',
  enabled: true,
  order_index: 1,
  config: {},
})
const actionPreset = ref<string>('noop')

const availableWebhookTools = computed(() =>
  (props.tools || []).filter(
    (tool) =>
      tool.execution_type === 'http_webhook' &&
      Boolean(tool.endpoint) &&
      (tool.webhook_scope === 'function_only' || tool.webhook_scope === 'both') &&
      (tool.status === 'active' || tool.status === undefined),
  ),
)

const isWebhookPreset = computed(() => actionPreset.value.startsWith('webhook_'))
type ToolSchemaParam = {
  name: string
  type: string
  description: string
  mappingTarget: string
  required: boolean
  defaultValue: any
}
const selectedWebhookTool = computed(() =>
  availableWebhookTools.value.find((tool) => tool.id === local.config.tool_id),
)
const functionVariableOptions = computed(() =>
  (props.ruleVariables || [])
    .map((item) => ({
      name: String(item.name || '').trim(),
      type: String(item.type || 'string'),
      description: String(item.description || ''),
    }))
    .filter((item) => Boolean(item.name))
    .filter((item, index, all) => all.findIndex((x) => x.name === item.name) === index),
)
const newVariableDraft = reactive<Record<string, { name: string; type: string; description: string }>>({})
const toolSchemaParams = computed<ToolSchemaParam[]>(() => {
  const tool = selectedWebhookTool.value
  const schema = tool?.input_schema
  const properties = schema && typeof schema === 'object' ? schema.properties : null
  if (!properties || typeof properties !== 'object') return []
  const requiredList = Array.isArray(schema.required) ? schema.required.map((v: any) => String(v)) : []
  const seen = new Set<string>()
  return Object.entries(properties)
    .filter(([name, cfg]: [string, any]) => {
      if (!name || seen.has(name)) return false
      if (String(name).startsWith('_')) return false
      if (cfg?.['x-variable'] === true) return false
      seen.add(name)
      return true
    })
    .map(([name, cfg]: [string, any]) => ({
      name,
      type: String(cfg?.type || 'string'),
      description: String(cfg?.description || ''),
      mappingTarget: String(tool?.parameter_mapping?.[name] || 'body'),
      required: requiredList.includes(name),
      defaultValue: cfg?.default,
    }))
})

const messageText = computed({
  get: () => String(local.config.message || ''),
  set: (value: string) => {
    local.config = { ...local.config, message: value }
  },
})

const tagName = computed({
  get: () => String(local.config.tag || ''),
  set: (value: string) => {
    local.config = { ...local.config, tag: value }
  },
})

const tagConfidence = computed({
  get: () => Number(local.config.confidence || 0),
  set: (value: number) => {
    local.config = { ...local.config, confidence: value }
  },
})

const webhookUrl = computed({
  get: () => String(local.config.url || ''),
  set: (value: string) => {
    local.config = { ...local.config, url: value }
  },
})

const webhookMethod = computed({
  get: () => String(local.config.method || 'POST'),
  set: (value: string) => {
    local.config = { ...local.config, method: value }
  },
})

const selectedToolId = computed(() => String(local.config.tool_id || '__none__'))

const delayedMessageText = computed({
  get: () => String(local.config.delayed_message || ''),
  set: (value: string) => {
    local.config = { ...local.config, delayed_message: value }
  },
})

const delayedSeconds = computed({
  get: () => Number(local.config.delay_seconds || 60),
  set: (value: number) => {
    local.config = { ...local.config, delay_seconds: value }
  },
})

const adminMessageText = computed({
  get: () => String(local.config.admin_message || ''),
  set: (value: string) => {
    local.config = { ...local.config, admin_message: value }
  },
})

const adminMessenger = computed({
  get: () => String(local.config.admin_messenger || 'telegram'),
  set: (value: string) => {
    local.config = { ...local.config, admin_messenger: value }
  },
})

const promptText = computed({
  get: () => String(local.config.prompt || ''),
  set: (value: string) => {
    local.config = { ...local.config, prompt: value }
  },
})

const resultKey = computed({
  get: () => String(local.config.key || ''),
  set: (value: string) => {
    local.config = { ...local.config, key: value }
  },
})

const resultValue = computed({
  get: () => String(local.config.value || ''),
  set: (value: string) => {
    local.config = { ...local.config, value: value }
  },
})

watch(
  () => props.model,
  (model) => {
    if (!model) {
      Object.assign(local, {
        id: '',
        rule_id: '',
        action_type: 'noop',
        on_status: 'always',
        enabled: true,
        order_index: 1,
        config: {},
      })
      actionPreset.value = 'noop'
      return
    }
    Object.assign(local, {
      ...model,
      config: { ...(model.config || {}) },
    })
    if (model.action_type === 'webhook') {
      actionPreset.value = String(model.config?.action_kind || 'webhook_api_call')
    } else {
      actionPreset.value = model.action_type
    }
  },
  { immediate: true },
)

const onSelectPreset = (value: string) => {
  actionPreset.value = value
  if (value.startsWith('webhook_')) {
    local.action_type = 'webhook'
    local.config = { ...local.config, action_kind: value }
    return
  }
  local.action_type = value as FunctionRuleAction['action_type']
  local.config = {}
}

const onSelectTool = (value: string) => {
  const toolId = value === '__none__' ? null : value
  const selectedTool = availableWebhookTools.value.find((tool) => tool.id === toolId)
  const existingPayload = local.config.payload && typeof local.config.payload === 'object'
    ? { ...local.config.payload }
    : {}
  const schemaProps = selectedTool?.input_schema?.properties
  if (schemaProps && typeof schemaProps === 'object') {
    Object.entries(schemaProps).forEach(([key, cfg]: [string, any]) => {
      if (existingPayload[key] === undefined && cfg?.default !== undefined) {
        existingPayload[key] = cfg.default
      }
    })
  }
  local.config = {
    ...local.config,
    tool_id: toolId,
    url: selectedTool?.endpoint || local.config.url || '',
    method: selectedTool?.http_method || local.config.method || 'POST',
    payload: existingPayload,
  }
}

const getTypeLabel = (type: string) => {
  if (type === 'number' || type === 'integer') return 'число'
  if (type === 'boolean') return 'да/нет'
  if (type === 'array') return 'массив'
  if (type === 'object') return 'объект'
  return 'текст'
}

const getMappingLabel = (target: string) => {
  if (target === 'path') return 'path'
  if (target === 'query') return 'query'
  if (target === 'header') return 'header'
  return 'body'
}

const getPayloadFieldValue = (key: string, fallback: any) => {
  const payload = local.config.payload
  if (payload && typeof payload === 'object' && payload[key] !== undefined) return payload[key]
  return fallback
}

const setPayloadFieldValue = (key: string, value: any) => {
  const payload = local.config.payload && typeof local.config.payload === 'object'
    ? { ...local.config.payload }
    : {}
  payload[key] = value
  local.config = { ...local.config, payload }
}

const extractVariableToken = (value: any): string | null => {
  if (typeof value !== 'string') return null
  const match = value.trim().match(/^\{\{\s*([a-zA-Z_][\w]*)\s*\}\}$/)
  return match?.[1] || null
}

const getVariableSelectValue = (paramName: string) => {
  const currentValue = getPayloadFieldValue(paramName, undefined)
  const token = extractVariableToken(currentValue)
  if (token) return `var:${token}`
  if (newVariableDraft[paramName]?.name) return '__create__'
  return '__none__'
}

const isCreatingVariableForParam = (paramName: string) => getVariableSelectValue(paramName) === '__create__'

const normalizeVariableType = (type: string) => {
  if (type === 'number' || type === 'integer') return 'number'
  if (type === 'boolean') return 'boolean'
  return 'string'
}

const onNewVariableDraftChange = (
  paramName: string,
  field: 'name' | 'type' | 'description',
  value: string,
) => {
  const current = newVariableDraft[paramName] || {
    name: '',
    type: 'string',
    description: '',
  }
  newVariableDraft[paramName] = {
    ...current,
    [field]: value,
  }
}

const onVariableSelectChange = (param: ToolSchemaParam, value: string) => {
  if (value === '__none__') {
    delete newVariableDraft[param.name]
    const payload = local.config.payload && typeof local.config.payload === 'object'
      ? { ...local.config.payload }
      : {}
    delete payload[param.name]
    local.config = { ...local.config, payload }
    return
  }
  if (value === '__create__') {
    const defaultName = `${param.name}_value`
    newVariableDraft[param.name] = newVariableDraft[param.name] || {
      name: defaultName,
      type: normalizeVariableType(param.type),
      description: param.description || `Переменная для ${param.name}`,
    }
    return
  }
  if (value.startsWith('var:')) {
    const variableName = value.slice(4).trim()
    if (!variableName) return
    delete newVariableDraft[param.name]
    setPayloadFieldValue(param.name, `{{${variableName}}}`)
  }
}

const createVariableAndBind = (param: ToolSchemaParam) => {
  const draft = newVariableDraft[param.name]
  const variableName = String(draft?.name || '').trim()
  if (!variableName) return
  const variableType = String(draft?.type || normalizeVariableType(param.type))
  const variableDescription = String(draft?.description || '').trim()
  emit('add-rule-variable', {
    name: variableName,
    type: variableType === 'number' || variableType === 'boolean' ? variableType : 'string',
    description: variableDescription || param.description || `Переменная для ${param.name}`,
  })
  setPayloadFieldValue(param.name, `{{${variableName}}}`)
  delete newVariableDraft[param.name]
}

const submitAction = () => {
  const payloadConfig = { ...local.config }

  if (isWebhookPreset.value) {
    payloadConfig.action_kind = actionPreset.value
    const linkedTool = availableWebhookTools.value.find((tool) => tool.id === payloadConfig.tool_id)
    if (!payloadConfig.url && linkedTool?.endpoint) {
      payloadConfig.url = linkedTool.endpoint
    }
    if (!payloadConfig.method && linkedTool?.http_method) {
      payloadConfig.method = linkedTool.http_method
    }
    payloadConfig.method = String(payloadConfig.method || 'POST').toUpperCase()
    if (actionPreset.value === 'webhook_api_call') {
      // keep payload as is
    } else if (actionPreset.value === 'webhook_delayed_message') {
      payloadConfig.payload = {
        message: String(payloadConfig.delayed_message || ''),
        delay_seconds: Number(payloadConfig.delay_seconds || 60),
      }
    } else if (actionPreset.value === 'webhook_admin_message') {
      payloadConfig.payload = {
        message: String(payloadConfig.admin_message || ''),
        messenger: String(payloadConfig.admin_messenger || 'telegram'),
      }
    }
  }

  emit('submit', { ...local, config: payloadConfig })
  emit('update:open', false)
}
</script>
