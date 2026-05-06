export interface DevteamAgent {
  role: string
  name: string
  emoji: string
  title: string
  expertise: string
  character: string
}

export interface DevteamChat {
  id: number
  kind: 'dm' | 'group'
  title: string | null
  agents: string[]
  session_id: string | null
  created_at: string
  updated_at: string
}

export interface DevteamToolCall {
  name: string
  input: Record<string, unknown>
  output: string | null
}

export interface DevteamMessage {
  id: number
  chat_id: number
  author: string  // 'user' | role
  content: string
  tool_calls: DevteamToolCall[]
  task_id: number | null
  created_at: string
}

export interface DevteamTask {
  id: number
  chat_id: number
  description: string
  priority: string
  agent_roles: string[]
  status: 'pending' | 'in_progress' | 'done' | 'failed'
  created_at: string
  updated_at: string
}

// ─── WebSocket Events ─────────────────────────────────────────────────────────

export interface WsMessageCreated {
  type: 'message_created'
  message: DevteamMessage
}

export interface WsAgentTyping {
  type: 'agent_typing'
  role: string
}

export interface WsAgentChunk {
  type: 'agent_chunk'
  role: string
  delta: string
}

export interface WsToolCall {
  type: 'tool_call'
  role: string
  tool: string
  input: Record<string, unknown>
}

export interface WsToolResult {
  type: 'tool_result'
  role: string
  tool: string | null
  output: string
}

export interface WsTaskStatus {
  type: 'task_status'
  task: DevteamTask
}

export interface WsError {
  type: 'error'
  message: string
}

export interface WsPong {
  type: 'pong'
}

export type DevteamWsEvent =
  | WsMessageCreated
  | WsAgentTyping
  | WsAgentChunk
  | WsToolCall
  | WsToolResult
  | WsTaskStatus
  | WsError
  | WsPong

// Сообщение в процессе стриминга (накапливается перед message_created)
export interface DevteamStreamingMessage {
  role: string
  content: string
  toolCalls: DevteamToolCall[]
  isStreaming: boolean
}
