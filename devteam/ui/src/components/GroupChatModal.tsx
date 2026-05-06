import { useState } from 'react'
import { X } from 'lucide-react'
import { ROLE_COLORS } from './MessageBubble'
import type { DevteamAgent } from '@/types/devteam'

interface Props {
  agents:   DevteamAgent[]
  onClose:  () => void
  onCreate: (roles: string[], title?: string) => void
}

export function GroupChatModal({ agents, onClose, onCreate }: Props) {
  const [selected, setSelected] = useState<string[]>(['orchestrator'])
  const [title, setTitle] = useState('')

  const toggle = (role: string) => {
    setSelected((prev) =>
      prev.includes(role) ? prev.filter((r) => r !== role) : [...prev, role],
    )
  }

  const submit = () => {
    if (selected.length === 0) return
    onCreate(selected, title || undefined)
    onClose()
  }

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-fade-in">
      <div
        className="w-full max-w-sm rounded-sm shadow-2xl"
        style={{ background: '#0a0a12', border: '1px solid #1a1a28' }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-5 py-4"
          style={{ borderBottom: '1px solid #131320' }}
        >
          <div>
            <p className="font-display font-bold text-[12px] tracking-[0.2em] text-white">
              НОВЫЙ КАНАЛ
            </p>
            <p className="font-mono text-[10px] text-muted mt-0.5 tracking-wider">
              групповой чат с агентами
            </p>
          </div>
          <button
            onClick={onClose}
            className="w-6 h-6 flex items-center justify-center text-muted hover:text-white transition-colors rounded-sm hover:bg-surface-3"
          >
            <X size={14} />
          </button>
        </div>

        <div className="px-5 py-4 space-y-4">
          {/* Title input */}
          <div>
            <label className="section-label block mb-1.5">Название (необязательно)</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="general, sprint-42, ..."
              className="w-full text-[13px] text-white placeholder-muted outline-none px-3 py-2 rounded-sm font-mono"
              style={{ background: '#0d0d18', border: '1px solid #1a1a28' }}
              onFocus={(e) => (e.currentTarget.style.borderColor = '#c8f75240')}
              onBlur={(e) => (e.currentTarget.style.borderColor = '#1a1a28')}
            />
          </div>

          {/* Agent list */}
          <div>
            <label className="section-label block mb-2">Участники</label>
            <div className="space-y-0.5">
              {agents.map((agent) => {
                const isOn = selected.includes(agent.role)
                const color = ROLE_COLORS[agent.role] ?? '#6b7280'

                return (
                  <label
                    key={agent.role}
                    className="flex items-center gap-3 px-3 py-2 rounded-sm cursor-pointer transition-colors hover:bg-surface-2"
                  >
                    {/* Custom checkbox */}
                    <div
                      className="flex-shrink-0 w-4 h-4 rounded-sm flex items-center justify-center transition-all"
                      style={{
                        background: isOn ? color : 'transparent',
                        border: `1px solid ${isOn ? color : '#2a2a3e'}`,
                      }}
                      onClick={() => toggle(agent.role)}
                    >
                      {isOn && (
                        <svg width="9" height="7" viewBox="0 0 9 7" fill="none">
                          <path d="M1 3.5L3.5 6L8 1" stroke="#050508" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                      )}
                    </div>

                    <span className="text-base">{agent.emoji}</span>
                    <div className="flex-1 min-w-0">
                      <p
                        className="text-[13px] font-medium leading-tight transition-colors"
                        style={{ color: isOn ? color : '#9898b2' }}
                      >
                        {agent.name}
                      </p>
                      <p className="text-[11px] text-muted leading-tight">{agent.title}</p>
                    </div>
                  </label>
                )
              })}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div
          className="flex justify-end gap-2 px-5 py-4"
          style={{ borderTop: '1px solid #131320' }}
        >
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-[13px] text-muted hover:text-white transition-colors font-mono tracking-wider"
          >
            ОТМЕНА
          </button>
          <button
            onClick={submit}
            disabled={selected.length === 0}
            className="px-4 py-1.5 text-[13px] font-bold tracking-wider rounded-sm transition-all font-mono"
            style={{
              background: selected.length > 0 ? '#c8f752' : '#1a1a28',
              color: selected.length > 0 ? '#050508' : '#3a3a52',
              cursor: selected.length > 0 ? 'pointer' : 'default',
            }}
          >
            СОЗДАТЬ
          </button>
        </div>
      </div>
    </div>
  )
}
