/** Значение для input type="date" (YYYY-MM-DD) из ISO или текстовой даты. */
export const isoToDateInput = (value: unknown): string => {
  if (value === null || value === undefined || value === '') return ''
  const s = String(value).trim()
  const m = /^(\d{4}-\d{2}-\d{2})/.exec(s)
  return m ? m[1] : s.slice(0, 10)
}

/** Значение для input type="datetime-local" (локальная дата/время, без секунд в UI). */
export const isoToDatetimeLocal = (value: unknown): string => {
  if (value === null || value === undefined || value === '') return ''
  const s = String(value).trim()
  if (!s) return ''
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** datetime-local (локальное) → ISO UTC для API. */
export const datetimeLocalToIsoUtc = (value: unknown): string => {
  const s = value === null || value === undefined ? '' : String(value).trim()
  if (!s) throw new Error('Укажите дату и время')
  const d = new Date(s)
  if (Number.isNaN(d.getTime())) throw new Error('Некорректная дата и время')
  return d.toISOString()
}
