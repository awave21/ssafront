import {
  SCRIPT_FLOW_EXAMPLE_BIOREVITALIZATION,
  SCRIPT_FLOW_EXAMPLE_BIOREVITALIZATION_ENTRY_NODE_ID,
  SCRIPT_FLOW_EXAMPLE_BIOREVITALIZATION_TITLE,
} from '~/constants/scriptFlowExampleBiorevitalization'

export type ScriptFlowTemplateItem = {
  id: string
  title: string
  description: string
  definition: Record<string, unknown>
  entryNodeId: string
}

/** Готовые схемы для подстановки на канвас (список в боковой панели редактора). */
export const SCRIPT_FLOW_TEMPLATE_LIST: ScriptFlowTemplateItem[] = [
  {
    id: 'biorevitalization',
    title: SCRIPT_FLOW_EXAMPLE_BIOREVITALIZATION_TITLE,
    description:
      'Готовая карта разговора: от первого вопроса о биоревитализации до записи, консультации или мягкого follow-up. При загрузке в библиотеку добавляются типовые мотивы и связываются с ключевыми шагами.',
    definition: SCRIPT_FLOW_EXAMPLE_BIOREVITALIZATION,
    entryNodeId: SCRIPT_FLOW_EXAMPLE_BIOREVITALIZATION_ENTRY_NODE_ID,
  },
]
