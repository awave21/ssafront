<template>
  <KnowledgeSheetShell
    :open="isOpen"
    :title="scenario ? 'Редактирование сценария' : 'Создание сценария'"
    :subtitle="scenario?.name"
    :loading="saving"
    :submit-disabled="!isValid"
    size="viewport70"
    @close="$emit('close')"
    @cancel="$emit('close')"
    @submit="handleSave"
  >
    <template #header-actions>
      <div class="flex items-center gap-2 mr-2">
        <span class="text-xs text-slate-500">Активен</span>
        <Switch v-model="form.enabled" />
      </div>
    </template>

    <div class="p-6 space-y-8">
      <!-- Section: General Info -->
      <div class="space-y-4">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="text-sm font-medium text-slate-700">Название сценария</label>
            <input
              v-model.trim="form.name"
              type="text"
              placeholder="Например: Приветствие новых клиентов"
              class="mt-1.5 w-full rounded-md border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm text-slate-900 focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10 focus:bg-white transition-all duration-300 outline-none"
            />
          </div>
          <div>
            <label class="text-sm font-medium text-slate-700">Приоритет</label>
            <input
              v-model.number="form.priority"
              type="number"
              class="mt-1.5 w-full rounded-md border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm text-slate-900 focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10 focus:bg-white transition-all duration-300 outline-none"
            />
          </div>
        </div>
      </div>

      <!-- Section: Trigger (WHEN) -->
      <div class="space-y-4 rounded-2xl border border-indigo-100 bg-indigo-50/30 p-5">
        <div class="flex items-center gap-2 mb-2">
          <div class="h-8 w-8 rounded-lg bg-indigo-100 flex items-center justify-center">
            <Zap class="w-4 h-4 text-indigo-600" />
          </div>
          <h3 class="font-bold text-slate-900 text-sm uppercase tracking-wider">Когда (Триггер)</h3>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="text-sm font-medium text-slate-700">Событие</label>
            <select
              v-model="form.trigger_mode"
              class="mt-1.5 w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-900 focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10 focus:bg-white transition-all duration-300 outline-none"
            >
              <option v-for="(label, mode) in triggerLabels" :key="mode" :value="mode">
                {{ label }}
              </option>
            </select>
            <p class="mt-1 text-[10px] text-slate-500">{{ triggerHints[form.trigger_mode] }}</p>
          </div>
          <div>
            <label class="text-sm font-medium text-slate-700">Тип условия</label>
            <select
              v-model="form.condition_type"
              class="mt-1.5 w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-900 focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10 focus:bg-white transition-all duration-300 outline-none"
            >
              <option v-for="(label, type) in conditionLabels" :key="type" :value="type">
                {{ label }}
              </option>
            </select>
          </div>
        </div>

        <!-- Dynamic Condition Config -->
        <div class="mt-4 pt-4 border-t border-indigo-100/50">
          <!-- Keyword -->
          <div v-if="form.condition_type === 'keyword'" class="space-y-2">
            <label class="text-sm font-medium text-slate-700">Ключевые слова (через запятую)</label>
            <input
              v-model="keywordInput"
              type="text"
              placeholder="цена, сколько стоит, прайс"
              class="w-full rounded-md border border-slate-200 bg-white px-4 py-2.5 text-sm outline-none focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10 transition-all"
            />
          </div>

          <!-- Client Return Gap -->
          <div v-else-if="form.condition_type === 'client_return_gap'" class="space-y-2">
            <label class="text-sm font-medium text-slate-700 flex items-center gap-1.5">
              Интервал отсутствия (в днях)
              <TooltipProvider :delay-duration="300">
                <Tooltip>
                  <TooltipTrigger as-child>
                    <HelpCircle class="w-3.5 h-3.5 text-slate-400 cursor-help" />
                  </TooltipTrigger>
                  <TooltipContent side="right">
                    <p class="text-xs">Сценарий сработает, если клиент не писал более указанного количества дней</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </label>
            <input
              v-model.number="form.condition_config.min_days"
              type="number"
              step="0.1"
              class="w-full rounded-md border border-slate-200 bg-white px-4 py-2.5 text-sm outline-none focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10 transition-all"
            />
          </div>

          <!-- Dialog Source -->
          <div v-else-if="form.condition_type === 'dialog_source'" class="space-y-2">
            <label class="text-sm font-medium text-slate-700">Платформы</label>
            <div class="flex flex-wrap gap-3 mt-2">
              <label v-for="platform in ['telegram', 'whatsapp', 'web']" :key="platform" class="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  :value="platform"
                  v-model="form.condition_config.platforms"
                  class="rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                />
                <span class="text-sm text-slate-700 capitalize">{{ platform }}</span>
              </label>
            </div>
          </div>

          <!-- Schedule Time -->
          <div v-else-if="form.condition_type === 'schedule_time'" class="grid grid-cols-2 gap-4">
            <div>
              <label class="text-sm font-medium text-slate-700">С (ЧЧ:ММ)</label>
              <input
                v-model="form.condition_config.start_time"
                type="time"
                class="mt-1.5 w-full rounded-md border border-slate-200 bg-white px-4 py-2 text-sm outline-none focus:border-indigo-400 transition-all"
              />
            </div>
            <div>
              <label class="text-sm font-medium text-slate-700">До (ЧЧ:ММ)</label>
              <input
                v-model="form.condition_config.end_time"
                type="time"
                class="mt-1.5 w-full rounded-md border border-slate-200 bg-white px-4 py-2 text-sm outline-none focus:border-indigo-400 transition-all"
              />
            </div>
          </div>

          <!-- Schedule Weekday -->
          <div v-else-if="form.condition_type === 'schedule_weekday'" class="space-y-2">
            <label class="text-sm font-medium text-slate-700">Дни недели</label>
            <div class="flex flex-wrap gap-2 mt-2">
              <button
                v-for="(label, day) in weekdayLabels"
                :key="day"
                type="button"
                @click="toggleWeekday(Number(day))"
                class="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors border"
                :class="form.condition_config.weekdays?.includes(Number(day)) 
                  ? 'bg-indigo-600 text-white border-indigo-600' 
                  : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'"
              >
                {{ label }}
              </button>
            </div>
          </div>

          <!-- Start Param -->
          <div v-else-if="form.condition_type === 'start_param'" class="space-y-2">
            <label class="text-sm font-medium text-slate-700">Параметр запуска (tg_start)</label>
            <input
              v-model="form.condition_config.equals"
              type="text"
              placeholder="promo_2024"
              class="w-full rounded-md border border-slate-200 bg-white px-4 py-2.5 text-sm outline-none focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10 transition-all"
            />
          </div>

          <div v-else-if="form.condition_type === 'always'">
            <p class="text-xs text-slate-500 italic">Условие всегда истинно при срабатывании триггера.</p>
          </div>
          <div v-else>
            <p class="text-xs text-slate-400 italic">Настройка для этого типа условия будет доступна в ближайшее время.</p>
          </div>
        </div>
      </div>

      <!-- Section: Actions (THEN) -->
      <div class="space-y-4 rounded-2xl border border-emerald-100 bg-emerald-50/30 p-5">
        <div class="flex items-center justify-between mb-2">
          <div class="flex items-center gap-2">
            <div class="h-8 w-8 rounded-lg bg-emerald-100 flex items-center justify-center">
              <Play class="w-4 h-4 text-emerald-600" />
            </div>
            <h3 class="font-bold text-slate-900 text-sm uppercase tracking-wider">Тогда (Действия)</h3>
          </div>
          <button
            @click="addAction"
            class="text-xs font-bold text-emerald-700 hover:text-emerald-800 flex items-center gap-1 bg-emerald-100 px-3 py-1.5 rounded-lg transition-colors"
          >
            <Plus class="w-3 h-3" />
            Добавить действие
          </button>
        </div>

        <button
          v-if="form.actions.length === 0"
          type="button"
          class="w-full text-center py-8 border-2 border-dashed border-emerald-100 rounded-xl transition-all duration-300 hover:-translate-y-0.5 hover:border-emerald-200 hover:bg-emerald-50/30"
          @click="addAction"
        >
          <p class="text-sm text-slate-400">Действия не добавлены. Сценарий ничего не сделает.</p>
        </button>

        <div v-else class="space-y-3">
          <div
            v-for="(action, index) in form.actions"
            :key="`${index}-${action.action_type}`"
            class="bg-white border border-emerald-100 rounded-xl p-4 shadow-sm relative group"
          >
            <button
              @click="removeAction(index)"
              class="absolute -right-2 -top-2 h-6 w-6 rounded-full bg-white border border-red-100 text-red-500 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity shadow-sm hover:bg-red-50"
            >
              <X class="w-3 h-3" />
            </button>

            <div class="space-y-4">
              <div>
                <label class="text-xs font-medium text-slate-500 mb-1.5 block">Тип действия</label>
                <OptionCardPicker
                  :items="scenarioActionItems"
                  :model-value="action.action_type"
                  @update:model-value="changeActionType(action, index, $event)"
                />
              </div>

              <div>
                <!-- Action Specific Config -->
                <div v-if="isMessageLikeAction(action.action_type)">
                  <label class="text-xs font-medium text-slate-500 mb-1 block">Текст сообщения</label>
                  <textarea
                    v-model="action.config.message"
                    rows="2"
                    class="w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs outline-none focus:border-emerald-400 transition-all resize-none"
                  ></textarea>
                  
                  <div v-if="isDelayedAction(action.action_type)" class="mt-2 flex items-center gap-4">
                    <div class="flex items-center gap-2">
                      <label class="text-[10px] font-bold text-slate-400 uppercase">Задержка:</label>
                      <input
                        v-model.number="delayValue[index]"
                        type="number"
                        class="w-16 rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-xs outline-none"
                      />
                    </div>
                    <select
                      v-model="delayUnit[index]"
                      class="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-xs outline-none"
                    >
                      <option value="seconds">секунд</option>
                      <option value="minutes">минут</option>
                      <option value="hours">часов</option>
                      <option value="days">дней</option>
                    </select>
                  </div>
                </div>
                <div v-else-if="isSetTagAction(action.action_type)">
                  <label class="text-xs font-medium text-slate-500 mb-1 block">Название тега</label>
                  <input
                    v-model="action.config.tag"
                    type="text"
                    class="w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs outline-none focus:border-emerald-400 transition-all"
                  />
                </div>
                <div v-else-if="isAugmentPromptAction(action.action_type)">
                  <label class="text-xs font-medium text-slate-500 mb-1 block">Текст для дополнения промпта</label>
                  <textarea
                    v-model="action.config.instruction"
                    rows="3"
                    placeholder="Например: Отвечай кратко, в деловом тоне, и предлагай следующий шаг."
                    class="w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs outline-none focus:border-emerald-400 transition-all resize-none"
                  ></textarea>
                  <p class="mt-1 text-[10px] text-slate-500">
                    Эта инструкция будет добавлена в контекст агента перед формированием ответа.
                  </p>
                </div>
                <div v-else-if="isSetResultAction(action.action_type)">
                  <label class="text-xs font-medium text-slate-500 mb-1 block">Готовый ответ</label>
                  <textarea
                    v-model="action.config.result"
                    rows="3"
                    placeholder="Текст, который уйдёт клиенту вместо ответа модели"
                    class="w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs outline-none focus:border-emerald-400 transition-all resize-none"
                  ></textarea>
                  <p class="mt-1 text-[10px] text-slate-500">
                    Обрывает цепочку: LLM не вызывается, клиент получает этот текст как есть.
                  </p>
                </div>
                <div v-else-if="isSetVariableAction(action.action_type)" class="space-y-2">
                  <div class="grid grid-cols-2 gap-2">
                    <input
                      v-model="action.config.name"
                      type="text"
                      placeholder="Имя переменной"
                      class="w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs outline-none focus:border-emerald-400 transition-all"
                    />
                    <select
                      v-model="action.config.operation"
                      class="w-full rounded-md border border-slate-200 bg-slate-50 px-2 py-1.5 text-xs outline-none focus:border-emerald-400 transition-all"
                    >
                      <option value="set">Записать значение</option>
                      <option value="increment">Увеличить на</option>
                      <option value="clear">Очистить</option>
                    </select>
                  </div>
                  <input
                    v-if="action.config.operation !== 'clear'"
                    v-model="action.config.value"
                    type="text"
                    placeholder="Значение (можно подставлять переменные)"
                    class="w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs outline-none focus:border-emerald-400 transition-all"
                  />
                  <p class="text-[10px] text-slate-500">
                    Значение сохраняется в диалоге и доступно дальше по разговору.
                  </p>
                </div>
                <div v-else-if="isNotifyAdminAction(action.action_type)" class="space-y-2">
                  <label class="text-xs font-medium text-slate-500 mb-1 block">Текст уведомления</label>
                  <textarea
                    v-model="action.config.message"
                    rows="2"
                    placeholder="Например: клиент запросил счёт — нужен менеджер"
                    class="w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs outline-none focus:border-emerald-400 transition-all resize-none"
                  ></textarea>
                  <div class="grid grid-cols-2 gap-2">
                    <input
                      v-model="action.config.chat_id"
                      type="text"
                      placeholder="Chat ID (опц.)"
                      class="w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs outline-none focus:border-emerald-400 transition-all"
                    />
                    <input
                      v-model="action.config.bot_token"
                      type="text"
                      placeholder="Токен бота (опц.)"
                      class="w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs outline-none focus:border-emerald-400 transition-all"
                    />
                  </div>
                  <label class="flex items-center gap-2 text-[10px] text-slate-500">
                    <input v-model="action.config.include_context" type="checkbox" class="accent-emerald-500" />
                    Приложить последнее сообщение клиента
                  </label>
                  <p class="text-[10px] text-slate-500">
                    Если Chat ID и токен пустые — берутся из настроек агента, и уведомления там должны быть включены.
                  </p>
                </div>
                <div v-else-if="isHandoffAction(action.action_type)" class="space-y-2">
                  <label class="text-xs font-medium text-slate-500 mb-1 block">Сообщение клиенту (опц.)</label>
                  <textarea
                    v-model="action.config.client_message"
                    rows="2"
                    placeholder="Например: передаю вас администратору, он ответит в ближайшее время"
                    class="w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs outline-none focus:border-emerald-400 transition-all resize-none"
                  ></textarea>
                  <input
                    v-model="action.config.reason"
                    type="text"
                    placeholder="Причина для администратора"
                    class="w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs outline-none focus:border-emerald-400 transition-all"
                  />
                  <label class="flex items-center gap-2 text-[10px] text-slate-500">
                    <input v-model="action.config.notify_admin" type="checkbox" class="accent-emerald-500" />
                    Уведомить администратора в Telegram
                  </label>
                  <p class="text-[10px] text-slate-500">
                    Ставит диалог на паузу — агент перестаёт отвечать, пока оператор не вернёт его в работу.
                  </p>
                </div>
                <div v-else-if="isWebhookAction(action.action_type)" class="space-y-2">
                  <div class="flex items-center gap-2">
                    <select
                      v-model="action.config.method"
                      class="w-24 shrink-0 rounded-md border border-slate-200 bg-slate-50 px-2 py-1.5 text-xs outline-none focus:border-emerald-400 transition-all"
                    >
                      <option value="POST">POST</option>
                      <option value="GET">GET</option>
                      <option value="PUT">PUT</option>
                      <option value="PATCH">PATCH</option>
                    </select>
                    <input
                      v-model="action.config.url"
                      type="url"
                      placeholder="https://example.com/webhook/..."
                      class="flex-1 min-w-0 rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs outline-none focus:border-emerald-400 transition-all"
                    />
                  </div>
                  <textarea
                    v-model="webhookPayloadText[index]"
                    rows="3"
                    :placeholder="webhookPayloadPlaceholder"
                    class="w-full rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs outline-none focus:border-emerald-400 transition-all resize-none"
                  ></textarea>
                  <p v-pre class="text-[10px] text-slate-500">
                    Доступные переменные в payload:
                    <code class="bg-slate-100 px-1 rounded">{{session_id}}</code>,
                    <code class="bg-slate-100 px-1 rounded">{{input_message}}</code>,
                    <code class="bg-slate-100 px-1 rounded">{{agent_timezone}}</code>
                  </p>
                </div>
                <div v-else>
                  <p class="text-[10px] text-slate-400 italic pt-4">Дополнительных настроек не требуется.</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </KnowledgeSheetShell>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Zap, Play, Plus, X, HelpCircle } from 'lucide-vue-next'
