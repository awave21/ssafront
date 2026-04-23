/**
 * Управление переменными потока (flow_metadata.variables).
 *
 * Переменные — это плейсхолдеры {{name}} в текстах нод, привязанные к источнику данных:
 *   static   → фиксированный текст
 *   search   → RAG-поиск по справочнику
 *   function → агентская функция (tool), возвращает актуальные данные в рантайме
 *
 * Composable не знает о ScriptFlow — получает только `variables` по ссылке и
 * коллбэк `onUpdate`, чтобы родитель мог сохранить изменения.
 */
import { computed, type Ref } from 'vue'
import { nanoid } from 'nanoid'
import type { VariableBinding } from '~/types/scriptFlow'

export type FlowVariableEntry = {
  name: string
  binding: VariableBinding
}

/** Генерирует уникальное snake_case имя переменной для функции. */
function makeVarName(
  functionName: string,
  existingNames: string[],
): string {
  const base = functionName
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 30) || 'fn_var'

  if (!existingNames.includes(base)) return base
  for (let i = 2; i < 100; i++) {
    const candidate = `${base}_${i}`
    if (!existingNames.includes(candidate)) return candidate
  }
  return `${base}_${nanoid(4)}`
}

export function useFlowVariables(
  variables: Ref<Record<string, VariableBinding> | undefined>,
  onUpdate: (updated: Record<string, VariableBinding>) => void,
) {
  const entries = computed((): FlowVariableEntry[] =>
    Object.entries(variables.value ?? {}).map(([name, binding]) => ({ name, binding })),
  )

  const functionEntries = computed(() =>
    entries.value.filter(e => e.binding.source_type === 'function'),
  )

  /** Добавить переменную для функции и сразу вставить {{name}} в активное поле (insertVar). */
  const addFunctionVariable = (
    opts: {
      functionId: string
      functionName: string
      argumentHint: string
      llmInstruction?: string
    },
    insertVar?: (name: string) => void,
  ): string => {
    const existing = Object.keys(variables.value ?? {})
    const name = makeVarName(opts.functionName, existing)
    const updated: Record<string, VariableBinding> = {
      ...(variables.value ?? {}),
      [name]: {
        source_type: 'function',
        function_id: opts.functionId,
        argument_hint: opts.argumentHint,
        llm_instruction: opts.llmInstruction?.trim() || undefined,
      },
    }
    onUpdate(updated)
    insertVar?.(name)
    return name
  }

  /** Обновить поля существующей function-переменной. */
  const updateFunctionVariable = (
    name: string,
    patch: { argument_hint?: string; llm_instruction?: string; function_id?: string },
  ) => {
    const existing = variables.value ?? {}
    const binding = existing[name]
    if (!binding || binding.source_type !== 'function') return
    onUpdate({
      ...existing,
      [name]: { ...binding, ...patch } as VariableBinding,
    })
  }

  /** Удалить переменную по имени. */
  const removeVariable = (name: string) => {
    const updated = { ...(variables.value ?? {}) }
    delete updated[name]
    onUpdate(updated)
  }

  return {
    entries,
    functionEntries,
    addFunctionVariable,
    updateFunctionVariable,
    removeVariable,
    makeVarName,
  }
}
