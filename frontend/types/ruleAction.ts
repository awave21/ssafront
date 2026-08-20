export const functionRuleActionTypes = {
  setTag: 'set_tag',
  sendMessage: 'send_message',
  sendDelayed: 'send_delayed',
  webhook: 'webhook',
  pauseDialog: 'pause_dialog',
  resumeDialog: 'resume_dialog',
  blockUser: 'block_user',
  unblockUser: 'unblock_user',
  augmentPrompt: 'augment_prompt',
  setResult: 'set_result',
  notifyAdmin: 'notify_admin',
  handoffToOperator: 'handoff_to_operator',
  setVariable: 'set_variable',
  tableFind: 'table_find',
  tableWrite: 'table_write',
  noop: 'noop',
} as const

export type FunctionRuleActionType = (typeof functionRuleActionTypes)[keyof typeof functionRuleActionTypes]

export const functionRuleActionStatuses = {
  success: 'success',
  error: 'error',
  always: 'always',
} as const

export type FunctionRuleActionStatus = (typeof functionRuleActionStatuses)[keyof typeof functionRuleActionStatuses]

/**
 * Человекочитаемые названия действий — единый источник для формы функции и
 * редактора сценария. Раньше у каждого экрана был свой словарь, и оба разошлись
 * с бэкендом: в одном лежали несуществующие типы (crm_note, transfer_dialog),
 * в другом не хватало половины реальных. Тип `Record<FunctionRuleActionType, …>`
 * не даст добавить действие в бэкенд и забыть подпись — TS сломает сборку.
 */
export const functionRuleActionLabels: Record<FunctionRuleActionType, string> = {
  send_message: 'Отправить сообщение',
  send_delayed: 'Отложенное сообщение',
  notify_admin: 'Отправить уведомление админу',
  handoff_to_operator: 'Передать оператору',
  set_variable: 'Управление переменными',
  table_find: 'Поиск в таблице',
  table_write: 'Запись в таблицу',
  set_tag: 'Пометить диалог тегом',
  webhook: 'Отправить вебхук',
  augment_prompt: 'Дополнить промпт',
  // Пишет forced_result, который короткозамыкает LLM и уходит клиенту как есть —
  // работает и в функции, и в сценарии, поэтому подпись нейтральная.
  set_result: 'Задать готовый ответ (без LLM)',
  pause_dialog: 'Пауза диалога',
  resume_dialog: 'Возобновить диалог',
  block_user: 'Заблокировать пользователя',
  unblock_user: 'Разблокировать пользователя',
  noop: 'Ничего не делать',
}

/**
 * Короткие пояснения под названием действия в карточках выбора.
 * Одна строка, без точки в конце — верстка рассчитана на 1–2 строки.
 */
export const functionRuleActionDescriptions: Record<FunctionRuleActionType, string> = {
  send_message: 'Отправляет клиенту заданный текст',
  send_delayed: 'Отправит сообщение через заданное время',
  notify_admin: 'Сообщение администратору в Telegram',
  handoff_to_operator: 'Ставит диалог на паузу и передаёт человеку',
  set_variable: 'Запоминает значение на весь диалог',
  table_find: 'Находит строку и кладёт её в переменные',
  table_write: 'Добавляет строку или обновляет существующую',
  set_tag: 'Помечает диалог тегом для фильтров и аналитики',
  webhook: 'HTTP-запрос на ваш URL с данными функции',
  augment_prompt: 'Добавляет инструкцию в промпт перед ответом',
  set_result: 'Отвечает готовым текстом, не вызывая модель',
  pause_dialog: 'Агент перестаёт отвечать в этом диалоге',
  resume_dialog: 'Снимает диалог с паузы',
  block_user: 'Полностью отключает агента для пользователя',
  unblock_user: 'Снимает блокировку с пользователя',
  noop: 'Ничего не делает — только отметка в логе',
}

export const functionRuleActionStatusLabels: Record<FunctionRuleActionStatus, string> = {
  always: 'Всегда',
  success: 'При успехе',
  error: 'При ошибке',
}

export type BackendFunctionRuleActionType = FunctionRuleActionType
export type BackendFunctionRuleActionStatus = FunctionRuleActionStatus

export type BackendFunctionRuleAction = {
  id: string
  tenant_id: string
  rule_id: string
  action_type: BackendFunctionRuleActionType
  action_config: Record<string, any>
  on_status: BackendFunctionRuleActionStatus
  order_index: number
  enabled: boolean
  created_at?: string
  updated_at?: string | null
}

export type BackendFunctionRuleActionPayload = {
  action_type: BackendFunctionRuleActionType
  action_config: Record<string, any>
  on_status: BackendFunctionRuleActionStatus
  order_index: number
  enabled: boolean
}

export type FunctionRuleAction = {
  id: string
  rule_id: string
  action_type: FunctionRuleActionType
  on_status: FunctionRuleActionStatus
  enabled: boolean
  order_index: number
  config: Record<string, any>
  created_at?: string
  updated_at?: string
}

export type FunctionRuleActionPayload = Omit<
  FunctionRuleAction,
  'id' | 'rule_id' | 'created_at' | 'updated_at'
>

const normalizeActionConfigFromBackend = (
  actionType: BackendFunctionRuleActionType,
  config: Record<string, any> | null | undefined,
): Record<string, any> => {
  const source = { ...(config || {}) }

  if (actionType === 'augment_prompt' && source.instruction && !source.prompt) {
    source.prompt = source.instruction
  }

  if (actionType === 'set_result' && source.result != null && source.value == null) {
    source.value = source.result
  }

  return source
}

const normalizeActionConfigToBackend = (
  actionType: FunctionRuleActionType,
  config: Record<string, any> | null | undefined,
): Record<string, any> => {
  const source = { ...(config || {}) }

  if (actionType === 'augment_prompt') {
    const instruction = String(source.instruction ?? source.prompt ?? '').trim()
    return {
      ...source,
      instruction,
    }
  }

  if (actionType === 'set_result') {
    const result = source.result ?? source.value ?? ''
    return {
      ...source,
      result,
    }
  }

  return source
}

export const mapRuleActionFromBackend = (action: BackendFunctionRuleAction): FunctionRuleAction => ({
  id: action.id,
  rule_id: action.rule_id,
  action_type: action.action_type,
  on_status: action.on_status,
  enabled: action.enabled,
  order_index: action.order_index,
  config: normalizeActionConfigFromBackend(action.action_type, action.action_config),
  created_at: action.created_at,
  updated_at: action.updated_at || undefined,
})

export const mapRuleActionPayloadToBackend = (
  payload: FunctionRuleActionPayload,
): BackendFunctionRuleActionPayload => ({
  action_type: payload.action_type,
  action_config: normalizeActionConfigToBackend(payload.action_type, payload.config),
  on_status: payload.on_status,
  enabled: payload.enabled,
  order_index: payload.order_index,
})
