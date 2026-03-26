/** Дата/время последней успешной индексации (ISO с бэкенда) для отображения в UI. */
export const formatKnowledgeIndexedAt = (iso: string | null | undefined): string => {
  if (!iso || typeof iso !== 'string') return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'short',
    timeStyle: 'short'
  }).format(d)
}
