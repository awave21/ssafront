interface TodoItem {
  content: string
  activeForm?: string
  status: 'pending' | 'in_progress' | 'completed'
}

interface Props {
  todos: TodoItem[]
}

export function TodoListBlock({ todos }: Props) {
  if (!todos || todos.length === 0) return null

  const done    = todos.filter((t) => t.status === 'completed').length
  const total   = todos.length
  const pct     = Math.round((done / total) * 100)

  return (
    <div
      className="my-1.5 rounded-sm overflow-hidden font-mono text-xs"
      style={{ background: '#06060f', border: '1px solid #151524' }}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-3 py-1.5"
        style={{ borderBottom: '1px solid #0e0e1c' }}
      >
        <div className="flex items-center gap-2">
          <span style={{ color: '#c8f752' }}>▣</span>
          <span className="text-[10px] tracking-widest text-muted">TODO</span>
        </div>
        <span className="text-[10px] text-muted tracking-wider">
          {done}/{total}
          {pct > 0 && (
            <span style={{ color: '#c8f75280' }}> · {pct}%</span>
          )}
        </span>
      </div>

      {/* Progress bar */}
      {pct > 0 && (
        <div className="h-px" style={{ background: '#0e0e1c' }}>
          <div
            className="h-full transition-all duration-500"
            style={{ width: `${pct}%`, background: '#c8f752' }}
          />
        </div>
      )}

      {/* Items */}
      <div className="px-3 py-2 space-y-1.5">
        {todos.map((item, i) => (
          <div key={i} className="flex items-start gap-2.5">
            {/* Status icon */}
            <span className="flex-shrink-0 mt-0.5 text-[13px] leading-none select-none">
              {item.status === 'completed' && (
                <span style={{ color: '#4ade80' }}>✓</span>
              )}
              {item.status === 'in_progress' && (
                <span style={{ color: '#c8f752' }} className="animate-pulse">◆</span>
              )}
              {item.status === 'pending' && (
                <span style={{ color: '#2a2a40' }}>○</span>
              )}
            </span>

            {/* Label */}
            <span
              className="text-[11px] leading-snug"
              style={{
                color: item.status === 'completed'
                  ? '#3a3a52'
                  : item.status === 'in_progress'
                    ? '#e0e0ff'
                    : '#5a5a72',
                textDecoration: item.status === 'completed' ? 'line-through' : 'none',
              }}
            >
              {item.status === 'in_progress' ? (item.activeForm ?? item.content) : item.content}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
