import { useState } from 'react'
import { ChevronRight, ChevronDown } from 'lucide-react'
import { TodoListBlock } from './TodoListBlock'
import type { DevteamToolCall } from '@/types/devteam'

interface Props {
  toolCall: DevteamToolCall
}

// Extracts the most meaningful preview string from a tool input
function getInputPreview(name: string, input: Record<string, unknown>): string {
  const v = (k: string) => input[k]?.toString() ?? ''
  switch (name) {
    case 'Read':      return v('file_path') || v('path')
    case 'Write':     return v('file_path') || v('path')
    case 'Edit':      return v('file_path') || v('path')
    case 'Glob':      return v('pattern')
    case 'Grep':      return v('pattern') + (input.path ? ` in ${input.path}` : '')
    case 'Bash':      return v('command').slice(0, 80)
    case 'TodoWrite': return ''
    default:          return Object.values(input)[0]?.toString().slice(0, 60) ?? ''
  }
}

// Icon prefix per tool
function getToolIcon(name: string): string {
  switch (name) {
    case 'Read':       return '📄'
    case 'Write':      return '✏️'
    case 'Edit':       return '✏️'
    case 'Glob':       return '🔍'
    case 'Grep':       return '🔍'
    case 'Bash':       return '⚡'
    case 'TodoWrite':  return '▣'
    default:           return '🔧'
  }
}

export function ToolCallBlock({ toolCall }: Props) {
  // TodoWrite always renders as checklist, no collapse needed
  if (toolCall.name === 'TodoWrite') {
    const todos = (toolCall.input as any)?.todos ?? []
    return <TodoListBlock todos={todos} />
  }

  return <GenericToolBlock toolCall={toolCall} />
}

function GenericToolBlock({ toolCall }: Props) {
  const [open, setOpen] = useState(false)
  const isRunning = !toolCall.output

  const icon    = getToolIcon(toolCall.name)
  const preview = getInputPreview(toolCall.name, toolCall.input)

  // For file tools, output is usually big — keep collapsed by default
  const isFileTool = ['Read', 'Write', 'Edit', 'Glob', 'Grep'].includes(toolCall.name)
  const isBash     = toolCall.name === 'Bash'

  return (
    <div
      className="my-1.5 rounded-sm overflow-hidden text-xs font-mono"
      style={{ background: '#06060f', border: '1px solid #151524' }}
    >
      {/* Header row */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 w-full px-3 py-1.5 text-left hover:bg-surface-2 transition-colors"
      >
        <span className="text-muted flex-shrink-0 text-[10px]">
          {open ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
        </span>

        {/* Tool badge */}
        <span className="text-[11px] flex-shrink-0 select-none">{icon}</span>
        <span
          className="px-1.5 py-0.5 rounded-sm text-[10px] font-medium leading-none flex-shrink-0"
          style={{ background: '#1a1228', color: '#c084fc', border: '1px solid #2a1a40' }}
        >
          {toolCall.name}
        </span>

        {/* Preview */}
        {preview && (
          <span className="text-muted truncate flex-1 text-[11px]">
            {preview}
          </span>
        )}

        {/* Status */}
        {isRunning ? (
          <span className="ml-auto flex-shrink-0 flex items-center gap-1">
            <span className="text-acid animate-pulse">◆</span>
            <span className="text-acid text-[10px] tracking-wider">RUNNING</span>
          </span>
        ) : (
          <span className="ml-auto flex-shrink-0 text-[10px] tracking-wider" style={{ color: '#2a4a2a' }}>DONE</span>
        )}
      </button>

      {/* Expanded content */}
      {open && (
        <div style={{ borderTop: '1px solid #151524' }}>
          {/* For Bash — show command prominently */}
          {isBash && toolCall.input.command && (
            <div className="px-3 pt-2 pb-1.5">
              <p className="text-[10px] text-muted tracking-widest mb-1">COMMAND</p>
              <pre className="text-[11px] text-[#9898c8] whitespace-pre-wrap break-all leading-relaxed">
                {toolCall.input.command as string}
              </pre>
            </div>
          )}

          {/* For file tools — show only the path (no full content dump in input) */}
          {isFileTool && (
            <div className="px-3 pt-2 pb-1.5">
              <p className="text-[10px] text-muted tracking-widest mb-1">PATH</p>
              <pre className="text-[11px] text-[#9898c8] whitespace-pre-wrap break-all leading-relaxed">
                {(toolCall.input.file_path ?? toolCall.input.path ?? toolCall.input.pattern ?? '') as string}
              </pre>
            </div>
          )}

          {/* For other tools — show full input JSON */}
          {!isBash && !isFileTool && (
            <div className="px-3 pt-2 pb-1.5">
              <p className="text-[10px] text-muted tracking-widest mb-1">INPUT</p>
              <pre className="text-[11px] text-[#9898c8] whitespace-pre-wrap break-all leading-relaxed max-h-32 overflow-y-auto">
                {JSON.stringify(toolCall.input, null, 2)}
              </pre>
            </div>
          )}

          {/* Output */}
          {toolCall.output && (
            <div className="px-3 pt-1.5 pb-2" style={{ borderTop: '1px solid #0e0e1c' }}>
              <p className="text-[10px] text-muted tracking-widest mb-1">OUTPUT</p>
              <pre className="text-[11px] text-[#6868a0] whitespace-pre-wrap break-all leading-relaxed max-h-40 overflow-y-auto">
                {toolCall.output}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
