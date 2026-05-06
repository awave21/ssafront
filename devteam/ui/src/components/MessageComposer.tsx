import { useState, useRef, useCallback } from 'react'
import { ArrowUp, Loader2, X } from 'lucide-react'
import { ROLE_COLORS } from './MessageBubble'
import type { DevteamAgent, DevteamMessage } from '@/types/devteam'

interface Props {
  onSend:          (text: string) => void
  sending:         boolean
  agents:          DevteamAgent[]
  isGroup?:        boolean
  replyTo?:        DevteamMessage | null
  onCancelReply?:  () => void
}

export function MessageComposer({ onSend, sending, agents, isGroup, replyTo, onCancelReply }: Props) {
  const [text, setText] = useState('')
  const [mentions, setMentions] = useState<DevteamAgent[]>([])
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const focused = useRef(false)

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value
    setText(val)

    if (isGroup) {
      const match = val.match(/@(\w*)$/)
      setMentions(
        match
          ? agents.filter((a) => a.role !== 'orchestrator' && a.role.startsWith(match[1].toLowerCase()))
          : [],
      )
    }

    const ta = textareaRef.current
    if (ta) {
      ta.style.height = 'auto'
      ta.style.height = Math.min(ta.scrollHeight, 160) + 'px'
    }
  }

  const applyMention = (role: string) => {
    setText((p) => p.replace(/@\w*$/, `@${role} `))
    setMentions([])
    textareaRef.current?.focus()
  }

  const submit = useCallback(() => {
    const trimmed = text.trim()
    if (!trimmed || sending) return
    onSend(trimmed)
    setText('')
    setMentions([])
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }, [text, sending, onSend])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  const canSend = text.trim().length > 0 && !sending

  return (
    <div className="flex-shrink-0 px-5 pb-5 pt-2">
      {/* Reply banner */}
      {replyTo && (
        <div
          className="mb-1.5 flex items-center gap-2 px-3 py-1.5 rounded-sm"
          style={{ background: '#0d0d18', border: '1px solid #1a1a28' }}
        >
          <span
            className="font-mono text-[10px] tracking-widest flex-shrink-0"
            style={{ color: ROLE_COLORS[replyTo.author] ?? '#6b7280' }}
          >
            ↩ {replyTo.author === 'user' ? 'ВЫ' : (agents.find((a) => a.role === replyTo.author)?.name?.toUpperCase() ?? replyTo.author.toUpperCase())}
          </span>
          <span className="text-[11px] text-muted truncate flex-1">
            {replyTo.content.slice(0, 80)}
          </span>
          <button
            onClick={onCancelReply}
            className="flex-shrink-0 text-muted hover:text-white transition-colors"
          >
            <X size={11} />
          </button>
        </div>
      )}

      {/* @mention autocomplete */}
      {mentions.length > 0 && (
        <div
          className="mb-2 rounded-sm overflow-hidden"
          style={{ background: '#0d0d18', border: '1px solid #1a1a28' }}
        >
          {mentions.map((a) => (
            <button
              key={a.role}
              onClick={() => applyMention(a.role)}
              className="flex items-center gap-2.5 w-full px-3 py-2 text-left hover:bg-surface-3 transition-colors"
            >
              <span className="text-base">{a.emoji}</span>
              <span className="text-[13px] text-white font-medium">{a.name}</span>
              <span className="text-[11px] font-mono text-muted">@{a.role}</span>
            </button>
          ))}
        </div>
      )}

      {/* Input row */}
      <div
        className="flex items-end gap-3 px-4 py-3 rounded-sm transition-all duration-150"
        style={{
          background: '#0d0d18',
          border: `1px solid ${focused.current ? '#c8f75240' : '#1a1a28'}`,
          outline: 'none',
        }}
        onFocus={() => { focused.current = true }}
        onBlur={() => { focused.current = false }}
      >
        <textarea
          ref={textareaRef}
          value={text}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onFocus={(e) => {
            focused.current = true
            ;(e.currentTarget.closest('div') as HTMLDivElement).style.borderColor = '#c8f75240'
          }}
          onBlur={(e) => {
            focused.current = false
            ;(e.currentTarget.closest('div') as HTMLDivElement).style.borderColor = '#1a1a28'
          }}
          placeholder={
            isGroup
              ? 'Сообщение…  (@role — обратиться напрямую)'
              : 'Сообщение…  (Enter — отправить, Shift+Enter — новая строка)'
          }
          rows={1}
          className="flex-1 bg-transparent resize-none text-[13.5px] text-[#d0d0e8] placeholder-muted outline-none leading-relaxed font-sans"
          style={{ minHeight: '22px' }}
        />

        <button
          onClick={submit}
          disabled={!canSend}
          className="flex-shrink-0 w-7 h-7 flex items-center justify-center rounded-sm transition-all duration-150"
          style={{
            background: canSend ? '#c8f752' : '#1a1a28',
            cursor: canSend ? 'pointer' : 'default',
          }}
        >
          {sending ? (
            <Loader2 size={13} className="animate-spin" style={{ color: '#050508' }} />
          ) : (
            <ArrowUp size={13} style={{ color: canSend ? '#050508' : '#3a3a52', strokeWidth: 2.5 }} />
          )}
        </button>
      </div>

      <p className="mt-1.5 px-1 font-mono text-[10px] text-muted tracking-wider">
        CTRL+ENTER — новая строка
      </p>
    </div>
  )
}
