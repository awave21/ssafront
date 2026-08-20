import {
  Ban,
  Bell,
  CircleSlash,
  CornerDownLeft,
  MessageSquare,
  Pause,
  Play,
  ShieldCheck,
  Sparkles,
  Tag,
  Timer,
  UserCheck,
  Webhook,
} from 'lucide-vue-next'
import type { Component } from 'vue'
import type { FunctionRuleActionType } from '~/types/ruleAction'

/**
 * Иконки действий для карточек выбора. Держим отдельно от types/ruleAction.ts,
 * чтобы файл типов не тянул за собой рантайм-зависимость на lucide.
 */
export const functionRuleActionIcons: Record<FunctionRuleActionType, Component> = {
  send_message: MessageSquare,
  send_delayed: Timer,
  notify_admin: Bell,
  handoff_to_operator: UserCheck,
  set_tag: Tag,
  webhook: Webhook,
  augment_prompt: Sparkles,
  set_result: CornerDownLeft,
  pause_dialog: Pause,
  resume_dialog: Play,
  block_user: Ban,
  unblock_user: ShieldCheck,
  noop: CircleSlash,
}
