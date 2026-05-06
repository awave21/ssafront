import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { CornerUpLeft } from 'lucide-react'
import { ToolCallBlock } from './ToolCallBlock'
import { extractTouchedFiles } from '@/utils/touchedFiles'
import type { DevteamAgent, DevteamMessage, DevteamReplyTo, StreamingMessage } from '@/types/devteam'

export const ROLE_COLORS: Record<string, string> = {
  orchestrator: '#c084fc',
  backend:      '#60a5fa',
  frontend:     '#f472b6',
  devops:       '#fb923c',
  ai_engineer:  '#22d3ee',
  analyst:      '#4ade80',
  user:         '#c8f752',
}

interface Props {
  message: DevteamMessage | (Partial<DevteamMessage> & {
    author: string
    content: string
    isStreaming?: boolean
    toolCalls?: StreamingMessage['toolCalls']
  })
  agents: DevteamAgent[]
  onReply?: (msg: DevteamMessage) => void
}

export function MessageBubble({ message, agents, onReply }: Props) {
  const [hovered, setHovered] = useState(false)
  const isUser      = message.author === 'user'
  const agent       = agents.find((a) => a.role === message.author)
  const isStreaming  = (message as any).isStreaming
  const roleColor   = ROLE_COLORS[message.author] ?? '#6b7280'
  const emoji       = isUser ? '◈' : (agent?.emoji ?? '◈')
  const name        = isUser ? 'ВЫ' : (agent?.name?.toUpperCase() ?? message.author.toUpperCase())
  const toolCalls   = (message.tool_calls ?? (message as any).toolCalls ?? []) as any[]
  const replyTo     = (message as DevteamMessage).reply_to ?? null

  const canReply = onReply && !isStreaming && (message as DevteamMessage).id != null

  if (isUser) {
    return (
      <div
        className="flex justify-end msg-enter"
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
      >
        {/* Reply button (left of bubble) */}
        {canReply && hovered && (
          <button
            onClick={() => onReply(message as DevteamMessage)}
            className="self-center mr-2 p-1 rounded-sm text-muted hover:text-white transition-colors"
            style={{ background: '#111122' }}
            title="Ответить"
          >
            <CornerUpLeft size={12} />
          </button>
        )}

        <div className="max-w-[72%]">
          {/* Reply preview */}
          {replyTo && <ReplyQuote replyTo={replyTo} agents={agents} />}

          {/* Label */}
          <div className="flex justify-end items-center gap-1.5 mb-1 pr-1">
            <span
              className="font-mono text-[10px] font-medium tracking-[0.15em]"
              style={{ color: roleColor }}
            >
              {name}
            </span>
            <span className="text-[10px] text-muted">{emoji}</span>
          </div>

          {/* Bubble */}
          <div
            className="px-4 py-2.5 rounded-sm text-[13.5px] leading-relaxed"
            style={{
              background: '#0a120a',
              borderRight: `2px solid ${roleColor}`,
              color: '#d8e8d8',
            }}
          >
            <p className="whitespace-pre-wrap break-words">{message.content}</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div
      className="msg-enter"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Author line */}
      <div className="flex items-center gap-2 mb-1.5 pl-4">
        <span className="text-base leading-none select-none">{emoji}</span>
        <span
          className="font-display font-bold text-[11px] tracking-[0.18em]"
          style={{ color: roleColor }}
        >
          {name}
        </span>
        {agent && (
          <span className="text-[10px] text-muted tracking-wider">
            — {agent.title}
          </span>
        )}
        {/* Reply button */}
        {canReply && hovered && (
          <button
            onClick={() => onReply(message as DevteamMessage)}
            className="ml-auto mr-2 p-1 rounded-sm text-muted hover:text-white transition-colors flex-shrink-0"
            style={{ background: '#111122' }}
            title="Ответить"
          >
            <CornerUpLeft size={11} />
          </button>
        )}
        {isStreaming && (
          <span className="flex items-center gap-0.5 ml-1">
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className="w-1 h-1 rounded-full animate-pulse-dot"
                style={{
                  background: roleColor,
                  animationDelay: `${i * 0.18}s`,
                }}
              />
            ))}
          </span>
        )}
      </div>

      {/* Reply quote */}
      {replyTo && (
        <div className="ml-3 mr-6 mb-1">
          <ReplyQuote replyTo={replyTo} agents={agents} />
        </div>
      )}

      {/* Content card */}
      <div
        className="ml-3 mr-6 rounded-sm overflow-hidden"
        style={{
          background: '#0d0d17',
          borderLeft: `2px solid ${roleColor}30`,
        }}
      >
        {/* Tool calls */}
        {toolCalls.length > 0 && (
          <div className="px-4 pt-3 space-y-1">
            {toolCalls.map((tc, i) => (
              <ToolCallBlock key={i} toolCall={tc} />
            ))}
          </div>
        )}

        {/* Touched files pill — only when there were file operations */}
        {!isStreaming && toolCalls.length > 0 && (() => {
          const { read, written } = extractTouchedFiles(toolCalls)
          if (read.length === 0 && written.length === 0) return null
          return (
            <div
              className="px-4 py-1.5 flex flex-wrap gap-x-4 gap-y-0.5"
              style={{ borderTop: '1px solid #0e0e1c' }}
            >
              {written.length > 0 && (
                <span className="font-mono text-[10px] tracking-wider" style={{ color: `${roleColor}90` }}>
                  ✏️ <span style={{ color: `${roleColor}60` }}>{written.join(' · ')}</span>
                </span>
              )}
              {read.length > 0 && (
                <span className="font-mono text-[10px] tracking-wider text-muted">
                  👁 <span style={{ color: '#3a3a52' }}>{read.join(' · ')}</span>
                </span>
              )}
            </div>
          )
        })()}

        {/* Text */}
        {message.content && (
          <div className="px-4 py-3 agent-prose prose prose-sm max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  )
}

function ReplyQuote({ replyTo, agents }: { replyTo: DevteamReplyTo; agents: DevteamAgent[] }) {
  const agent = agents.find((a) => a.role === replyTo.author)
  const color = ROLE_COLORS[replyTo.author] ?? '#6b7280'
  const label = replyTo.author === 'user'
    ? 'ВЫ'
    : (agent?.name?.toUpperCase() ?? replyTo.author.toUpperCase())
  const preview = replyTo.content.length > 80
    ? replyTo.content.slice(0, 80) + '…'
    : replyTo.content

  return (
    <div
      className="flex items-center gap-2 px-3 py-1.5 rounded-sm text-[11px] font-mono overflow-hidden"
      style={{ background: `${color}0d`, borderLeft: `2px solid ${color}50` }}
    >
      <span style={{ color: `${color}90` }} className="flex-shrink-0">{agent?.emoji ?? '◈'}</span>
      <span style={{ color: `${color}90` }} className="flex-shrink-0 font-bold tracking-wider">{label}</span>
      <span className="text-muted truncate">{preview}</span>
    </div>
  )
}
