import { ref } from 'vue'
import type { Dialog, DialogAgentStatus, CreateDialogData, UpdateDialogData, DialogsListResponse } from '../types/dialogs'
import { useApiFetch } from './useApiFetch'
import { getReadableErrorMessage } from '~/utils/api-errors'
import {
  normalizeDialogUserInfo,
  resolveDialogPlatform,
  resolveDialogUserTitle
} from '~/utils/dialogIdentity'

const AGENT_STATUSES = new Set<string>(['active', 'paused', 'disabled'])

type UserAgentStateResponse = {
  agent_id: string
  platform: string
  platform_user_id: string
  is_disabled: boolean
  disabled_at: string | null
  disabled_by_user_id: string | null
}

const coerceIsDisabled = (value: unknown): boolean => {
  if (typeof value === 'boolean') return value
  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase()
    if (normalized === 'true' || normalized === '1') return true
    if (normalized === 'false' || normalized === '0' || normalized === '') return false
  }
  if (typeof value === 'number') return value === 1
  return Boolean(value)
}

/**
 * Normalize a raw dialog from the API:
 * backend returns agent toggle as `status: "active"|"paused"`,
 * but frontend uses `status` for UI indicators (IN_PROGRESS, etc.)
 * so we move it to `agent_status` and reset `status` to 'NORMAL'.
 */
const normalizeDialog = (raw: any): Dialog => {
  const hasIsDisabled = raw?.is_disabled !== undefined && raw?.is_disabled !== null
  const backendSt = typeof raw?.status === 'string' ? raw.status.trim().toLowerCase() : ''

  const agentStatus: DialogAgentStatus = hasIsDisabled
    ? (coerceIsDisabled(raw.is_disabled) ? 'paused' : 'active')
    : backendSt === 'disabled' || backendSt === 'paused'
      ? 'paused'
      : backendSt === 'active'
        ? 'active'
        : raw.agent_status === 'paused' || raw.agent_status === 'active'
          ? raw.agent_status
          : 'active'

  return {
    ...raw,
    agent_status: agentStatus,
    // Backend dialog list uses status = active|paused|disabled; UI indicator — отдельное поле
    status: AGENT_STATUSES.has(backendSt) ? 'NORMAL' : (raw.status || 'NORMAL')
  }
}

// Shared state across components - using ref for deep reactivity
const dialogs = ref<Dialog[]>([])
const isLoading = ref(false)
const error = ref<string | null>(null)
const currentAgentId = ref<string | null>(null)

