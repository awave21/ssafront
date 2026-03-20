/**
 * Склонение слова по числу (русский язык)
 * @param count - число
 * @param forms - [единственное, 2-4, множественное] напр. ['запись', 'записи', 'записей']
 */
export const pluralize = (count: number, forms: [string, string, string]): string => {
  const abs = Math.abs(count) % 100
  const lastDigit = abs % 10
  if (abs >= 11 && abs <= 19) return forms[2]
  if (lastDigit === 1) return forms[0]
  if (lastDigit >= 2 && lastDigit <= 4) return forms[1]
  return forms[2]
}