import { Switch } from '~/components/ui/switch'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '~/components/ui/tooltip'
import KnowledgeSheetShell from '~/components/knowledge/KnowledgeSheetShell.vue'
import type { Scenario, ScenarioUpsertPayload, ScenarioAction } from '~/types/scenario'
import { functionRuleActionDescriptions, functionRuleActionLabels } from '~/types/ruleAction'
import { functionRuleActionIcons } from '~/utils/ruleActionIcons'
import { soonActionItems } from '~/utils/ruleActionSoon'
import OptionCardPicker, { type OptionCardItem } from '~/components/agents/function-rules/OptionCardPicker.vue'

const props = withDefaults(
  defineProps<{
    isOpen: boolean
    scenario: Scenario | null
    agentId: string
    saving?: boolean
  }>(),
  { saving: false }
)

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save', data: ScenarioUpsertPayload): void
}>()

/** В шаблоне нельзя оставлять `{{...}}` в статическом placeholder — парсер Vue ломается. */
const webhookPayloadPlaceholder =
  'Payload JSON (опционально): {"event":"new_dialog","session":"{{session_id}}"}'

const triggerLabels = {
  client_message: 'Сообщение клиента',
  agent_message: 'Сообщение агента',
  manager_message: 'Сообщение менеджера',
  client_return: 'Возврат клиента',
  dialog_start: 'Начало диалога',
  send_error: 'Ошибка отправки',
  spend_limit: 'Лимит трат',
  pre_run: 'Перед запуском',
  post_run: 'После завершения',
  post_tool: 'После инструмента'
}

