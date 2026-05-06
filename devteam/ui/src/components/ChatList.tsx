import { Plus, Hash, Trash2, ChevronLeft, ChevronRight } from 'lucide-react'
import { AgentCard } from './AgentCard'
import { ROLE_COLORS } from './MessageBubble'
import type { DevteamAgent, DevteamChat } from '@/types/devteam'

interface Props {
  agents:        DevteamAgent[]
  chats:         DevteamChat[]
  activeChatId:  number | null
  collapsed:     boolean
  onToggle:      () => void
  onOpenDm:      (role: string) => void
  onOpenChat:    (chatId: number) => void
  onCreateGroup: () => void
  onDeleteChat:  (chatId: number) => void
}

function chatLabel(chat: DevteamChat, agents: DevteamAgent[]): string {
  if (chat.title) return chat.title
  if (chat.kind === 'dm') {
    const a = agents.find((a) => a.role === chat.agents[0])
    return a ? a.name : chat.agents[0]
  }
  return chat.agents.map((r) => agents.find((a) => a.role === r)?.name ?? r).join(', ')
}

export function ChatList({ agents, chats, activeChatId, collapsed, onToggle, onOpenDm, onOpenChat, onCreateGroup, onDeleteChat }: Props) {
  const groupChats = chats.filter((c) => c.kind === 'group')

  return (
    <aside
      className="relative flex-shrink-0 flex flex-col h-full grain"
      style={{
        width: collapsed ? 52 : 256,
        background: '#09090f',
        borderRight: '1px solid #181826',
        transition: 'width 0.22s cubic-bezier(0.4, 0, 0.2, 1)',
        overflow: 'hidden',
      }}
    >
      {/* ── Brand header ── */}
      <div
        className="flex-shrink-0 flex items-center justify-between px-3 py-3"
        style={{ borderBottom: '1px solid #181826', minHeight: 52 }}
      >
        {!collapsed && (
          <div className="overflow-hidden">
            <span className="font-display font-bold text-[15px] tracking-[0.22em] text-white whitespace-nowrap">
              DEV<span className="text-acid">TEAM</span>
              <span className="text-acid animate-blink">▌</span>
            </span>
          </div>
        )}
        <button
          onClick={onToggle}
          className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-sm text-muted hover:text-acid hover:bg-surface-3 transition-all"
          title={collapsed ? 'Развернуть' : 'Свернуть'}
        >
          {collapsed ? <ChevronRight size={13} /> : <ChevronLeft size={13} />}
        </button>
      </div>

      {/* ── Scrollable content ── */}
      <div className="flex-1 overflow-y-auto overflow-x-hidden py-3">

        {/* Collapsed: icon-only column */}
        {collapsed ? (
          <div className="flex flex-col items-center gap-1 px-1.5">
            {/* + button */}
            <button
              onClick={onCreateGroup}
              title="Новый канал"
              className="w-8 h-8 flex items-center justify-center rounded-sm text-muted hover:text-acid hover:bg-surface-3 transition-all mb-1"
            >
              <Plus size={13} />
            </button>

            {/* Agent icons */}
            {agents.map((agent) => {
              const dm = chats.find((c) => c.kind === 'dm' && c.agents.length === 1 && c.agents[0] === agent.role)
              const isActive = dm ? dm.id === activeChatId : false
              const color = ROLE_COLORS[agent.role] ?? '#6b7280'

              return (
                <button
                  key={agent.role}
                  onClick={() => onOpenDm(agent.role)}
                  title={`${agent.name} — ${agent.title}`}
                  className="w-8 h-8 flex items-center justify-center rounded-sm text-base leading-none transition-all"
                  style={{
                    background: isActive ? `${color}18` : 'transparent',
                    border: `1px solid ${isActive ? `${color}35` : 'transparent'}`,
                    boxShadow: isActive ? `0 0 8px ${color}20` : 'none',
                  }}
                >
                  {agent.emoji}
                </button>
              )
            })}

            {/* Group channel icons */}
            {groupChats.length > 0 && (
              <>
                <div className="w-4 h-px my-1" style={{ background: '#181826' }} />
                {groupChats.map((chat) => {
                  const isActive = chat.id === activeChatId
                  return (
                    <button
                      key={chat.id}
                      onClick={() => onOpenChat(chat.id)}
                      title={chatLabel(chat, agents)}
                      className="w-8 h-8 flex items-center justify-center rounded-sm transition-all"
                      style={{
                        background: isActive ? '#1a1a28' : 'transparent',
                        border: `1px solid ${isActive ? '#2a2a3e' : 'transparent'}`,
                      }}
                    >
                      <Hash size={13} className={isActive ? 'text-acid' : 'text-muted'} />
                    </button>
                  )
                })}
              </>
            )}
          </div>
        ) : (
          /* Expanded: full sidebar */
          <div className="space-y-5">
            {/* Employees */}
            <section className="px-3">
              <div className="flex items-center justify-between px-1 mb-2">
                <p className="section-label">Сотрудники</p>
                <button
                  onClick={onCreateGroup}
                  title="Новый канал"
                  className="w-5 h-5 flex items-center justify-center rounded-sm text-muted hover:text-acid hover:bg-surface-3 transition-all"
                >
                  <Plus size={11} strokeWidth={2.5} />
                </button>
              </div>
              <div className="space-y-0.5">
                {agents.map((agent) => {
                  const dm = chats.find((c) => c.kind === 'dm' && c.agents.length === 1 && c.agents[0] === agent.role)
                  return (
                    <AgentCard
                      key={agent.role}
                      agent={agent}
                      isActive={dm ? dm.id === activeChatId : false}
                      onClick={() => onOpenDm(agent.role)}
                    />
                  )
                })}
              </div>
            </section>

            {/* Group channels */}
            {groupChats.length > 0 && (
              <section className="px-3">
                <p className="section-label px-1 mb-2">Каналы</p>
                <div className="space-y-0.5">
                  {groupChats.map((chat) => (
                    <ChatRow
                      key={chat.id}
                      label={chatLabel(chat, agents)}
                      isActive={chat.id === activeChatId}
                      icon={<Hash size={11} className="text-muted flex-shrink-0" />}
                      onClick={() => onOpenChat(chat.id)}
                      onDelete={() => onDeleteChat(chat.id)}
                    />
                  ))}
                </div>
              </section>
            )}
          </div>
        )}
      </div>

      {/* ── Footer ── */}
      {!collapsed && (
        <div className="flex-shrink-0 px-4 py-3" style={{ borderTop: '1px solid #181826' }}>
          <p className="font-mono text-[10px] text-muted tracking-wider">
            <span className="text-acid">●</span> ONLINE
          </p>
        </div>
      )}
    </aside>
  )
}

function ChatRow({
  label, isActive, icon, onClick, onDelete,
}: {
  label: string; isActive: boolean; icon: React.ReactNode
  onClick: () => void; onDelete: () => void
}) {
  return (
    <div
      className={`group flex items-center gap-2 px-3 py-1.5 rounded-sm cursor-pointer transition-all duration-100 ${isActive ? 'bg-surface-3' : 'hover:bg-surface-2'}`}
      onClick={onClick}
    >
      {icon}
      <span className={`flex-1 text-[13px] truncate transition-colors ${isActive ? 'text-white' : 'text-[#9898b2] group-hover:text-[#c4c4d8]'}`}>
        {label}
      </span>
      <button
        onClick={(e) => { e.stopPropagation(); onDelete() }}
        className="opacity-0 group-hover:opacity-100 text-muted hover:text-red-400 transition-all p-0.5 rounded"
      >
        <Trash2 size={10} />
      </button>
    </div>
  )
}
