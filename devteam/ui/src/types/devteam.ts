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

export interface DevteamReplyTo {
  id: number
  author: string
  content: string
}

export interface DevteamMessage {
  id: number
  chat_id: number
  author: string
  content: string
  tool_calls: DevteamToolCall[]
  task_id: number | null
  reply_to_id: number | null
  reply_to: DevteamReplyTo | null
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

// WebSocket events
export type WsEvent =
  | { type: 'message_created'; message: DevteamMessage }
  | { type: 'agent_typing'; role: string }
  | { type: 'agent_chunk'; role: string; delta: string }
  | { type: 'tool_call'; role: string; tool: string; input: Record<string, unknown> }
  | { type: 'tool_result'; role: string; tool: string | null; output: string }
  | { type: 'task_status'; task: DevteamTask }
  | { type: 'error'; message: string }
  | { type: 'pong' }

export interface StreamingMessage {
  role: string
  content: string
  toolCalls: { name: string; input: Record<string, unknown>; output: string | null }[]
}