const triggerHints = {
  client_message: 'Срабатывает, когда клиент присылает сообщение.',
  agent_message: 'Срабатывает, когда агент (ИИ) отправляет ответ.',
  manager_message: 'Срабатывает, когда менеджер пишет в чат.',
  client_return: 'Срабатывает при возврате клиента после паузы.',
  dialog_start: 'Срабатывает в самом начале нового диалога.',
  send_error: 'Срабатывает, если сообщение не удалось доставить.',
  spend_limit: 'Срабатывает при достижении лимита трат.',
  pre_run: 'Срабатывает до начала обработки сообщения агентом.',
  post_run: 'Срабатывает после завершения обработки сообщения.',
  post_tool: 'Срабатывает после выполнения конкретного инструмента.'
}

const conditionLabels = {
  keyword: 'Ключевые слова',
  regex: 'Регулярное выражение',
  semantic: 'Смысловое соответствие',
  always: 'Всегда',
  schedule_time: 'По времени',
  schedule_weekday: 'По дням недели',
  dialog_source: 'Источник диалога',
  start_param: 'Параметр запуска',
  after_scenario: 'После сценария',
  client_return_gap: 'Интервал возврата',
  json_context: 'Контекст JSON'
}

// Общий словарь с формой функции — раньше здесь был свой список, и он отставал
// от бэкенда (не было set_result). Порядок в выпадашке задаётся порядком ключей
// в functionRuleActionLabels.
// В сценарии доступны все типы действий: ограничений на уровне бэкенда нет,
// правило сценария отличается от правила функции только отсутствием tool_id.
const scenarioActionItems: OptionCardItem[] = [
  ...(
    Object.keys(functionRuleActionLabels) as Array<keyof typeof functionRuleActionLabels>
  ).map((type) => ({
    value: type,
    label: functionRuleActionLabels[type],
    description: functionRuleActionDescriptions[type],
    icon: functionRuleActionIcons[type],
  })),
  ...soonActionItems,
]

