import { ArrowLeftRight, Building2, Contact, CreditCard } from 'lucide-vue-next'
import type { ActionPickerItem } from '~/components/agents/function-rules/ActionTypePicker.vue'

/**
 * Действия из роадмапа, которых пока нет в бэкенде.
 *
 * Карточки заблокированы, поэтому их `value` наверх никогда не уходит и в
 * function_post_action_type эти значения добавлять не нужно: сохранить
 * неработающее действие невозможно by design.
 *
 * Показываем их сознательно — иначе пользователь ищет интеграцию с CRM,
 * не находит и решает, что её не будет.
 */
export const soonActionItems: ActionPickerItem[] = [
  {
    value: 'soon_bitrix24',
    label: 'Отправка в Битрикс24',
    description: 'Создаёт или обновляет лиды, сделки и контакты',
    icon: Building2,
    disabled: true,
    badge: 'Скоро',
  },
  {
    value: 'soon_amocrm',
    label: 'Отправка в amoCRM',
    description: 'Создаёт или обновляет сущности в amoCRM',
    icon: Contact,
    disabled: true,
    badge: 'Скоро',
  },
  {
    value: 'soon_switch_agent',
    label: 'Переключить агента',
    description: 'Передаёт диалог другому агенту',
    icon: ArrowLeftRight,
    disabled: true,
    badge: 'Скоро',
  },
  {
    value: 'soon_payment_link',
    label: 'Отправить ссылку на оплату',
    description: 'Формирует ссылку и отправляет её клиенту',
    icon: CreditCard,
    disabled: true,
    badge: 'Скоро',
  },
]
