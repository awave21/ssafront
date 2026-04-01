import type { TableAttribute, TableAttributeType } from '~/types/tables'

export const splitCsvLine = (line: string, delimiter: string): string[] => {
  const result: string[] = []
  let current = ''
  let inQuotes = false
  for (let i = 0; i < line.length; i++) {
    const c = line[i]
    if (c === '"') {
      inQuotes = !inQuotes
      continue
    }
    if (!inQuotes && c === delimiter) {
      result.push(current)
      current = ''
      continue
    }
    current += c
  }
  result.push(current)
  return result.map((s) => s.trim().replace(/^"|"$/g, ''))
}

export const normHeaderCell = (s: string) => s.trim().replace(/^\uFEFF/, '').toLowerCase()

export const detectCsvDelimiter = (firstLine: string): string => {
  const commas = (firstLine.match(/,/g) ?? []).length
  const semis = (firstLine.match(/;/g) ?? []).length
  return semis > commas ? ';' : ','
}

export type ParsedCsvTable = {
  delimiter: string
  headerCells: string[]
  /** Каждая строка — массив ячеек (длина может быть меньше заголовков) */
  dataRows: string[][]
  rowCount: number
}

export const parseCsvTable = (text: string): ParsedCsvTable | null => {
  const lines = text
    .split(/\r?\n/)
    .map((l) => l.trimEnd())
    .filter((l) => l.length > 0)
  if (lines.length < 2) return null
  const delimiter = detectCsvDelimiter(lines[0])
  const headerCells = splitCsvLine(lines[0], delimiter)
  if (headerCells.length === 0 || headerCells.every((h) => !h.trim())) return null

  const dataRows: string[][] = []
  for (let r = 1; r < lines.length; r++) {
    const cells = splitCsvLine(lines[r], delimiter)
    dataRows.push(cells)
  }

  return {
    delimiter,
    headerCells,
    dataRows,
    rowCount: dataRows.length,
  }
}

const parseRuDate = (v: string): boolean => {
  const t = v.trim()
  const m = /^(\d{1,2})\.(\d{1,2})\.(\d{4})$/.exec(t)
  if (m) {
    const d = new Date(Number(m[3]), Number(m[2]) - 1, Number(m[1]))
    return !Number.isNaN(d.getTime())
  }
  const iso = Date.parse(t)
  return !Number.isNaN(iso)
}

export const checkCellType = (value: string, attr: TableAttribute): boolean => {
  const v = value.trim()
  if (v === '') return true

  const t = attr.attribute_type
  if (t === 'integer') {
    const n = Number(v)
    return !Number.isNaN(n) && Number.isInteger(n)
  }
  if (t === 'float') {
    const n = Number(v)
    return !Number.isNaN(n)
  }
  if (t === 'boolean') {
    const s = v.toLowerCase()
    return ['true', 'false', '1', '0', 'да', 'нет', 'yes', 'no'].includes(s)
  }
  if (t === 'date' || t === 'datetime' || t === 'timestamp') {
    return parseRuDate(v) || !Number.isNaN(Date.parse(v))
  }
  if (t === 'number_array' || t === 'text_array' || t === 'json') {
    return true
  }
  return true
}

export const inferColumnType = (samples: string[]): TableAttributeType => {
  const nonEmpty = samples.map((s) => s.trim()).filter((s) => s.length > 0).slice(0, 10)
  if (nonEmpty.length === 0) return 'text'

  const allInt = nonEmpty.every((v) => {
    const n = Number(v.replace(',', '.'))
    return !Number.isNaN(n) && Number.isInteger(n) && /^-?\d+$/.test(v.replace(',', '').replace(/^-/, ''))
  })
  if (allInt) return 'integer'

  const allFloat = nonEmpty.every((v) => {
    const n = Number(String(v).replace(',', '.'))
    return !Number.isNaN(n)
  })
  if (allFloat) return 'float'

  const allBool = nonEmpty.every((v) => {
    const s = v.toLowerCase()
    return ['true', 'false', '1', '0', 'да', 'нет', 'yes', 'no'].includes(s)
  })
  if (allBool) return 'boolean'

  const allDate = nonEmpty.every((v) => parseRuDate(v) || !Number.isNaN(Date.parse(v)))
  if (allDate) return 'date'

  return 'text'
}

