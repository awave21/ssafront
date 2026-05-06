import { useState, useCallback } from 'react'
import { Settings2, X, Plus, Check } from 'lucide-react'
import { MessageFeed } from './MessageFeed'
import { MessageComposer } from './MessageComposer'
import { useDevteamWebSocket } from '@/hooks/useDevteamWebSocket'
import { ROLE_COLORS } from './MessageBubble'
import type { DevteamAgent, DevteamChat, DevteamMessage, StreamingMessage, WsEvent } from '@/types/devteam'

interface Props {
  chat:             DevteamChat
  agents:           DevteamAgent[]
  messages:         DevteamMessage[]
  streaming:        StreamingMessage | null
  loading:          boolean
  sending:          boolean
  waitingForAgent:  boolean
  onSend:           (text: string, replyToId?: number) => void
  onWsEvent:        (event: WsEvent) => void
  onUpdateAgents?:  (chatId: number, agents: string[]) => Promise<any>
}

export function ChatArea({ chat, agents, messages, streaming, loading, sending, waitingForAgent, onSend, onWsEvent, onUpdateAgents }: Props) {
  useDevteamWebSocket(chat.id, onWsEvent)
  const [showMembers, setShowMembers] = useState(false)
  const [replyTo, setReplyTo] = useState<DevteamMessage | null>(null)

  const handleSend = useCallback((text: string) => {
    onSend(text, replyTo?.id)
    setReplyTo(null)
  }, [onSend, replyTo])

  return (
    <div className="flex flex-col flex-1 h-full min-w-0">
      {/* Header */}
      <div
        className="flex-shrink-0 px-5 py-3 flex items-center justify-between"
        style={{ borderBottom: '1px solid #131320', background: '#08080d' }}
      >
        <ChatHeader chat={chat} agents={agents} />

        {/* Members button — только для групп */}
        {chat.kind === 'group' && onUpdateAgents && (
          <button
            onClick={() => setShowMembers(true)}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-sm font-mono text-[10px] text-muted hover:text-white hover:bg-surface-3 transition-all tracking-wider"
          >
            <Settings2 size={11} />
            УЧАСТНИКИ
          </button>
        )}
      </div>

      {/* Members panel */}
      {showMembers && chat.kind === 'group' && onUpdateAgents && (
        <MembersPanel
          chat={chat}
          agents={agents}
          onClose={() => setShowMembers(false)}
          onSave={async (roles) => {
            await onUpdateAgents(chat.id, roles)
            setShowMembers(false)
          }}
        />
      )}

      {/* Messages */}
      <MessageFeed
        messages={messages}
        streaming={streaming}
        agents={agents}
        loading={loading}
        sending={sending}
        waitingForAgent={waitingForAgent}
        chat={chat}
        onReply={setReplyTo}
      />

      {/* Composer */}
      <MessageComposer
        onSend={handleSend}
        sending={sending}
        agents={agents}
        isGroup={chat.kind === 'group'}
        replyTo={replyTo}
        onCancelReply={() => setReplyTo(null)}
      />
    </div>
  )
}

/* ── Chat header ─────────────────────────────────────────────────── */

function ChatHeader({ chat, agents }: { chat: DevteamChat; agents: DevteamAgent[] }) {
  if (chat.kind === 'dm') {
    const agent = agents.find((a) => a.role === chat.agents[0])
    if (!agent) return null
    const color = ROLE_COLORS[agent.role] ?? '#6b7280'
    return (
      <div className="flex items-center gap-4">
        <div
          className="w-8 h-8 rounded-sm flex items-center justify-center text-lg flex-shrink-0"
          style={{ background: `${color}14`, border: `1px solid ${color}25` }}
        >
          {agent.emoji}
        </div>
        <div>
          <div className="flex items-center gap-2">
            <p className="font-display font-bold text-[13px] tracking-[0.14em]" style={{ color }}>
              {agent.name.toUpperCase()}
            </p>
            <span className="font-mono text-[10px] text-muted tracking-widest">DM</span>
          </div>
          <p className="text-[11px] text-muted mt-0.5">{agent.expertise}</p>
        </div>
      </div>
    )
  }

  const members = chat.agents.map((r) => agents.find((a) => a.role === r)).filter(Boolean) as DevteamAgent[]
  return (
    <div className="flex items-center gap-3">
      <div className="flex -space-x-2 flex-shrink-0">
        {members.slice(0, 6).map((a) => {
          const color = ROLE_COLORS[a.role] ?? '#6b7280'
          return (
            <div
              key={a.role}
              className="w-7 h-7 rounded-sm flex items-center justify-center text-sm"
              style={{ background: `${color}14`, border: `1px solid ${color}25` }}
              title={a.name}
            >
              {a.emoji}
            </div>
          )
        })}
      </div>
      <div>
        <p className="font-display font-bold text-[13px] tracking-[0.14em] text-white">
          {(chat.title ?? 'ГРУППА').toUpperCase()}
        </p>
        <p className="text-[11px] text-muted mt-0.5">
          {members.map((a) => a.name).join(' · ')}
        </p>
      </div>
    </div>
  )
}

