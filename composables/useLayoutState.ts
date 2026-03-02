export const useLayoutState = () => {
  // useState -- SSR-safe, shared across components (Nuxt auto-import)
  const isCollapsed = useState<boolean>('sidebar-collapsed', () => false)

  // Page title for TopBar (set by pages, consumed by default.vue layout)
  const pageTitle = useState<string>('page-title', () => '')

  // Breadcrumb state for TopBar (set by AgentPageShell, consumed by agent.vue layout)
  const breadcrumbTitle = useState<string>('breadcrumb-title', () => '')
  const breadcrumbAgentName = useState<string>('breadcrumb-agent-name', () => '')

  // Hide Save/Cancel buttons in TopBar (e.g. for auto-saving pages)
  const hideTopBarActions = useState<boolean>('hide-topbar-actions', () => false)

  // Functions page actions and state (for TopBar buttons)
  const functionsRunAction = useState<(() => void) | null>('functions-run-action', () => null)
  const functionsDeleteAction = useState<(() => void) | null>('functions-delete-action', () => null)
  const functionsToggleStatusAction = useState<((isActive: boolean) => void) | null>('functions-toggle-status-action', () => null)
  const functionsSaveAction = useState<(() => void) | null>('functions-save-action', () => null)
  const functionsDuplicateAction = useState<(() => void) | null>('functions-duplicate-action', () => null)
  const functionsSelectedFunction = useState<any | null>('functions-selected-function', () => null)
  const functionsTesting = useState<boolean>('functions-testing', () => false)
  const functionsCanSave = useState<boolean>('functions-can-save', () => false)

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
    hideTopBarActions,
    functionsRunAction,
    functionsDeleteAction,
    functionsToggleStatusAction,
    functionsSaveAction,
    functionsDuplicateAction,
    functionsSelectedFunction,
    functionsTesting,
    functionsCanSave
  }
}
