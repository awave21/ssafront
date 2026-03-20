// Dialog statuses for indicators
export type DialogStatus = 'NEW' | 'IN_PROGRESS' | 'UNREAD' | 'ERROR' | 'NORMAL'

// Per-dialog agent toggle status (active = agent responds, paused = agent silent)
export type DialogAgentStatus = 'active' | 'paused'

// User info from external platforms
export type DialogUserInfo = {
  platform?: string                 // 'telegram', 'whatsapp', 'web', etc.
  platform_id?: string
  session_id?: string
  username?: string
  first_name?: string
  last_name?: string
}

// Dialog entity
export type Dialog = {
  id: string
  agent_id: string
  title: string | null              // null = auto-label from first message
  last_message_preview: string | null
  last_message_at: string | null
  unread_count: number
  is_pinned: boolean
  is_archived: boolean
  status: DialogStatus
  created_at: string
  updated_at?: string
  // Platform info
  platform?: string                 // 'telegram', 'whatsapp', 'web'
  user_info?: DialogUserInfo
  // Per-dialog agent status
  agent_status?: DialogAgentStatus  // 'active' (default) or 'paused'
}

// Message types
export type MessageRole = 'user' | 'agent' | 'manager'
export type MessageType = 'text' | 'image' | 'voice'
export type MessageStatus = 'sending' | 'sent' | 'failed' | 'streaming' | 'done'

// Message entity
export type Message = {
  id: string
  dialog_id: string
  role: MessageRole
  type: MessageType
  content: string                   // text content or URL for images/voice
  status: MessageStatus
  duration_seconds?: number         // for voice messages
  created_at: string
  error_message?: string            // for failed messages
}

// API request/response types
export type CreateDialogData = {
  title?: string
}

export type UpdateDialogData = {
  title?: string
  is_pinned?: boolean
  is_archived?: boolean
}

export type SendMessageData = {
  content: string
  type: MessageType
}

export type SendManagerMessageData = {
  content: string
}

export type DialogsListResponse = {
  dialogs: Dialog[]
  total: number
  has_more: boolean
}

export type MessagesListResponse = {
  messages: Message[]
  has_more: boolean
  next_cursor?: string
}

// SSE streaming event types
export type StreamEventType = 'start' | 'delta' | 'done' | 'error'

export type StreamEvent = {
  type: StreamEventType
  data: {
    message_id?: string
    content?: string
    error?: string
  }
}
