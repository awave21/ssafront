import { ref, readonly } from 'vue'

const STORAGE_KEY = 'agent-enabled-states'
const isBrowser = typeof window !== 'undefined'

/**
 * Read enabled states from localStorage
 */
const readStoredStates = (): Record<string, boolean> => {
  if (!isBrowser) return {}
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    return stored ? (JSON.parse(stored) as Record<string, boolean>) : {}
  } catch (error) {
    console.error('Failed to parse stored agent enabled states:', error)
    return {}
  }
}

/**
 * Write enabled states to localStorage
 */
const writeStoredStates = (states: Record<string, boolean>) => {
  if (!isBrowser) return
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(states))
  } catch (error) {
    console.error('Failed to persist agent enabled states:', error)
  }
}

// Shared reactive state
const enabledStates = ref<Record<string, boolean>>(isBrowser ? readStoredStates() : {})

export const useAgentEnabled = () => {
  /**
   * Check if agent is enabled (defaults to true if not set)
   */
  const isAgentEnabled = (agentId: string): boolean => {
    return enabledStates.value[agentId] ?? true
  }

  /**
   * Set agent enabled/disabled state
   */
  const setAgentEnabled = (agentId: string, enabled: boolean) => {
    enabledStates.value = {
      ...enabledStates.value,
      [agentId]: enabled
    }
    writeStoredStates(enabledStates.value)
  }

  /**
   * Toggle agent enabled state
   */
  const toggleAgentEnabled = (agentId: string): boolean => {
    const currentState = isAgentEnabled(agentId)
    const newState = !currentState
    setAgentEnabled(agentId, newState)
    return newState
  }

  /**
   * Remove agent from enabled states (cleanup)
   */
  const removeAgentState = (agentId: string) => {
    if (enabledStates.value[agentId] !== undefined) {
      const { [agentId]: _, ...rest } = enabledStates.value
      enabledStates.value = rest
      writeStoredStates(enabledStates.value)
    }
  }

  return {
    enabledStates: readonly(enabledStates),
    isAgentEnabled,
    setAgentEnabled,
    toggleAgentEnabled,
    removeAgentState
  }
}
