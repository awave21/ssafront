import type { DevteamAgent } from '@/types/devteam'

const ROLE_COLORS: Record<string, string> = {
  orchestrator: '#c084fc',
  backend:      '#60a5fa',
  frontend:     '#f472b6',
  devops:       '#fb923c',
  ai_engineer:  '#22d3ee',
  analyst:      '#4ade80',
}

interface Props {
  agent: DevteamAgent
  isActive?: boolean
  onClick: () => void
}

export function AgentCard({ agent, isActive, onClick }: Props) {
  const color = ROLE_COLORS[agent.role] ?? '#6b7280'

  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-3 py-2 text-left transition-all duration-150 rounded-sm relative group ${
        isActive ? 'bg-surface-3' : 'hover:bg-surface-2'
      }`}
    >
      {/* Role color indicator */}
      <div
        className="flex-shrink-0 w-0.5 h-8 rounded-full transition-opacity"
        style={{
          background: color,
          opacity: isActive ? 1 : 0.35,
        }}
      />

      {/* Emoji avatar */}
      <div
        className="flex-shrink-0 w-7 h-7 rounded-sm flex items-center justify-center text-base leading-none transition-all"
        style={{
          background: isActive ? `${color}18` : 'transparent',
          border: `1px solid ${isActive ? `${color}30` : 'transparent'}`,
        }}
      >
        {agent.emoji}
      </div>

      {/* Info */}
      <div className="min-w-0 flex-1">
        <p
          className="text-[13px] font-semibold leading-tight truncate transition-colors"
          style={{ color: isActive ? color : '#d8d8ec' }}
        >
          {agent.name}
        </p>
        <p className="text-[11px] text-muted leading-tight truncate mt-0.5">
          {agent.title}
        </p>
      </div>

      {/* Online dot */}
      <div
        className="flex-shrink-0 w-1.5 h-1.5 rounded-full opacity-0 group-hover:opacity-100 transition-opacity"
        style={{ background: color }}
      />
    </button>
  )
}