export const useDialogs = () => {
  const apiFetch = useApiFetch()

  const extractUserIdFromDialogId = (dialogId: string | undefined): string | null => {
    if (!dialogId || !dialogId.includes(':')) return null
    const [, ...parts] = dialogId.split(':')
    const value = parts.join(':').trim()
    return value || null
  }

  const resolvePlatformAndUserId = (dialog: Dialog): { platform: string; platformUserId: string } | null => {
    const platform = resolveDialogPlatform(dialog)
    const rawPlatformUserId = dialog.user_info?.platform_id || extractUserIdFromDialogId(dialog.id) || null

    if (platform && rawPlatformUserId) {
      return { platform, platformUserId: String(rawPlatformUserId) }
    }

    // Fallback для исторических кейсов, когда platform есть, а platform_id нет.
    const fallbackUserId = extractUserIdFromDialogId(dialog.user_info?.session_id)
    if (platform && fallbackUserId) {
      return { platform, platformUserId: fallbackUserId }
    }

    return null
  }

  /**
   * Fetch dialogs for a specific agent
   */
  const fetchDialogs = async (agentId: string, options?: { archived?: boolean }) => {
    if (!agentId) {
      console.warn('[useDialogs] fetchDialogs called without agentId')
      return
    }

    isLoading.value = true
    error.value = null
    currentAgentId.value = agentId

    try {
      const params = new URLSearchParams()
      if (options?.archived !== undefined) {
        params.set('archived', String(options.archived))
      }

      const queryString = params.toString()
      const url = `agents/${agentId}/dialogs${queryString ? `?${queryString}` : ''}`

      const response = await apiFetch<DialogsListResponse | Dialog[]>(url)
      
      // Handle both response formats: {dialogs: [...]} or direct array [...]
      let dialogsList: Dialog[] = []
      if (Array.isArray(response)) {
        dialogsList = response
      } else if (response && typeof response === 'object' && 'dialogs' in response) {
        dialogsList = response.dialogs || []
      } else if (response && typeof response === 'object' && 'items' in response) {
        // Some APIs use 'items' instead of 'dialogs'
        dialogsList = (response as any).items || []
      }
      
      dialogs.value = dialogsList.map(normalizeDialog)
    } catch (err: any) {
      console.error('[useDialogs] Error fetching dialogs:', err)
      console.error('[useDialogs] Error details:', {
        status: err?.statusCode || err?.status,
        data: err?.data,
        message: err?.message
      })
      error.value = getReadableErrorMessage(err, 'Не удалось загрузить диалоги')
      dialogs.value = []
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Create a new dialog for the current agent
   */
  const createDialog = async (agentId: string, data?: CreateDialogData): Promise<Dialog | null> => {
    if (!agentId) return null

    isLoading.value = true
    error.value = null

    try {
      const response = await apiFetch<Dialog>(`agents/${agentId}/dialogs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: data || {}
      })

      const normalized = normalizeDialog(response)
      // Add to the beginning of the list
      dialogs.value = [normalized, ...dialogs.value]
      return normalized
    } catch (err: any) {
      error.value = getReadableErrorMessage(err, 'Не удалось создать диалог')
      return null
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Update a dialog (rename, pin, archive)
   */
  const updateDialog = async (agentId: string, dialogId: string, data: UpdateDialogData): Promise<Dialog | null> => {
    if (!agentId || !dialogId) return null

    try {
      const response = await apiFetch<Dialog>(`agents/${agentId}/dialogs/${encodeURIComponent(dialogId)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: data
      })

      const normalized = normalizeDialog(response)
      // Update in local state
      const index = dialogs.value.findIndex(d => d.id === dialogId)
      if (index !== -1) {
        dialogs.value[index] = normalized
      }

      return normalized
    } catch (err: any) {
      error.value = getReadableErrorMessage(err, 'Не удалось обновить диалог')
      return null
    }
  }

  /**
   * Delete a dialog
   */
  const deleteDialog = async (agentId: string, dialogId: string): Promise<boolean> => {
    if (!agentId || !dialogId) return false

    try {
      await apiFetch(`agents/${agentId}/dialogs/${encodeURIComponent(dialogId)}`, {
        method: 'DELETE'
      })

      // Remove from local state
      dialogs.value = dialogs.value.filter(d => d.id !== dialogId)
      return true
    } catch (err: any) {
      error.value = getReadableErrorMessage(err, 'Не удалось удалить диалог')
      return false
    }
  }

  /**
   * Toggle per-user agent status (active <-> paused) via API
   * PUT /agents/{agent_id}/users/{platform}/{platform_user_id}/state  { is_disabled: boolean }
   */
  const toggleDialogAgentStatus = async (
    agentId: string,
    dialog: Dialog
  ): Promise<DialogAgentStatus | null> => {
    if (!agentId || !dialog?.id) return null

    const resolved = resolvePlatformAndUserId(dialog)
    if (!resolved) {
      error.value = 'Не удалось определить пользователя диалога'
      return null
    }

    const { platform, platformUserId } = resolved
    const encodedPlatform = encodeURIComponent(platform)
    const encodedUserId = encodeURIComponent(platformUserId)

    const stateUrl = `agents/${agentId}/users/${encodedPlatform}/${encodedUserId}/state`

    const idx = dialogs.value.findIndex(d => d.id === dialog.id)
    const currentStatus: DialogAgentStatus = idx !== -1
      ? (dialogs.value[idx].agent_status ?? 'active')
      : 'active'

    // Optimistic update
    const optimisticStatus: DialogAgentStatus = currentStatus === 'active' ? 'paused' : 'active'
    if (idx !== -1) {
      dialogs.value[idx] = { ...dialogs.value[idx], agent_status: optimisticStatus }
    }

    try {
      const nextIsDisabled = currentStatus === 'active'

      console.info('[Dialog Agent Toggle] PUT state request', {
        method: 'PUT',
        url: stateUrl,
        body: { is_disabled: nextIsDisabled },
        action: nextIsDisabled ? 'disable' : 'enable'
      })
      await apiFetch(stateUrl, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: { is_disabled: nextIsDisabled }
      })
      console.info('[Dialog Agent Toggle] PUT state response', {
        method: 'PUT',
        url: stateUrl,
        success: true,
        is_disabled: nextIsDisabled
      })

      const finalStatus: DialogAgentStatus = nextIsDisabled ? 'paused' : 'active'
      if (idx !== -1) {
        dialogs.value[idx] = { ...dialogs.value[idx], agent_status: finalStatus }
      }
      return finalStatus
    } catch (err: any) {
      // Rollback on failure
      if (idx !== -1) {
        dialogs.value[idx] = { ...dialogs.value[idx], agent_status: currentStatus }
      }
      error.value = getReadableErrorMessage(err, 'Не удалось изменить статус агента')
      console.error('[useDialogs] toggleDialogAgentStatus error:', err)
      return null
    }
  }

  const syncDialogAgentStatus = async (
    agentId: string,
    dialog: Dialog
  ): Promise<DialogAgentStatus | null> => {
    if (!agentId || !dialog?.id) return null

    const resolved = resolvePlatformAndUserId(dialog)
    if (!resolved) return null

    const { platform, platformUserId } = resolved
    const stateUrl = `agents/${agentId}/users/${encodeURIComponent(platform)}/${encodeURIComponent(platformUserId)}/state`

    try {
      console.info('[Dialog Agent Toggle] GET state sync request', {
        method: 'GET',
        url: stateUrl,
        agentId,
        platform,
        platformUserId,
        dialogId: dialog.id
      })
      const currentState = await apiFetch<UserAgentStateResponse>(stateUrl)
      console.info('[Dialog Agent Toggle] GET state sync response', {
        method: 'GET',
        url: stateUrl,
        is_disabled: currentState.is_disabled,
        is_disabled_type: typeof (currentState as any)?.is_disabled,
        disabled_at: currentState.disabled_at,
        disabled_by_user_id: currentState.disabled_by_user_id
      })
      const normalized: DialogAgentStatus = coerceIsDisabled((currentState as any)?.is_disabled) ? 'paused' : 'active'
      const idx = dialogs.value.findIndex(d => d.id === dialog.id)
      if (idx !== -1) {
        dialogs.value[idx] = { ...dialogs.value[idx], agent_status: normalized }
      }
      return normalized
    } catch (err: any) {
      console.error('[useDialogs] syncDialogAgentStatus error:', err)
      return null
    }
  }

  /**
   * Update dialog status locally (for real-time indicators)
   */
  const updateDialogStatus = (dialogId: string, status: Dialog['status']) => {
    const index = dialogs.value.findIndex(d => d.id === dialogId)
    if (index !== -1) {
      dialogs.value[index] = { ...dialogs.value[index], status }
    }
  }

  /**
   * Update last message preview locally
   */
  const updateLastMessage = (dialogId: string, preview: string, timestamp: string) => {
    const index = dialogs.value.findIndex(d => d.id === dialogId)
    if (index !== -1) {
      dialogs.value[index] = {
        ...dialogs.value[index],
        last_message_preview: preview,
        last_message_at: timestamp
      }
      // Move to top of list
      const dialog = dialogs.value.splice(index, 1)[0]
      dialogs.value.unshift(dialog)
    }
  }

  /**
   * Increment unread count locally
   */
  const incrementUnread = (dialogId: string) => {
    const index = dialogs.value.findIndex(d => d.id === dialogId)
    if (index !== -1) {
      dialogs.value[index] = {
        ...dialogs.value[index],
        unread_count: dialogs.value[index].unread_count + 1
      }
    }
  }

  /**
   * Mark dialog as read
   */
  const markAsRead = (dialogId: string) => {
    const index = dialogs.value.findIndex(d => d.id === dialogId)
    if (index !== -1) {
      dialogs.value[index] = {
        ...dialogs.value[index],
        unread_count: 0
      }
    }
  }

  /**
   * Get dialog by ID
   */
  const getDialogById = (dialogId: string): Dialog | undefined => {
    return dialogs.value.find(d => d.id === dialogId)
  }

  /**
   * Clear dialogs state
   */
  const clearDialogs = () => {
    dialogs.value = []
    currentAgentId.value = null
    error.value = null
  }

  /**
   * Update or insert dialog (for real-time updates)
   */
  const upsertDialog = (dialogData: any) => {
    const id = dialogData.id || dialogData.session_id
    if (!id) return

    const index = dialogs.value.findIndex(d => d.id === id)
    const existing = index !== -1 ? dialogs.value[index] : null
    
    const mergedRawUserInfo = dialogData.user_info || existing?.user_info
    const platform = resolveDialogPlatform({
      id,
      platform: dialogData.platform || existing?.platform,
      user_info: mergedRawUserInfo
    })
    const userInfo = normalizeDialogUserInfo(
      {
        id,
        platform,
        user_info: mergedRawUserInfo
      },
      mergedRawUserInfo
    )
    const userTitle = resolveDialogUserTitle({ id, platform, user_info: userInfo })
    const finalTitle = userTitle || existing?.title || 'Диалог'
    
    // Map incoming data to Dialog type, then normalize status fields
    const updatedDialog = normalizeDialog({
      ...(existing || {}),
      id,
      title: finalTitle,
      last_message_preview: dialogData.last_message_preview || dialogData.content || existing?.last_message_preview || '',
      last_message_at: dialogData.last_message_at || dialogData.created_at || existing?.last_message_at || new Date().toISOString(),
      unread_count: dialogData.is_new ? (existing?.unread_count ?? 0) + 1 : (existing?.unread_count ?? 0),
      status: dialogData.status || existing?.status || 'NORMAL',
      agent_status: dialogData.agent_status || existing?.agent_status,
      created_at: dialogData.created_at || existing?.created_at || new Date().toISOString(),
      updated_at: new Date().toISOString(),
      platform,
      user_info: userInfo || existing?.user_info
    })

    if (index !== -1) {
      // Update existing - move to top to trigger reactivity
      dialogs.value = [
        updatedDialog,
        ...dialogs.value.filter((_, i) => i !== index)
      ]
    } else {
      // Add new dialog to beginning
      dialogs.value = [updatedDialog, ...dialogs.value]
    }
  }

  const resolveDialogId = (rawDialogId: unknown): string | null => {
    if (!rawDialogId) return null
    const rawId = String(rawDialogId)
    // dialogs is ref<Dialog[]>
    const exactMatch = dialogs.value.find(dialog => dialog.id === rawId)
    if (exactMatch) return exactMatch.id
    const suffixMatch = dialogs.value.find(dialog => dialog.id.endsWith(`:${rawId}`))
    return suffixMatch?.id ?? rawId
  }

  return {
    // State - returning refs directly for proper reactivity
    dialogs,
    isLoading,
    error,
    currentAgentId,

    // Actions
    fetchDialogs,
    createDialog,
    updateDialog,
    deleteDialog,
    toggleDialogAgentStatus,
    syncDialogAgentStatus,
    upsertDialog,
    updateDialogStatus,
    updateLastMessage,
    incrementUnread,
    markAsRead,
    getDialogById,
    resolveDialogId,
    clearDialogs
  }
}
