import {
  functionRuleActionDescriptions,
  functionRuleActionLabels,
  type FunctionRuleActionType,
} from '~/types/ruleAction'
import { functionPresets } from '~/utils/functionPresets'
import { scenarioPresets } from '~/utils/scenarioPresets'

export type AssistantCatalogItem = {
  value: string
  label: string
  description: string
}

/**
 * Каталог возможностей уходит на бэкенд вместе с вопросом.
 *
 * Так помощник знает ровно то, что у пользователя есть на экране: второй копии
 * списка действий на бэкенде нет, значит и разъезжаться нечему. Бэкенд всё
 * равно пересекает присланное со своим enum — совет про действие, которого
 * раннер не знает, до модели не дойдёт.
 *
 * Карточки-заглушки «Скоро» (`ruleActionSoon.ts`) сюда не попадают: их нет в
 * словаре подписей, а рекомендовать неработающее хуже, чем промолчать.
 */
export const buildActionCatalog = (): AssistantCatalogItem[] =>
  (Object.keys(functionRuleActionLabels) as FunctionRuleActionType[]).map((type) => ({
    value: type,
    label: functionRuleActionLabels[type],
    description: functionRuleActionDescriptions[type],
  }))

/** Заготовки функций: их id — это значение `?preset=` в ссылке на конструктор. */
export const buildFunctionPresetCatalog = (): AssistantCatalogItem[] =>
  functionPresets.map((preset) => ({
    value: preset.id,
    label: preset.title,
    description: preset.description,
  }))

/** Заготовки сценариев — тот же контракт, другая страница. */
export const buildScenarioPresetCatalog = (): AssistantCatalogItem[] =>
  scenarioPresets.map((preset) => ({
    value: preset.id,
    label: preset.title,
    description: preset.description,
  }))
