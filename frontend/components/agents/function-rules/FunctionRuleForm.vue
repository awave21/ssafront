<template>
  <div class="min-w-0 space-y-4" :class="!canEdit ? 'opacity-80' : ''">
    <div :class="!canEdit ? 'pointer-events-none' : ''" class="space-y-4">
      <!-- Название + описание -->
      <div class="space-y-4 rounded-2xl bg-slate-100 p-5">
        <div class="space-y-1.5">
          <label class="flex items-center gap-1.5 text-sm font-semibold text-slate-900">
            Название функции <span class="text-red-500">*</span>
            <FieldHint
              title="Название функции"
              text="Короткое имя на английском в snake_case (например: create_booking). Модель видит это имя как имя инструмента — по нему она решает, вызывать функцию или нет."
            />
          </label>
          <Input
            :model-value="local.name"
            placeholder="Например: create_booking"
            class="bg-white font-mono placeholder:font-mono placeholder:text-slate-400"
            @update:model-value="onNameInput"
            @blur="emitModelUpdate"
          />
          <p class="text-xs text-slate-500">Осмысленное и описательное название на английском. Оно влияет на успешность применения функции.</p>
        </div>

        <div class="space-y-1.5">
          <label class="flex items-center gap-1.5 text-sm font-semibold text-slate-900">
            Описание функции <span class="text-red-500">*</span>
            <FieldHint
              title="Описание функции"
              text="Инструкция для модели: КОГДА вызывать функцию и ЧТО она делает. Модель читает это как описание инструмента. Чем яснее — тем реже ложные вызовы."
            />
          </label>
          <Textarea
            v-model="functionDescription"
            placeholder="Введите чёткую инструкцию — что должна делать функция. Например: Сохранение деталей заказа"
            class="min-h-[110px] bg-white"
          />
          <p class="text-xs text-slate-500">Чёткое описание помогает модели понять, когда и как вызывать функцию.</p>
        </div>
      </div>

      <!-- Параметры -->
      <div class="space-y-4 rounded-2xl bg-slate-100 p-5">
        <div class="flex items-center justify-between gap-3">
          <div class="flex items-center gap-2">
            <span class="text-sm font-semibold text-slate-900">Параметры</span>
            <FieldHint
              title="Параметры функции"
              text="Что именно модель должна извлечь из сообщения клиента перед вызовом функции. Каждый параметр — часть JSON Schema инструмента. Опишите смысл словами — модель сама распознает значения в тексте."
            />
            <span v-if="functionParameters.length" class="text-xs font-medium text-slate-500">{{ functionParameters.length }}/{{ MAX_PARAMETERS }}</span>
          </div>
          <button
            type="button"
            :disabled="functionParameters.length >= MAX_PARAMETERS"
            class="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-[0_1px_2px_rgba(0,0,0,0.02)] transition-colors hover:border-primary/40 hover:text-primary disabled:cursor-not-allowed disabled:opacity-50"
            @click="addParameter"
          >
            + Добавить параметр
          </button>
        </div>

        <div v-if="functionParameters.length === 0" class="py-4 text-center text-sm text-slate-400">
          Параметров пока нет. Нажмите «+ Добавить параметр».
        </div>

        <div v-else class="space-y-3">
          <div
            v-for="(parameter, index) in functionParameters"
            :key="`param_${index}`"
            class="space-y-3 rounded-xl bg-white p-4"
          >
            <div class="grid gap-3 sm:grid-cols-[1fr_180px]">
              <div class="space-y-1.5">
                <label class="text-xs font-semibold text-slate-700">Имя параметра</label>
                <Input
                  :model-value="parameter.name"
                  placeholder="Например: client_name"
                  class="font-mono placeholder:font-mono placeholder:text-slate-400"
                  @update:model-value="updateParameter(index, 'name', $event)"
                />
              </div>
              <div class="space-y-1.5">
                <label class="text-xs font-semibold text-slate-700">Тип параметра</label>
                <Select :model-value="parameter.type" @update:model-value="updateParameter(index, 'type', $event)">
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="string">Текстовый</SelectItem>
                    <SelectItem value="number">Числовой</SelectItem>
                    <SelectItem value="boolean">Логический (Да/Нет)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div class="space-y-1.5">
              <label class="text-xs font-semibold text-slate-700">Описание параметра</label>
              <Input
                :model-value="parameter.description"
                placeholder="Например: Имя клиента для записи"
                @update:model-value="updateParameter(index, 'description', $event)"
              />
            </div>

            <div class="flex items-center justify-between pt-1">
              <label class="flex cursor-pointer items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  class="h-4 w-4 rounded border-slate-300 text-primary focus:ring-primary"
                  :checked="parameter.required"
                  @change="updateParameter(index, 'required', ($event.target as HTMLInputElement).checked ? '1' : '')"
                />
                <span class="font-medium">Обязательный</span>
                <span class="text-xs text-slate-400">— {{ parameter.required ? 'обязательный' : 'необязательный' }}</span>
              </label>
              <button
                type="button"
                class="flex h-8 w-8 items-center justify-center rounded-xl text-slate-400 transition-colors hover:bg-red-50 hover:text-red-600"
                title="Удалить параметр"
                @click="removeParameter(index)"
              >
                <X class="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Реакция на выполнение -->
      <div class="space-y-3 rounded-2xl bg-slate-100 p-5">
        <div class="flex items-center gap-1.5 text-sm font-semibold text-slate-900">
          Реакция на выполнение функции
          <FieldHint
            title="Реакция на результат"
            text="Что бот сделает после успешного выполнения функции. «AI ответит сам» — модель сформулирует ответ по данным функции. «Отправить сообщение» — фиксированный текст. «Инструкция для AI» — подсказка модели, как ответить. «Промолчать» — только тихое действие без сообщения клиенту."
          />
        </div>
        <OptionCardPicker
          :items="reactionCards"
          :model-value="local.reaction_mode"
          :disabled="!canEdit"
          :columns="4"
          @update:model-value="local.reaction_mode = $event as any"
        />
        <div v-if="local.reaction_mode === 'send_message'" class="space-y-1.5">
          <label class="text-xs font-semibold text-slate-700">Текст сообщения</label>
          <Textarea v-model="local.reaction_message" class="bg-white" />
        </div>
        <div v-if="local.reaction_mode === 'ai_instruction'" class="space-y-1.5">
          <label class="text-xs font-semibold text-slate-700">Инструкция для AI</label>
          <Textarea v-model="local.reaction_instruction" class="bg-white" />
        </div>
      </div>

      <!-- Сценарий после выполнения -->
      <div class="space-y-3 rounded-2xl bg-slate-100 p-5">
        <div class="flex items-center gap-1.5 text-sm font-semibold text-slate-900">
          Сценарий после выполнения
          <FieldHint
            title="Что дальше с диалогом"
            text="«Продолжить» — обычная работа бота. «Пауза» — бот замолкает, ждёт сотрудника или события возобновления. «Дополнить промпт» — к системному промпту на СЛЕДУЮЩИЙ ход подмешивается указанный текст (не сохраняется навсегда)."
          />
        </div>
        <OptionCardPicker
          :items="postScenarioCards"
          :model-value="local.post_scenario"
          :disabled="!canEdit"
          @update:model-value="local.post_scenario = $event as any"
        />
        <div v-if="local.post_scenario === 'augment_prompt'" class="space-y-1.5">
          <label class="text-xs font-semibold text-slate-700">Что добавить в промпт</label>
          <Textarea v-model="local.post_scenario_prompt" class="bg-white" />
        </div>
      </div>

      <!-- Дополнительные настройки -->
      <div class="space-y-3 rounded-2xl bg-slate-100 p-5">
        <div class="flex items-center gap-1.5 text-sm font-semibold text-slate-900">
          Дополнительно
          <FieldHint
            title="Тонкие настройки правила"
            text="Приоритет управляет порядком проверки правил (меньше — раньше). Тестовый режим пишет в лог, что правило сработало бы, но реакцию/действия не применяет. «Остановить следующие правила» — после срабатывания этого правила остальные правила той же фазы пропускаются."
          />
        </div>
        <!-- Три колонки только на широких экранах: на планшете карточка ужимается
             до ~200px, и «по возрастанию» рядом с полем ввода уже не помещается. -->
        <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div class="flex flex-col justify-between rounded-xl bg-white p-4">
            <label class="flex items-center gap-1.5 text-xs font-semibold text-slate-700">
              Приоритет
              <FieldHint text="Меньше = раньше срабатывает. По умолчанию 100." />
            </label>
            <div class="mt-2 flex items-center gap-2">
              <Input v-model.number="local.priority" type="number" min="1" class="h-9 w-24 bg-slate-50" />
              <span class="text-[11px] text-slate-500">по возрастанию</span>
            </div>
          </div>
          <div class="flex flex-col justify-between rounded-xl bg-white p-4">
            <label class="flex items-center justify-between gap-2 text-xs font-semibold text-slate-700">
              <span class="inline-flex items-center gap-1.5">
                Тестовый режим
                <FieldHint text="Правило срабатывает, но реакции и действия не применяются — только запись в журнал выполнения. Удобно проверить, на каких сообщениях правило сработает, прежде чем включать боевой режим." />
              </span>
              <Switch :model-value="local.dry_run" @update:model-value="local.dry_run = !!$event" />
            </label>
            <p class="mt-2 text-[11px] text-slate-500">Пишет в журнал, но не применяет реакцию и действия.</p>
          </div>
          <div class="flex flex-col justify-between rounded-xl bg-white p-4">
            <label class="flex items-center justify-between gap-2 text-xs font-semibold text-slate-700">
              <span class="inline-flex items-center gap-1.5">
                Остановить следующие
                <FieldHint text="После срабатывания правила остальные правила той же фазы не проверяются. Полезно, если несколько правил могут совпасть, но нужно сработать только этому." />
              </span>
              <Switch :model-value="local.stop_on_match" @update:model-value="local.stop_on_match = !!$event" />
            </label>
            <p class="mt-2 text-[11px] text-slate-500">Прерывает цепочку правил.</p>
          </div>
        </div>
        <div v-if="local.dry_run" class="rounded-xl border border-amber-200 bg-amber-50/60 px-4 py-2.5 text-xs text-amber-800">
          Тестовый режим включён: правило пишется в журнал, но реакция и действия не применяются.
        </div>
      </div>

      <!-- Действия правила -->
      <div class="space-y-3 rounded-2xl bg-slate-100 p-5">
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
    </div>

    <div v-if="showCancel" class="flex justify-end gap-2">
      <Button variant="outline" @click="$emit('cancel')">Отмена</Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, reactive, ref, watch } from 'vue'
