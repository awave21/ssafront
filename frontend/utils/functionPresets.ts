import type { FunctionRule } from '~/types/functionRule'
import type { FunctionRuleAction } from '~/types/ruleAction'

type PresetParameter = {
  name: string
  type: 'string' | 'number' | 'boolean'
  description: string
  required?: boolean
}

type PresetAction = Pick<FunctionRuleAction, 'action_type'> & {
  config?: Record<string, any>
}

export type FunctionPreset = {
  id: string
  emoji: string
  title: string
  description: string
  /** Что подставится в форму. Всё остаётся редактируемым. */
  name: string
  functionDescription: string
  parameters?: PresetParameter[]
  reaction_mode?: FunctionRule['reaction_mode']
  reaction_message?: string
  reaction_instruction?: string
  post_scenario?: FunctionRule['post_scenario']
  post_scenario_prompt?: string
  actions?: PresetAction[]
}

/**
 * Каталог готовых функций.
 *
 * Здесь только то, что раннер действительно умеет: заготовка, которая
 * подставляет неработающее действие, хуже её отсутствия — пользователь настроит
 * функцию и будет ждать от неё поведения, которого нет. Поэтому ни генерации
 * изображений, ни Google Sheets, ни оценки диалога тут нет.
 *
 * Таблицу в табличных заготовках намеренно не выбираем: у каждого агента она
 * своя, подставить чужой table_id нельзя. Пользователь выберет её в форме.
 */
export const functionPresets: FunctionPreset[] = [
  {
    id: 'client_to_table',
    emoji: '📋',
    title: 'Записать клиента в таблицу',
    description: 'Собирает имя и телефон и добавляет строку в вашу таблицу',
    name: 'save_client',
    functionDescription:
      'Вызывай, когда клиент оставляет свои контакты для записи или обратной связи. Собери имя и телефон.',
    parameters: [
      { name: 'client_name', type: 'string', description: 'Имя клиента', required: true },
      { name: 'client_phone', type: 'string', description: 'Телефон клиента', required: true },
    ],
    actions: [{ action_type: 'table_write', config: { mode: 'insert', values: {} } }],
  },
  {
    id: 'find_client',
    emoji: '🔍',
    title: 'Узнать клиента по телефону',
    description: 'Находит строку в таблице и подставляет её данные в ответ агента',
    name: 'lookup_client',
    functionDescription:
      'Вызывай, когда нужно узнать, есть ли клиент в базе, и вспомнить, что о нём известно.',
    parameters: [
      { name: 'client_phone', type: 'string', description: 'Телефон для поиска', required: true },
    ],
    actions: [
      { action_type: 'table_find', config: { store_prefix: 'client', value: '{{client_phone}}' } },
      {
        action_type: 'augment_prompt',
        config: {
          instruction:
            'Если клиент найден ({{client_found}}), обращайся к нему по имени {{client_name}} и учитывай историю обращений.',
        },
      },
    ],
  },
  {
    id: 'remember_value',
    emoji: '🧠',
    title: 'Значение в память агента',
    description: 'Сохраняет значение в переменную диалога, чтобы использовать дальше',
    name: 'remember_value',
    functionDescription:
      'Вызывай, когда клиент сообщает данные, которые пригодятся дальше по разговору: город, услугу, удобное время.',
    parameters: [
      { name: 'value', type: 'string', description: 'Что запомнить', required: true },
    ],
    actions: [
      { action_type: 'set_variable', config: { name: 'client_note', operation: 'set', value: '{{value}}' } },
    ],
  },
  {
    id: 'reminder',
    emoji: '⏰',
    title: 'Установить напоминание',
    description: 'Отправит клиенту сообщение через заданное время',
    name: 'set_reminder',
    functionDescription: 'Вызывай, когда клиент просит напомнить о записи или перезвонить позже.',
    actions: [
      {
        action_type: 'send_delayed',
        config: { message: 'Напоминаем о вашей записи. Если планы изменились — напишите нам.', delay_seconds: 3600 },
      },
    ],
  },
  {
    id: 'handoff',
    emoji: '🙋',
    title: 'Передать оператору',
    description: 'Ставит диалог на паузу и зовёт администратора',
    name: 'call_operator',
    functionDescription:
      'Вызывай, когда клиент просит живого человека или вопрос выходит за рамки твоих знаний.',
    reaction_mode: 'silent',
    post_scenario: 'pause',
    actions: [
      {
        action_type: 'handoff_to_operator',
        config: {
          client_message: 'Передаю вас администратору, он ответит в ближайшее время.',
          reason: 'клиент попросил оператора',
          notify_admin: true,
        },
      },
    ],
  },
  {
    id: 'notify_admin',
    emoji: '🔔',
    title: 'Уведомить администратора',
    description: 'Отправляет сообщение в Telegram, диалог продолжается',
    name: 'notify_admin',
    functionDescription: 'Вызывай, когда о запросе клиента нужно сразу сообщить администратору.',
    actions: [
      {
        action_type: 'notify_admin',
        config: { message: 'Клиенту нужна помощь администратора', include_context: true },
      },
    ],
  },
  {
    id: 'external_api',
    emoji: '🔌',
    title: 'Вызов внешнего API',
    description: 'Отправляет собранные данные на ваш URL и возвращает ответ агенту',
    name: 'call_external_api',
    functionDescription: 'Вызывай, когда для ответа нужны данные из внешней системы.',
    parameters: [
      { name: 'query', type: 'string', description: 'Что запросить во внешней системе', required: true },
    ],
    actions: [{ action_type: 'webhook', config: { action_kind: 'webhook_api_call', payload: {} } }],
  },
  {
    id: 'custom',
    emoji: '🧩',
    title: 'Кастомная функция',
    description: 'Пустая заготовка — настроите всё сами',
    name: '',
    functionDescription: '',
  },
]

export const findFunctionPreset = (id: string | null | undefined): FunctionPreset | null =>
  functionPresets.find((preset) => preset.id === id) || null

/** Собирает tool_args_schema в том виде, в каком его читает форма функции. */
export const buildPresetArgsSchema = (parameters: PresetParameter[] | undefined) => ({
  type: 'object',
  properties: Object.fromEntries(
    (parameters || []).map((p) => [p.name, { type: p.type, description: p.description }]),
  ),
  required: (parameters || []).filter((p) => p.required).map((p) => p.name),
})
