import type { Message, Dialog } from './dialogs'

// WebSocket connection states
export type WsConnectionState = 'connecting' | 'connected' | 'disconnected' | 'error'

// ===========================================
// Outgoing messages (client → server)
// ===========================================

export type WsSendMessagePayload = {
  type: 'send_message'
  dialog_id: string
  content: string
}

export type WsJoinDialogPayload = {
  type: 'join_dialog'
  dialog_id: string
}

export type WsLeaveDialogPayload = {
  type: 'leave_dialog'
  dialog_id: string
}

export type WsGetStatusPayload = {
  type: 'get_status'
}

export type WsPongPayload = {
  type: 'pong'
}

export type WsOutgoingMessage =
  | WsSendMessagePayload
  | WsJoinDialogPayload
  | WsLeaveDialogPayload
  | WsGetStatusPayload
  | WsPongPayload

// ===========================================
// Incoming messages (server → client)
// ===========================================

// message_created - new message in dialog
export type WsMessageCreatedEvent = {
  type: 'message_created'
  data: {
    id: string
    session_id?: string
    dialog_id?: string
    agent_id: string
    role: string
    content: string
    created_at: string
    user_info?: Record<string, unknown>
  }
}

// dialog_updated - dialog list update
export type WsDialogUpdatedEvent = {
  type: 'dialog_updated'
  data: {
    id: string
    agent_id: string
    title: string | null
    last_message_preview: string | null
    last_message_at: string | null
    is_new?: boolean
  }
}

// run_start - agent started processing
export type WsRunStartEvent = {
  type: 'run_start'
  data: {
    run_id: string
    trace_id: string
    dialog_id: string
  }
}

// run_result - agent completed with response
export type WsRunResultEvent = {
  type: 'run_result'
  data: {
    run_id: string
    output: string
    dialog_id: string
    tokens?: {
      input: number
      output: number
    }
    tools_called?: string[]
  }
}

// run_error - agent execution error
export type WsRunErrorEvent = {
  type: 'run_error'
  data: {
    run_id: string
    error: string
    dialog_id: string
  }
}

// ping - keep-alive from server
export type WsPingEvent = {
  type: 'ping'
  data: {
    timestamp: number
  }
}

// error - request processing error
export type WsErrorEvent = {
  type: 'error'
  data: {
    message: string
  }
}

// status - connection status response
export type WsStatusEvent = {
  type: 'status'
  data: {
    connected: boolean
    agent_id: string
    connections_count: number
  }
}

// dialog_joined - subscription confirmation
export type WsDialogJoinedEvent = {
  type: 'dialog_joined'
  data: {
    dialog_id: string
  }
}

// dialog_left - unsubscription confirmation
export type WsDialogLeftEvent = {
  type: 'dialog_left'
  data: {
    dialog_id: string
  }
}

export type WsIncomingMessage =
  | WsMessageCreatedEvent
  | WsDialogUpdatedEvent
  | WsRunStartEvent
  | WsRunResultEvent
  | WsRunErrorEvent
  | WsPingEvent
  | WsErrorEvent
  | WsStatusEvent
  | WsDialogJoinedEvent
  | WsDialogLeftEvent

// ===========================================
// Helper types for composable
// ===========================================

export type WsEventHandler<T extends WsIncomingMessage['type']> = (
  data: Extract<WsIncomingMessage, { type: T }>['data']
) => void

export type WsEventHandlers = {
  onMessageCreated?: WsEventHandler<'message_created'>
  onDialogUpdated?: WsEventHandler<'dialog_updated'>
  onRunStart?: WsEventHandler<'run_start'>
  onRunResult?: WsEventHandler<'run_result'>
  onRunError?: WsEventHandler<'run_error'>
  onError?: WsEventHandler<'error'>
  onStatusChange?: (state: WsConnectionState) => void
}

// Reconnection config
export type WsReconnectConfig = {
  maxAttempts: number
  baseDelay: number
  maxDelay: number
}
