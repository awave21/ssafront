import type { ScriptFlow, ScriptFlowToolUsageNode } from '~/types/scriptFlow'
import type { CoverageRiskSummary } from '~/utils/scriptFlowCoverageRisk'

/** Данные для компактной полосы редактора потока в DashboardTopBar (layouts/agent.vue). */
export type ScriptFlowToolbarPayload = {
  flow: ScriptFlow
  publishing: boolean
  retrying: boolean
  riskSummary: CoverageRiskSummary | null
  toolUsage: {
    approximate_flow_tool_calls?: number
    days?: number
    disclaimer?: string | null
    daily_series?: Array<{ date: string; count: number }>
    top_node_refs?: ScriptFlowToolUsageNode[]
    by_node_id?: Record<string, ScriptFlowToolUsageNode>
  } | null
  onPublish: () => void
  onUnpublish: () => void
  onReadiness: () => void
  onDraftPreview: () => void
  onRetryIndex: () => void
}

/** Вкладки базы знаний (совпадает с AgentKnowledgePanel) */
export type KnowledgeBreadcrumbTab =
  | 'sqns'
  | 'directories'
  | 'direct_questions'
  | 'file_uploads'
  | 'tables'
  | 'dashboard'

export type BreadcrumbNavAction =
  | { type: 'route'; path: string }
  | { type: 'knowledge-dashboard' }
  | { type: 'knowledge-tab'; tab: KnowledgeBreadcrumbTab }

export type LayoutBreadcrumbSegment = {
  label: string
  /** null — текущая страница (не кликабельно) */
  action: BreadcrumbNavAction | null
}

export const useLayoutState = () => {
  // useState -- SSR-safe, shared across components (Nuxt auto-import)
  const isCollapsed = useState<boolean>('sidebar-collapsed', () => false)

  // Page title for TopBar (set by pages, consumed by default.vue layout)
  const pageTitle = useState<string>('page-title', () => '')

  // Breadcrumb state for TopBar (set by AgentPageShell, consumed by agent.vue layout)
  const breadcrumbTitle = useState<string>('breadcrumb-title', () => '')
  const breadcrumbAgentName = useState<string>('breadcrumb-agent-name', () => '')
  const breadcrumbBackPath = useState<string | null>('breadcrumb-back-path', () => null)

  /** Многоуровневые крошки (база знаний и др.); если задано — имеет приоритет над breadcrumbTitle */
  const layoutBreadcrumbSegments = useState<LayoutBreadcrumbSegment[] | null>(
    'layout-breadcrumb-segments',
    () => null
  )
  /** Внутренняя навигация по клику крошки (обрабатывает AgentKnowledgePanel) */
  const pendingBreadcrumbAction = useState<BreadcrumbNavAction | null>(
    'pending-breadcrumb-action',
    () => null
  )

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

  const isEditorFullscreen = useState<boolean>('editor-fullscreen', () => false)

  // Script-flow page actions (canvas editor → TopBar header buttons)
  const scriptFlowActionsVisible = useState<boolean>('script-flow-actions-visible', () => false)
  const scriptFlowSandboxOpen = useState<boolean>('script-flow-sandbox-open', () => false)
  const scriptFlowCoverageOpen = useState<boolean>('script-flow-coverage-open', () => false)

  /** Редактор сценария: компактная полоса статуса и действий в шапке агента */
  const scriptFlowToolbarPayload = useState<ScriptFlowToolbarPayload | null>(
    'script-flow-toolbar-payload',
    () => null,
  )

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
    layoutBreadcrumbSegments,
    pendingBreadcrumbAction,
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
    isEditorFullscreen,
    scriptFlowActionsVisible,
    scriptFlowSandboxOpen,
    scriptFlowCoverageOpen,
    scriptFlowToolbarPayload,
  }
}