export const coercePayloadFromData = (
  data: Record<string, unknown>,
  attrs: TableAttribute[]
): Record<string, unknown> => {
  const out: Record<string, unknown> = {}
  for (const attr of attrs) {
    const raw = data[attr.name]
    if (raw === '' || raw === undefined || raw === null) {
      if (attr.is_required) throw new Error(`Заполните поле «${attr.label}»`)
      continue
    }
    if (attr.attribute_type === 'integer') {
      const n = Number(typeof raw === 'string' ? raw.replace(',', '.') : raw)
      if (Number.isNaN(n)) throw new Error(`«${attr.label}» должно быть числом`)
      out[attr.name] = Math.trunc(n)
    } else if (attr.attribute_type === 'float') {
      const n = Number(typeof raw === 'string' ? String(raw).replace(',', '.') : raw)
      if (Number.isNaN(n)) throw new Error(`«${attr.label}» должно быть числом`)
      out[attr.name] = n
    } else if (attr.attribute_type === 'boolean') {
      if (typeof raw === 'boolean') {
        out[attr.name] = raw
      } else if (typeof raw === 'number') {
        out[attr.name] = raw !== 0
      } else if (typeof raw === 'string') {
        const s = raw.trim().toLowerCase()
        out[attr.name] = s === 'true' || s === '1' || s === 'да' || s === 'yes'
      } else {
        out[attr.name] = !!raw
      }
    } else if (attr.attribute_type === 'text_array') {
      if (Array.isArray(raw)) {
        out[attr.name] = raw.map((x) => String(x))
      } else if (typeof raw === 'string') {
        out[attr.name] = raw
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean)
      } else {
        throw new Error(`«${attr.label}» ожидает список значений или строку через запятую`)
      }
    } else if (attr.attribute_type === 'number_array') {
      const parts = Array.isArray(raw)
        ? raw.map((x) => String(x))
        : typeof raw === 'string'
          ? raw
              .split(',')
              .map((s) => s.trim())
              .filter(Boolean)
          : []
      if (parts.length === 0 && attr.is_required) {
        throw new Error(`Заполните поле «${attr.label}»`)
      }
      const nums: number[] = []
      for (const p of parts) {
        const n = Number(String(p).replace(',', '.'))
        if (Number.isNaN(n)) throw new Error(`«${attr.label}» — в массиве должны быть числа`)
        nums.push(n)
      }
      out[attr.name] = nums
    } else if (attr.attribute_type === 'json') {
      if (typeof raw === 'string') {
        const t = raw.trim()
        if (t.startsWith('{') || t.startsWith('[')) {
          try {
            out[attr.name] = JSON.parse(t) as unknown
          } catch {
            out[attr.name] = raw
          }
        } else {
          out[attr.name] = raw
        }
      } else {
        out[attr.name] = raw
      }
    } else if (attr.attribute_type === 'date') {
      const s = typeof raw === 'string' ? raw.trim() : String(raw)
      if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) throw new Error(`«${attr.label}» — укажите дату в формате ГГГГ-ММ-ДД`)
      out[attr.name] = s
    } else if (attr.attribute_type === 'datetime' || attr.attribute_type === 'timestamp') {
      const s = typeof raw === 'string' ? raw.trim() : String(raw)
      const d = new Date(s)
      if (Number.isNaN(d.getTime())) throw new Error(`«${attr.label}» — некорректная дата и время`)
      out[attr.name] = d.toISOString()
    } else {
      out[attr.name] = raw
    }
  }
  return out
}

export const countTypeIssuesInPreview = (
  columnIndex: number,
  previewRowCount: number,
  parsed: ParsedCsvTable,
  attr: TableAttribute
): number => {
  let bad = 0
  const limit = Math.min(previewRowCount, parsed.dataRows.length)
  for (let r = 0; r < limit; r++) {
    const cell = parsed.dataRows[r][columnIndex] ?? ''
    if (!checkCellType(cell, attr)) bad++
  }
  return bad
}