import type { Component } from 'vue'
import { ArrowRight, Bot, FileText, MessageSquare, Pause, Sparkles, VolumeX, X } from 'lucide-vue-next'
import { Button } from '~/components/ui/button'
import { Input } from '~/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '~/components/ui/select'
import { Switch } from '~/components/ui/switch'
import { Textarea } from '~/components/ui/textarea'
import RuleActionsTable from '~/components/agents/function-rules/RuleActionsTable.vue'
import OptionCardPicker, { type OptionCardItem } from '~/components/agents/function-rules/OptionCardPicker.vue'
import FieldHint from '~/components/agents/settings/FieldHint.vue'
import type { Tool } from '~/types/tool'
import type { FunctionRule } from '~/types/functionRule'
import type { FunctionRuleAction } from '~/types/ruleAction'

const MAX_PARAMETERS = 30

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
  { value: 'send_message', label: 'Отправить сообщение', description: 'Отправить пользователю заранее заготовленный текст.' },
  { value: 'ai_instruction', label: 'Инструкция для AI', description: 'Дать AI дополнительную инструкцию для формирования ответа.' },
  { value: 'ai_self_reply', label: 'Позволить AI ответить самому', description: 'ИИ сам формирует ответ по результату функции без дополнительных инструкций.' },
  { value: 'silent', label: 'Промолчать', description: 'Функция срабатывает, но пользователю ничего не отправляется.' },
]

