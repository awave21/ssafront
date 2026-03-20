const TRANSLIT_MAP: Record<string, string> = {
  'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
  'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
  'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
  'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '',
  'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya', ' ': '_', '-': '_'
}

/**
 * Транслитерация кириллицы в латиницу и нормализация в slug-формат
 */
export const transliterate = (input: string): string => {
  const lower = input.toLowerCase()
  let result = ''
  for (const char of lower) {
    result += TRANSLIT_MAP[char] ?? char
  }
  return result.replace(/[^a-z0-9_]/g, '').replace(/_+/g, '_').substring(0, 50)
}

/**
 * Генерация slug с опциональным префиксом (напр. "get_")
 */
export const generateSlug = (label: string, prefix?: string): string => {
  let result = transliterate(label)
  if (prefix && result && !result.startsWith(prefix)) {
    result = prefix + result
  }
  return result
}
