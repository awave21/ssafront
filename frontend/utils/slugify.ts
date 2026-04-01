/** Транслитерация кириллицы (рус.) + slug для кода атрибута таблицы. */

const CYRILLIC_TO_LATIN: Record<string, string> = {
  а: 'a',
  б: 'b',
  в: 'v',
  г: 'g',
  д: 'd',
  е: 'e',
  ё: 'yo',
  ж: 'zh',
  з: 'z',
  и: 'i',
  й: 'y',
  к: 'k',
  л: 'l',
  м: 'm',
  н: 'n',
  о: 'o',
  п: 'p',
  р: 'r',
  с: 's',
  т: 't',
  у: 'u',
  ф: 'f',
  х: 'h',
  ц: 'ts',
  ч: 'ch',
  ш: 'sh',
  щ: 'sch',
  ъ: '',
  ы: 'y',
  ь: '',
  э: 'e',
  ю: 'yu',
  я: 'ya',
  і: 'i',
  ї: 'yi',
  є: 'ye',
  ґ: 'g',
}

const MAX_SLUG_LEN = 100

export const slugifyHeader = (header: string): string => {
  const s = header.trim().replace(/^\uFEFF/, '')
  if (!s) return 'field'

  const lower = s.toLowerCase()
  let out = ''
  for (const ch of lower) {
    if (CYRILLIC_TO_LATIN[ch] !== undefined) {
      out += CYRILLIC_TO_LATIN[ch]
      continue
    }
    if (/[a-z0-9]/.test(ch)) {
      out += ch
      continue
    }
    if (ch === ' ' || ch === '-' || ch === '.' || ch === '/') {
      out += '_'
      continue
    }
    if (/[а-яёіїєґ]/.test(ch)) {
      continue
    }
    if (/[\u0300-\u036f]/.test(ch)) continue
    out += '_'
  }

  out = out.replace(/_+/g, '_').replace(/^_|_$/g, '')
  out = out.replace(/[^a-z0-9_]/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '')
  if (!out) return 'field'
  /** API: `^[a-z][a-z0-9_]*$` */
  if (!/^[a-z]/.test(out)) out = `col_${out}`
  out = out.replace(/[^a-z0-9_]/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '')
  if (!/^[a-z]/.test(out)) out = 'field'
  return out.slice(0, MAX_SLUG_LEN)
}

export const ensureUniqueSlug = (slug: string, reserved: Set<string>): string => {
  let base = slugifyHeader(slug)
  if (!base) base = 'field'
  if (!reserved.has(base)) {
    reserved.add(base)
    return base
  }
  let n = 2
  while (n < 10000) {
    const suffix = `_${n}`
    const maxBase = MAX_SLUG_LEN - suffix.length
    const truncated = base.slice(0, Math.max(1, maxBase))
    const candidate = `${truncated}${suffix}`
    if (!reserved.has(candidate)) {
      reserved.add(candidate)
      return candidate
    }
    n++
  }
  const fallback = `field_${Date.now()}`.slice(0, MAX_SLUG_LEN)
  reserved.add(fallback)
  return fallback
}