const changeActionType = (action: ScenarioAction, index: number, value: string) => {
  action.action_type = value as ScenarioAction['action_type']
  // Конфиг предыдущего типа не переносим: ensureActionConfig заполнит поля,
  // нужные новому типу, а чужие ключи иначе осели бы в JSONB мусором.
  action.config = {}
  ensureActionConfig(action, index)
}

const weekdayLabels = {
  0: 'Пн', 1: 'Вт', 2: 'Ср', 3: 'Чт', 4: 'Пт', 5: 'Сб', 6: 'Вс'
}

const form = ref<ScenarioUpsertPayload>({
  name: '',
  enabled: true,
  priority: 100,
  trigger_mode: 'client_message',
  condition_type: 'always',
  condition_config: {},
  actions: []
})

const keywordInput = ref('')
const delayValue = ref<Record<number, number>>({})
const delayUnit = ref<Record<number, string>>({})
const webhookPayloadText = ref<Record<number, string>>({})

const ensureActionConfig = (action: ScenarioAction, index: number) => {
  const t = action.action_type
  const cfg = { ...(action.config || {}) }
  if (t === 'send_message') {
    if (typeof cfg.message !== 'string') cfg.message = ''
  }
  if (t === 'send_delayed') {
    if (typeof cfg.message !== 'string') cfg.message = ''
    if (delayValue.value[index] == null) delayValue.value[index] = 60
    if (!delayUnit.value[index]) delayUnit.value[index] = 'seconds'
  }
  if (t === 'set_tag' && typeof cfg.tag !== 'string') cfg.tag = ''
  if (t === 'set_result' && typeof cfg.result !== 'string') cfg.result = ''
  if (t === 'set_variable') {
    if (typeof cfg.name !== 'string') cfg.name = ''
    if (typeof cfg.operation !== 'string') cfg.operation = 'set'
    if (typeof cfg.value !== 'string') cfg.value = ''
  }
  if (t === 'notify_admin') {
    if (typeof cfg.message !== 'string') cfg.message = ''
    // Дефолты повторяют раннер: там оба флага читаются как «включено», пока
    // явно не выставлено false. Иначе галка в UI врала бы про поведение.
    if (cfg.include_context == null) cfg.include_context = true
  }
  if (t === 'handoff_to_operator') {
    if (typeof cfg.client_message !== 'string') cfg.client_message = ''
    if (typeof cfg.reason !== 'string') cfg.reason = ''
    if (cfg.notify_admin == null) cfg.notify_admin = true
  }
  if (t === 'augment_prompt') {
    const instr = cfg.instruction ?? cfg.prompt ?? ''
    cfg.instruction = typeof instr === 'string' ? instr : String(instr)
    delete cfg.prompt
  }
  if (t === 'webhook') {
    if (typeof cfg.url !== 'string') cfg.url = cfg.url ? String(cfg.url) : ''
    if (typeof cfg.method !== 'string') cfg.method = 'POST'
    if (cfg.payload && typeof cfg.payload === 'object') {
      webhookPayloadText.value[index] = JSON.stringify(cfg.payload, null, 2)
    } else if (webhookPayloadText.value[index] == null) {
      webhookPayloadText.value[index] = ''
    }
  }
  action.config = cfg
}