/* ── Members panel ───────────────────────────────────────────────── */

function MembersPanel({
  chat,
  agents,
  onClose,
  onSave,
}: {
  chat: DevteamChat
  agents: DevteamAgent[]
  onClose: () => void
  onSave: (roles: string[]) => Promise<void>
}) {
  const [selected, setSelected] = useState<string[]>(chat.agents)
  const [saving, setSaving] = useState(false)

  const toggle = (role: string) => {
    setSelected((prev) =>
      prev.includes(role) ? prev.filter((r) => r !== role) : [...prev, role],
    )
  }

  const handleSave = async () => {
    if (selected.length === 0) return
    setSaving(true)
    try { await onSave(selected) } finally { setSaving(false) }
  }

  const changed = JSON.stringify([...selected].sort()) !== JSON.stringify([...chat.agents].sort())

  return (
    <div
      className="flex-shrink-0 border-b animate-fade-in"
      style={{ background: '#08080e', borderColor: '#131320' }}
    >
      {/* Panel header */}
      <div className="flex items-center justify-between px-5 py-2.5" style={{ borderBottom: '1px solid #131320' }}>
        <span className="font-mono text-[10px] text-muted tracking-widest">УПРАВЛЕНИЕ УЧАСТНИКАМИ</span>
        <button onClick={onClose} className="text-muted hover:text-white transition-colors">
          <X size={13} />
        </button>
      </div>

      {/* Agent list — horizontal */}
      <div className="flex flex-wrap gap-2 px-5 py-3">
        {agents.map((agent) => {
          const isOn = selected.includes(agent.role)
          const color = ROLE_COLORS[agent.role] ?? '#6b7280'

          return (
            <button
              key={agent.role}
              onClick={() => toggle(agent.role)}
              className="flex items-center gap-2 px-3 py-1.5 rounded-sm text-[12px] transition-all duration-100"
              style={{
                background: isOn ? `${color}14` : '#0e0e18',
                border: `1px solid ${isOn ? `${color}40` : '#1a1a28'}`,
                color: isOn ? color : '#5a5a72',
              }}
            >
              <span className="text-sm leading-none">{agent.emoji}</span>
              <span className="font-medium">{agent.name}</span>
              {isOn ? (
                <Check size={11} style={{ color }} />
              ) : (
                <Plus size={11} className="opacity-50" />
              )}
            </button>
          )
        })}
      </div>

      {/* Save */}
      <div className="flex items-center justify-between px-5 py-2.5" style={{ borderTop: '1px solid #0e0e18' }}>
        <p className="font-mono text-[10px] text-muted">
          {selected.length} из {agents.length} участников
        </p>
        <div className="flex gap-2">
          <button
            onClick={onClose}
            className="px-3 py-1 font-mono text-[10px] text-muted hover:text-white tracking-wider transition-colors"
          >
            ОТМЕНА
          </button>
          <button
            onClick={handleSave}
            disabled={!changed || saving || selected.length === 0}
            className="flex items-center gap-1.5 px-3 py-1 font-mono text-[10px] font-bold tracking-wider rounded-sm transition-all"
            style={{
              background: changed && selected.length > 0 ? '#c8f752' : '#1a1a28',
              color: changed && selected.length > 0 ? '#050508' : '#3a3a52',
              cursor: changed && selected.length > 0 ? 'pointer' : 'default',
            }}
          >
            {saving ? '...' : 'СОХРАНИТЬ'}
          </button>
        </div>
      </div>
    </div>
  )
}
