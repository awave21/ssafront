import { useState, useEffect, useCallback } from 'react'
import { ChatList } from './components/ChatList'
import { ChatArea } from './components/ChatArea'
import { GroupChatModal } from './components/GroupChatModal'
import { useDevteamChat } from './hooks/useDevteamChat'
import { ROLE_COLORS } from './components/MessageBubble'
import type { DevteamChat, WsEvent } from './types/devteam'

export function App() {
  const {
    agents, chats, messages, streaming, loading, sending, waitingForAgent,
    loadAgents, loadChats, loadMessages,
    openDm, createGroupChat, deleteChat, updateChatAgents, sendMessage,
    handleWsEvent, clearChatState,
  } = useDevteamChat()

  const [activeChat, setActiveChat]       = useState<DevteamChat | null>(null)
  const [showGroupModal, setGroupModal]   = useState(false)
  const [initDone, setInitDone]           = useState(false)
  const [sidebarCollapsed, setSidebar]    = useState(false)

  useEffect(() => {
    Promise.all([loadAgents(), loadChats()]).then(() => setInitDone(true))
  }, [])

  const switchChat = useCallback(async (chat: DevteamChat) => {
    clearChatState()
    setActiveChat(chat)
    await loadMessages(chat.id)
  }, [loadMessages, clearChatState])

  const handleOpenDm    = useCallback(async (role: string) => switchChat(await openDm(role, chats)), [chats, openDm, switchChat])
  const handleOpenChat  = useCallback(async (id: number) => { const c = chats.find((c) => c.id === id); if (c) await switchChat(c) }, [chats, switchChat])
  const handleCreateGrp = useCallback(async (roles: string[], title?: string) => switchChat(await createGroupChat(roles, title)), [createGroupChat, switchChat])
  const handleDeleteChat = useCallback(async (id: number) => { await deleteChat(id); if (activeChat?.id === id) setActiveChat(null) }, [deleteChat, activeChat])
  const handleSend      = useCallback(async (text: string, replyToId?: number) => { if (activeChat) await sendMessage(activeChat.id, text, replyToId) }, [activeChat, sendMessage])
  const handleWsForChat = useCallback((ev: WsEvent) => handleWsEvent(ev), [handleWsEvent])

  if (!initDone) {
    return (
      <div className="h-screen flex flex-col items-center justify-center bg-surface-0 gap-4">
        <div className="font-display font-bold text-2xl tracking-[0.3em] text-white">
          DEV<span className="text-acid">TEAM</span>
        </div>
        <div className="flex items-center gap-2 font-mono text-[11px] text-muted tracking-widest">
          <span className="text-acid animate-pulse">◆</span>
          ИНИЦИАЛИЗАЦИЯ
        </div>
      </div>
    )
  }

  return (
    <div className="h-screen flex bg-surface-0 overflow-hidden">
      <ChatList
        agents={agents}
        chats={chats}
        activeChatId={activeChat?.id ?? null}
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebar((v) => !v)}
        onOpenDm={handleOpenDm}
        onOpenChat={handleOpenChat}
        onCreateGroup={() => setGroupModal(true)}
        onDeleteChat={handleDeleteChat}
      />

      <main className="flex-1 flex min-w-0">
        {activeChat ? (
          <ChatArea
            key={activeChat.id}
            chat={activeChat}
            agents={agents}
            messages={messages}
            streaming={streaming}
            loading={loading}
            sending={sending}
            waitingForAgent={waitingForAgent}
            onSend={handleSend}
            onWsEvent={handleWsForChat}
            onUpdateAgents={updateChatAgents}
          />
        ) : (
          <WelcomeScreen agents={agents} onOpenDm={handleOpenDm} />
        )}
      </main>

      {showGroupModal && (
        <GroupChatModal
          agents={agents}
          onClose={() => setGroupModal(false)}
          onCreate={handleCreateGrp}
        />
      )}
    </div>
  )
}

function WelcomeScreen({ agents, onOpenDm }: { agents: any[]; onOpenDm: (role: string) => void }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-10 px-8 animate-fade-in">
      <div className="text-center">
        <h1 className="font-display font-bold text-4xl tracking-[0.25em] text-white mb-2">
          DEV<span className="text-acid">TEAM</span>
        </h1>
        <p className="font-mono text-[11px] text-muted tracking-[0.25em]">
          AI ENGINEERING COMMAND CENTER
        </p>
      </div>

      <div className="grid grid-cols-3 gap-3 max-w-lg w-full">
        {agents.map((agent) => {
          const color = ROLE_COLORS[agent.role] ?? '#6b7280'
          return (
            <button
              key={agent.role}
              onClick={() => onOpenDm(agent.role)}
              className="flex flex-col items-center gap-2 p-4 rounded-sm text-center transition-all duration-150 hover:scale-[1.02]"
              style={{ background: '#0a0a12', border: '1px solid #1a1a28' }}
              onMouseEnter={(e) => {
                const el = e.currentTarget as HTMLButtonElement
                el.style.borderColor = `${color}40`
                el.style.background = `${color}08`
              }}
              onMouseLeave={(e) => {
                const el = e.currentTarget as HTMLButtonElement
                el.style.borderColor = '#1a1a28'
                el.style.background = '#0a0a12'
              }}
            >
              <span className="text-2xl">{agent.emoji}</span>
              <div>
                <p className="font-display font-bold text-[11px] tracking-[0.15em] transition-colors" style={{ color }}>
                  {agent.name.toUpperCase()}
                </p>
                <p className="font-mono text-[9px] text-muted mt-0.5 tracking-wider">{agent.title}</p>
              </div>
            </button>
          )
        })}
      </div>

      <p className="font-mono text-[10px] text-dim tracking-widest">
        ВЫБЕРИТЕ СОТРУДНИКА ДЛЯ НАЧАЛА ДИАЛОГА
      </p>
    </div>
  )
}
