import { useEffect, useRef } from 'react'
import { MessageBubble, ROLE_COLORS } from './MessageBubble'
import type { DevteamAgent, DevteamChat, DevteamMessage, StreamingMessage } from '@/types/devteam'

interface Props {
  messages:        DevteamMessage[]
  streaming:       StreamingMessage | null
  agents:          DevteamAgent[]
  loading:         boolean
  sending:         boolean
  waitingForAgent: boolean
  chat:            DevteamChat
  onReply:         (msg: DevteamMessage) => void
}

export function MessageFeed({ messages, streaming, agents, loading, sending, waitingForAgent, chat, onReply }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length, streaming?.content, streaming?.toolCalls.length, sending, waitingForAgent])

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="flex items-center gap-2 font-mono text-[11px] text-muted tracking-widest">
          <span className="text-acid animate-pulse">◆</span>
          ЗАГРУЗКА
        </div>
      </div>
    )
  }

  if (messages.length === 0 && !streaming && !sending && !waitingForAgent) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-3 select-none">
        <div
          className="w-10 h-10 rounded-sm flex items-center justify-center text-xl"
          style={{ background: '#0e0e18', border: '1px solid #1a1a28' }}
        >
          ◈
        </div>
        <p className="font-mono text-[11px] text-muted tracking-widest">НАЧНИТЕ ДИАЛОГ</p>
      </div>
    )
  }

  // Determine which agent is "thinking"
  const thinkingAgent = (() => {
    if (streaming) return agents.find((a) => a.role === streaming.role) ?? null
    if (sending || waitingForAgent) {
      if (chat.kind === 'dm') return agents.find((a) => a.role === chat.agents[0]) ?? null
      return agents.find((a) => a.role === 'orchestrator') ?? null
    }
    return null
  })()

  const showThinking = (
    sending ||
    waitingForAgent ||
    (streaming != null && !streaming.content && streaming.toolCalls.length === 0)
  )

  return (
    <div className="flex-1 overflow-y-auto px-5 py-5 space-y-5">
      {messages.map((msg) => (
        <MessageBubble key={msg.id} message={msg} agents={agents} onReply={onReply} />
      ))}

      {/* Streaming with content or tool calls */}
      {streaming && (streaming.content || streaming.toolCalls.length > 0) && (
        <MessageBubble
          message={{
            author:     streaming.role,
            content:    streaming.content,
            tool_calls: streaming.toolCalls as any,
            isStreaming: true,
          } as any}
          agents={agents}
        />
      )}

      {/* Thinking indicator — shown while sending or waiting for first chunk */}
      {showThinking && thinkingAgent && (
        <ThinkingBubble agent={thinkingAgent} />
      )}

      <div ref={bottomRef} />
    </div>
  )
}

function ThinkingBubble({ agent }: { agent: DevteamAgent }) {
  const color = ROLE_COLORS[agent.role] ?? '#6b7280'

  return (
    <div className="msg-enter">
      {/* Author line */}
      <div className="flex items-center gap-2 mb-1.5 pl-4">
        <span className="text-base leading-none select-none">{agent.emoji}</span>
        <span
          className="font-display font-bold text-[11px] tracking-[0.18em]"
          style={{ color }}
        >
          {agent.name.toUpperCase()}
        </span>
        <span className="text-[10px] text-muted tracking-wider">— думает</span>
      </div>

      {/* Thinking card */}
      <div
        className="ml-3 mr-6 px-4 py-3 rounded-sm flex items-center gap-3"
        style={{
          background: '#0d0d17',
          borderLeft: `2px solid ${color}30`,
        }}
      >
        {/* Animated dots */}
        <div className="flex items-center gap-1.5">
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="block rounded-full"
              style={{
                width: 6,
                height: 6,
                background: color,
                animation: `pulseDot 1.4s ease-in-out ${i * 0.22}s infinite`,
              }}
            />
          ))}
        </div>

        {/* Scanning line */}
        <div
          className="flex-1 h-px rounded-full overflow-hidden"
          style={{ background: `${color}15` }}
        >
          <div
            className="h-full rounded-full"
            style={{
              width: '40%',
              background: `linear-gradient(90deg, transparent, ${color}60, transparent)`,
              animation: 'scan 1.8s ease-in-out infinite',
            }}
          />
        </div>

        <span
          className="font-mono text-[10px] tracking-widest"
          style={{ color: `${color}80` }}
        >
          PROCESSING
        </span>
      </div>

      <style>{`
        @keyframes scan {
          0%   { transform: translateX(-100%); }
          100% { transform: translateX(350%); }
        }
      `}</style>
    </div>
  )
}
