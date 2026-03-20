/**
 * Composable: function variables management
 * Handles: CRUD for variables, copy token, insert at cursor, build variable map
 */
import { ref, nextTick, type Ref } from 'vue'
import type { Tool } from '~/types/tool'

export type FunctionVariable = { name: string; value: string; description: string }

export const useVariables = (
  selectedFunction: Ref<Tool | null>,
  markAsChanged: () => void,
  showStatus: (type: 'success' | 'error', text: string) => void,
  generateInputSchema: () => void,
) => {
  const variables = ref<FunctionVariable[]>([])
  const urlInputRef = ref<HTMLInputElement | null>(null)

  const addVariable = () => {
    variables.value.push({ name: '', value: '', description: '' })
    markAsChanged()
  }

  const removeVariable = (index: number) => {
    variables.value.splice(index, 1)
    generateInputSchema()
    markAsChanged()
  }

  const onVariableInput = () => {
    variables.value.forEach(v => {
      v.name = v.name.replace(/[^a-zA-Z0-9_]/g, '').toLowerCase()
    })
    generateInputSchema()
    markAsChanged()
  }

  const copyVariableToken = async (name: string) => {
    const token = `{{${name}}}`
    try {
      await navigator.clipboard.writeText(token)
      showStatus('success', `Скопировано: ${token}`)
    } catch {
      showStatus('error', 'Не удалось скопировать')
    }
  }

  const insertVariableAtCursor = (target: string, _index: number, varName: string) => {
    const token = `{{${varName}}}`
    if (target === 'url' && selectedFunction.value) {
      const el = urlInputRef.value
      if (el) {
        const start = el.selectionStart ?? selectedFunction.value.endpoint.length
        const end = el.selectionEnd ?? start
        const current = selectedFunction.value.endpoint
        selectedFunction.value.endpoint = current.slice(0, start) + token + current.slice(end)
        markAsChanged()
        nextTick(() => {
          const newPos = start + token.length
          el.focus()
          el.setSelectionRange(newPos, newPos)
        })
      } else {
        selectedFunction.value.endpoint += token
        markAsChanged()
      }
    }
  }

  const buildVariableMap = (): Record<string, string> => {
    const map: Record<string, string> = {}
    variables.value.forEach((v) => {
      const key = v.name.trim()
      if (!key) return
      map[key] = v.value ?? ''
    })
    return map
  }

  return {
    variables,
    urlInputRef,
    addVariable,
    removeVariable,
    onVariableInput,
    copyVariableToken,
    insertVariableAtCursor,
    buildVariableMap,
  }
}