const postScenarioOptions = [
  { value: 'continue', label: 'Продолжить диалог', description: 'После выполнения функции диалог продолжится без изменений.' },
  { value: 'pause', label: 'Поставить на паузу', description: 'Диалог будет приостановлен до отдельного события возобновления.' },
  { value: 'augment_prompt', label: 'Дополнить промпт', description: 'К системному промпту добавится дополнительный текст на следующий ход.' },
]

// Описания переехали внутрь карточек, поэтому отдельная зелёная плашка с текстом
// выбранного варианта больше не нужна — теперь видно все варианты сразу.
const REACTION_ICONS: Record<string, Component> = {
  send_message: MessageSquare,
  ai_instruction: Sparkles,
  ai_self_reply: Bot,
  silent: VolumeX,
}
const POST_SCENARIO_ICONS: Record<string, Component> = {
  continue: ArrowRight,
  pause: Pause,
  augment_prompt: FileText,
}

const reactionCards = computed<OptionCardItem[]>(() =>
  reactionOptions.map((o) => ({ ...o, icon: REACTION_ICONS[o.value] || Bot })),
)
const postScenarioCards = computed<OptionCardItem[]>(() =>
  postScenarioOptions.map((o) => ({ ...o, icon: POST_SCENARIO_ICONS[o.value] || ArrowRight })),
)

type FunctionParameterUi = {
  name: string
  type: 'string' | 'number' | 'boolean'
  description: string
  required: boolean
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
  // Сохраняем оригинальные trigger_mode / condition_type, если они уже есть
  // в модели (правило создано через API/SQL с schedule_time / semantic и т.п.).
  // Только для новых правил без trigger_mode/condition_type используем дефолт.
  // Раньше здесь был жёсткий 'post_tool'+'always' — это затирало реальные значения
  // при любом emit и полностью ломало правила с расписанием, семантикой, возвратом.
  emit('update:model', {
    ...local,
    trigger_mode: local.trigger_mode || props.model.trigger_mode || 'post_tool',
    condition_type: local.condition_type || props.model.condition_type || 'always',
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
  const requiredList = Array.isArray((schema as any)?.required) ? (schema as any).required : []
  const requiredSet = new Set(requiredList.map(String))
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
      required: requiredSet.has(name),
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

  const required = functionParameters.value
    .filter((item) => item.required && String(item.name || '').trim())
    .map((item) => String(item.name).trim())

  local.condition_config = {
    ...(local.condition_config as Record<string, any>),
    tool_args_schema: {
      type: 'object',
      properties,
      ...(required.length ? { required } : {}),
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
  if (functionParameters.value.length >= MAX_PARAMETERS) return
  functionParameters.value = [
    ...functionParameters.value,
    { name: getNextParameterName(), type: 'string', description: '', required: false },
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
  } else if (field === 'required') {
    next[index] = {
      ...next[index],
      required: Boolean(value),
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
