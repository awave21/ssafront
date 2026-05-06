import type { DevteamToolCall } from '@/types/devteam'

export interface TouchedFiles {
  read: string[]
  written: string[]
}

const READ_TOOLS    = new Set(['Read', 'Glob', 'Grep'])
const WRITE_TOOLS   = new Set(['Write', 'Edit', 'NotebookEdit'])

function extractPath(input: Record<string, unknown>): string | null {
  const val = input.file_path ?? input.path ?? input.pattern ?? null
  return val ? String(val) : null
}

function basename(p: string): string {
  return p.split('/').pop() ?? p
}

export function extractTouchedFiles(toolCalls: DevteamToolCall[]): TouchedFiles {
  const read    = new Set<string>()
  const written = new Set<string>()

  for (const tc of toolCalls) {
    if (tc.name === 'TodoWrite') continue
    const path = extractPath(tc.input)
    if (!path) continue
    const label = basename(path)
    if (WRITE_TOOLS.has(tc.name)) {
      written.add(label)
      read.delete(label)  // written supersedes read
    } else if (READ_TOOLS.has(tc.name) && !written.has(label)) {
      read.add(label)
    }
  }

  return {
    read:    [...read],
    written: [...written],
  }
}
