import type { ScenarioConditionType, ScenarioTriggerMode } from '~/types/scenario'

type PresetAction = {
  action_type: string
  config?: Record<string, any>
}

export type ScenarioPreset = {
  id: string
  emoji: string
  title: string
  description: string
  /** Что подставится в форму сценария. Всё остаётся редактируемым. */
  name: string
  trigger_mode: ScenarioTriggerMode
  condition_type: ScenarioConditionType
  condition_config?: Record<string, any>
  actions?: PresetAction[]
}

/**
 * Каталог готовых сценариев.
 *
 * Как и в каталоге функций, здесь только рабочие связки триггер + условие +
 * действие: заготовка, которая подставляет неподдержанное действие, приводит
 * к сценарию, который молча не срабатывает.
 *
 * Тексты сообщений намеренно обобщённые — клиника подставит свои.
 */
export const scenarioPresets: ScenarioPreset[] = [
  {
    id: 'greeting',
    emoji: '👋',
    title: 'Приветствие нового диалога',
    description: 'Отправляет первое сообщение, когда клиент только написал',
    name: 'Приветствие нового диалога',
    trigger_mode: 'dialog_start',
    condition_type: 'always',
    actions: [
      {
        action_type: 'send_message',
        config: { message: 'Здравствуйте! Подскажите, чем можем помочь?' },
      },
    ],
  },
  {
    id: 'night_autoreply',
    emoji: '🌙',
    title: 'Ночной автоответ',
    description: 'Предупреждает о нерабочем времени с 22:00 до 09:00',
    name: 'Ночной автоответ (22:00–09:00)',
    trigger_mode: 'client_message',
    condition_type: 'schedule_time',
    condition_config: { start_time: '22:00', end_time: '09:00' },
    actions: [
      {
        action_type: 'send_message',
        config: {
          message: 'Спасибо за обращение! Мы работаем с 09:00 — администратор ответит утром.',
        },
      },
    ],
  },
  {
    id: 'client_return',
    emoji: '🔄',
    title: 'Возврат клиента',
    description: 'Реагирует, когда клиент вернулся после долгого перерыва',
    name: 'Возврат клиента спустя 30+ дней',
    trigger_mode: 'client_return',
    condition_type: 'client_return_gap',
    condition_config: { min_days: 30 },
    actions: [
      {
        action_type: 'send_message',
        config: { message: 'Рады снова вас видеть! Подсказать что-то по услугам?' },
      },
    ],
  },
  {
    id: 'ask_operator',
    emoji: '🙋',
    title: 'Просьба позвать оператора',
    description: 'Передаёт диалог человеку, когда клиент просит живого сотрудника',
    name: 'Запрос оператора',
    trigger_mode: 'client_message',
    condition_type: 'keyword',
    condition_config: { keywords: ['оператор', 'человек', 'менеджер', 'администратор'] },
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
    id: 'complaint',
    emoji: '🚨',
    title: 'Жалоба клиента',
    description: 'Помечает диалог тегом и сразу уведомляет администратора',
    name: 'Жалоба клиента',
    trigger_mode: 'client_message',
    condition_type: 'keyword',
    condition_config: { keywords: ['жалоба', 'верните деньги', 'ужасно', 'отвратительно'] },
    actions: [
      { action_type: 'set_tag', config: { tag: 'complaint' } },
      {
        action_type: 'notify_admin',
        config: { message: 'Жалоба от клиента — нужна реакция', include_context: true },
      },
    ],
  },
  {
    id: 'price_interest',
    emoji: '💰',
    title: 'Интерес к цене',
    description: 'Помечает диалог тегом, когда клиент спрашивает стоимость',
    name: 'Интерес к цене',
    trigger_mode: 'client_message',
    condition_type: 'keyword',
    condition_config: { keywords: ['цена', 'стоимость', 'сколько стоит', 'прайс'] },
    actions: [{ action_type: 'set_tag', config: { tag: 'price_interest' } }],
  },
  {
    id: 'manager_pause',
    emoji: '⏸️',
    title: 'Пауза при ответе менеджера',
    description: 'Останавливает агента, как только в диалог написал сотрудник',
    name: 'Пауза при ответе менеджера',
    trigger_mode: 'manager_message',
    condition_type: 'always',
    actions: [{ action_type: 'pause_dialog' }],
  },
  {
    id: 'blank',
    emoji: '🧩',
    title: 'Пустой сценарий',
    description: 'Настроите триггер, условие и действия сами',
    name: '',
    trigger_mode: 'client_message',
    condition_type: 'always',
  },
]

export const findScenarioPreset = (id: string | null | undefined): ScenarioPreset | null =>
  scenarioPresets.find((preset) => preset.id === id) || null
