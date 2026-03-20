export const useLayoutState = () => {
  // useState -- SSR-safe, shared across components (Nuxt auto-import)
  const isCollapsed = useState<boolean>('sidebar-collapsed', () => false)

  // Page title for TopBar (set by pages, consumed by default.vue layout)
  const pageTitle = useState<string>('page-title', () => '')

  // Breadcrumb state for TopBar (set by AgentPageShell, consumed by agent.vue layout)
  const breadcrumbTitle = useState<string>('breadcrumb-title', () => '')
  const breadcrumbAgentName = useState<string>('breadcrumb-agent-name', () => '')
  const breadcrumbBackPath = useState<string | null>('breadcrumb-back-path', () => null)

  // Hide Save/Cancel buttons in TopBar (e.g. for auto-saving pages)
  const hideTopBarActions = useState<boolean>('hide-topbar-actions', () => false)

  // Functions page actions and state (for TopBar buttons)
  const functionsRunAction = useState<(() => void) | null>('functions-run-action', () => null)
  const functionsDeleteAction = useState<(() => void) | null>('functions-delete-action', () => null)
  const functionsToggleStatusAction = useState<((isActive: boolean) => void) | null>('functions-toggle-status-action', () => null)
  const functionsSaveAction = useState<(() => void) | null>('functions-save-action', () => null)
  const functionsDuplicateAction = useState<(() => void) | null>('functions-duplicate-action', () => null)
  const functionsCreateAction = useState<(() => void) | null>('functions-create-action', () => null)
  const functionsCreateActionOwner = useState<string | null>('functions-create-action-owner', () => null)
  const functionsSelectedFunction = useState<any | null>('functions-selected-function', () => null)
  const functionsTesting = useState<boolean>('functions-testing', () => false)
  const functionsCanSave = useState<boolean>('functions-can-save', () => false)

  const setFunctionsCreateAction = (owner: string, action: (() => void) | null) => {
    functionsCreateActionOwner.value = owner
    functionsCreateAction.value = action
  }

  const clearFunctionsCreateAction = (owner: string) => {
    if (functionsCreateActionOwner.value !== owner) return
    functionsCreateActionOwner.value = null
    functionsCreateAction.value = null
  }

  const resetFunctionsTopbarState = (options?: { keepCreateAction?: boolean }) => {
    const keepCreateAction = Boolean(options?.keepCreateAction)
    functionsRunAction.value = null
    functionsDeleteAction.value = null
    functionsToggleStatusAction.value = null
    functionsSaveAction.value = null
    functionsDuplicateAction.value = null
    if (!keepCreateAction) {
      functionsCreateActionOwner.value = null
      functionsCreateAction.value = null
    }
    functionsSelectedFunction.value = null
    functionsTesting.value = false
    functionsCanSave.value = false
  }

  const toggleSidebar = () => {
    isCollapsed.value = !isCollapsed.value
    if (import.meta.client) {
      localStorage.setItem('sidebar-collapsed', String(isCollapsed.value))
    }
  }

  // Восстановить состояние из localStorage на клиенте
  const initSidebarState = () => {
    if (import.meta.client) {
      const saved = localStorage.getItem('sidebar-collapsed')
      if (saved !== null) {
        isCollapsed.value = saved === 'true'
      }
    }
  }

  return { 
    isCollapsed, 
    toggleSidebar, 
    initSidebarState, 
    pageTitle, 
    breadcrumbTitle, 
    breadcrumbAgentName,
    breadcrumbBackPath,
    hideTopBarActions,
    functionsRunAction,
    functionsDeleteAction,
    functionsToggleStatusAction,
    functionsSaveAction,
    functionsDuplicateAction,
    functionsCreateAction,
    functionsCreateActionOwner,
    setFunctionsCreateAction,
    clearFunctionsCreateAction,
    functionsSelectedFunction,
    functionsTesting,
    functionsCanSave,
    resetFunctionsTopbarState,
  }
}