watch(
  () => props.isOpen,
  (open) => {
    if (open) {
      if (props.scenario) {
        form.value = {
          name: props.scenario.name,
          enabled: props.scenario.enabled,
          priority: props.scenario.priority,
          trigger_mode: props.scenario.trigger_mode,
          condition_type: props.scenario.condition_type,
          condition_config: JSON.parse(JSON.stringify(props.scenario.condition_config || {})),
          actions: JSON.parse(JSON.stringify(props.scenario.actions || []))
        }
        
        // Initialize condition specific inputs
        if (form.value.condition_type === 'keyword') {
          keywordInput.value = (form.value.condition_config.keywords || []).join(', ')
        }
        if (form.value.condition_type === 'dialog_source' && !form.value.condition_config.platforms) {
          form.value.condition_config.platforms = []
        }
        if (form.value.condition_type === 'schedule_weekday' && !form.value.condition_config.weekdays) {
          form.value.condition_config.weekdays = []
        }

        form.value.actions.forEach((action, index) => {
          ensureActionConfig(action, index)
        })

        // Initialize delay inputs
        form.value.actions.forEach((action, index) => {
          if (action.action_type === 'send_delayed') {
            const totalSeconds = action.config.delay_seconds || 0
            if (totalSeconds % 86400 === 0 && totalSeconds > 0) {
              delayValue.value[index] = totalSeconds / 86400
              delayUnit.value[index] = 'days'
            } else if (totalSeconds % 3600 === 0 && totalSeconds > 0) {
              delayValue.value[index] = totalSeconds / 3600
              delayUnit.value[index] = 'hours'
            } else if (totalSeconds % 60 === 0 && totalSeconds > 0) {
              delayValue.value[index] = totalSeconds / 60
              delayUnit.value[index] = 'minutes'
            } else {
              delayValue.value[index] = totalSeconds
              delayUnit.value[index] = 'seconds'
            }
          }
        })
      } else {
        form.value = {
          name: '',
          enabled: true,
          priority: 100,
          trigger_mode: 'client_message',
          condition_type: 'always',
          condition_config: {},
          actions: []
        }
        keywordInput.value = ''
        delayValue.value = {}
        delayUnit.value = {}
        webhookPayloadText.value = {}
      }
    }
  },
  { immediate: true }
)

