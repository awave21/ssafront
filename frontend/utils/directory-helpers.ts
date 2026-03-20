/**
 * Поля, которые считаются длинным текстом и рендерятся через textarea
 */
export const LONG_TEXT_FIELDS = ['answer', 'description', 'info', 'specs']

/**
 * Является ли поле длинным текстом (textarea)
 */
export const isLongTextField = (colName: string): boolean =>
  LONG_TEXT_FIELDS.includes(colName)

/**
 * Валидация формата имени колонки/функции (slug)
 */
export const isValidSlugName = (name: string): boolean => {
  if (!name) return true
  return /^[a-z][a-z0-9_]*$/.test(name)
}

/**
 * Валидация tool_name на уникальность
 */
export const validateToolName = (
  toolName: string,
  existingNames: string[],
  excludeName?: string
): string => {
  if (!toolName) return ''

  if (!/^[a-z][a-z0-9_]*$/.test(toolName)) {
    return 'Только латиница в нижнем регистре, цифры и _'
  }

  const names = excludeName
    ? existingNames.filter(n => n !== excludeName)
    : existingNames

  if (names.includes(toolName)) {
    return 'Такое имя функции уже существует'
  }

  return ''
}

/**
 * Ширина колонки по типу
 */
export const getColumnWidth = (colType: string, colName: string): string => {
  if (colType === 'bool') return '80px'
  if (colType === 'number') return '100px'
  if (colType === 'date') return '120px'
  if (isLongTextField(colName)) return '200px'
  return '140px'
}

/**
 * Форматирование значения ячейки для отображения
 */
export const formatCellValue = (value: any, type: string): string => {
  if (value === null || value === undefined || value === '') return ''

  switch (type) {
    case 'number':
      return typeof value === 'number' ? value.toLocaleString('ru-RU') : String(value)
    case 'date':
      if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value)) {
        const [y, m, d] = value.split('-')
        return `${d}.${m}.${y}`
      }
      return String(value)
    case 'bool':
      return value ? 'Да' : 'Нет'
    default:
      return String(value)
  }
}

/**
 * Плейсхолдеры для полей справочника
 */
export const getFieldPlaceholder = (colName: string, colLabel: string): string => {
  const placeholders: Record<string, string> = {
    question: 'Введите вопрос...',
    answer: 'Введите ответ...',
    name: 'Введите название...',
    description: 'Введите описание...',
    topic: 'Введите тему...',
    info: 'Введите информацию...',
    specs: 'Введите характеристики...'
  }
  return placeholders[colName] || `Введите ${colLabel.toLowerCase()}...`
}
