export type DiffSegment = {
  type: 'equal' | 'added' | 'removed'
  text: string
}

/**
 * Простой построчный diff двух текстов.
 * Возвращает массив сегментов для левой (old) и правой (new) стороны.
 */
export const computeLineDiff = (
  oldText: string,
  newText: string
): { left: DiffSegment[]; right: DiffSegment[] } => {
  const oldLines = oldText.split('\n')
  const newLines = newText.split('\n')

  // LCS (Longest Common Subsequence) для определения общих строк
  const m = oldLines.length
  const n = newLines.length
  const dp: number[][] = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0))

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      dp[i][j] = oldLines[i - 1] === newLines[j - 1]
        ? dp[i - 1][j - 1] + 1
        : Math.max(dp[i - 1][j], dp[i][j - 1])
    }
  }

  // Backtrack
  const left: DiffSegment[] = []
  const right: DiffSegment[] = []

  let i = m
  let j = n
  const leftStack: DiffSegment[] = []
  const rightStack: DiffSegment[] = []

  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && oldLines[i - 1] === newLines[j - 1]) {
      leftStack.push({ type: 'equal', text: oldLines[i - 1] })
      rightStack.push({ type: 'equal', text: newLines[j - 1] })
      i--
      j--
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      rightStack.push({ type: 'added', text: newLines[j - 1] })
      j--
    } else if (i > 0) {
      leftStack.push({ type: 'removed', text: oldLines[i - 1] })
      i--
    }
  }

  left.push(...leftStack.reverse())
  right.push(...rightStack.reverse())

  return { left, right }
}
