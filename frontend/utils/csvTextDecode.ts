/**
 * Выбор лучшей декодировки для CSV-байтов (UTF-8 vs windows-1251) по эвристике кириллицы.
 * Совпадает с логикой импорта прямых вопросов в AgentKnowledgePanel.
 */

const countMatches = (value: string, pattern: RegExp): number => value.match(pattern)?.length ?? 0

export const estimateCyrillicDecodeScore = (value: string): number => {
  const cyrillicCount = countMatches(value, /[А-Яа-яЁё]/g)
  const latinCount = countMatches(value, /[A-Za-z]/g)
  const replacementCount = countMatches(value, /\uFFFD/g)
  const mojibakeRuPairs = countMatches(value, /[РС][а-яё]/g)
  const mojibakeWeird = countMatches(value, /[ЃЌЋЏ]/g)
  const mojibakeCount = countMatches(value, /[ÐÑ]/g)
  return (
    cyrillicCount
    + latinCount
    - replacementCount * 10
    - mojibakeCount * 4
    - mojibakeRuPairs * 3
    - mojibakeWeird * 2
  )
}

export const decodeCsvBuffer = (buffer: ArrayBuffer): string => {
  const bytes = new Uint8Array(buffer)
  const utf8Decoded = new TextDecoder('utf-8').decode(bytes).replace(/^\uFEFF/, '')

  let bestDecoded = utf8Decoded
  let bestScore = estimateCyrillicDecodeScore(utf8Decoded)

  try {
    const cp1251Decoded = new TextDecoder('windows-1251').decode(bytes).replace(/^\uFEFF/, '')
    const cp1251Score = estimateCyrillicDecodeScore(cp1251Decoded)
    if (cp1251Score > bestScore) {
      bestDecoded = cp1251Decoded
    }
  } catch {
    // Окружение без windows-1251
  }

  return bestDecoded
}