const isValid = computed(() => {
  return form.value.name.trim().length > 0
})

const addAction = () => {
  const index = form.value.actions.length
  form.value.actions.push({
    action_type: 'send_message',
    config: { message: '' },
    on_status: 'always',
    enabled: true,
    order_index: index,
    id: '',
    rule_id: ''
  } as any)
  ensureActionConfig(form.value.actions[index]!, index)
  delayValue.value[index] = 60
  delayUnit.value[index] = 'seconds'
}

const removeAction = (index: number) => {
  form.value.actions.splice(index, 1)
  delete delayValue.value[index]
  delete delayUnit.value[index]
}

const toggleWeekday = (day: number) => {
  if (!form.value.condition_config.weekdays) {
    form.value.condition_config.weekdays = []
  }
  const index = form.value.condition_config.weekdays.indexOf(day)
  if (index === -1) {
    form.value.condition_config.weekdays.push(day)
  } else {
    form.value.condition_config.weekdays.splice(index, 1)
  }
}

const handleSave = () => {
  if (!isValid.value || props.saving) return
  
  // Sync keyword input to config
  if (form.value.condition_type === 'keyword') {
    form.value.condition_config.keywords = keywordInput.value
      .split(',')
      .map(s => s.trim())
      .filter(Boolean)
  }

  // Sync delays
  form.value.actions.forEach((action, index) => {
    if (isDelayedAction(action.action_type)) {
      const val = delayValue.value[index] || 0
      const unit = delayUnit.value[index] || 'seconds'
      let seconds = val
      if (unit === 'minutes') seconds = val * 60
      if (unit === 'hours') seconds = val * 3600
      if (unit === 'days') seconds = val * 86400
      action.config.delay_seconds = seconds
    }
    if (isWebhookAction(action.action_type)) {
      const raw = String(webhookPayloadText.value[index] || '').trim()
      if (!raw) {
        delete action.config.payload
      } else {
        try {
          const parsed = JSON.parse(raw)
          action.config.payload = parsed && typeof parsed === 'object' ? parsed : {}
        } catch {
          action.config.payload = {}
        }
      }
    }
  })

  emit('save', form.value)
}

const isDelayedAction = (actionType: string): boolean => actionType === 'send_delayed'
const isMessageLikeAction = (actionType: string): boolean =>
  actionType === 'send_message' || actionType === 'send_delayed'
const isSetTagAction = (actionType: string): boolean => actionType === 'set_tag'
const isAugmentPromptAction = (actionType: string): boolean => actionType === 'augment_prompt'
const isWebhookAction = (actionType: string): boolean => actionType === 'webhook'
const isSetResultAction = (actionType: string): boolean => actionType === 'set_result'
const isSetVariableAction = (actionType: string): boolean => actionType === 'set_variable'
const isNotifyAdminAction = (actionType: string): boolean => actionType === 'notify_admin'
const isHandoffAction = (actionType: string): boolean => actionType === 'handoff_to_operator'
</script>
