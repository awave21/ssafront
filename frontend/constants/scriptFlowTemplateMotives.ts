/** Семена мотивов для готовых шаблонов сценария: создаются в библиотеке при применении шаблона. */

export type TemplateMotiveSeed = {
  name: string
  description: string
}

/** Мотивы под сценарий «Биоревитализация (клиника)».
 *  Имена совпадают с привязкой к узлам в BIOREVITALIZATION_NODE_MOTIVE_BY_NODE_ID.
 */
export const BIOREVITALIZATION_TEMPLATE_MOTIVES: TemplateMotiveSeed[] = [
  {
    name: 'Доверие к очной консультации',
    description:
      'Клиенту важна безопасность решения: очный осмотр и мнение врача, а не только информация из статей или самоназначение.',
  },
  {
    name: 'Сравнение цены между клиниками',
    description:
      'Клиент ориентируется на стоимость позиции в прайсе и сравнивает предложения конкурентов.',
  },
  {
    name: 'Прозрачность стоимости перед записью',
    description:
      'Нужна ясная цена до записи; часто уточняют, была ли процедура назначена доктором.',
  },
  {
    name: 'Честный сервис без навязанных продаж',
    description:
      'Страх давления и «развода на услуги»: важны экспертиза и свобода выбора после консультации.',
  },
  {
    name: 'Комфорт и отсутствие боли',
    description:
      'Клиент боится уколов, болевых ощущений или синяков — выбирает безинъекционный метод или ищет подтверждение, что будет комфортно.',
  },
  {
    name: 'Доверие к результату через опыт других',
    description:
      'Клиент пришёл по рекомендации подруги или статьи — ищет подтверждение правильности решения.',
  },
  {
    name: 'Готовность к записи',
    description:
      'Клиент принял принципиальное решение о процедуре и переходит к финальному шагу — выбору времени. Важно не перегружать, а быстро и конкретно довести до записи.',
  },
]

/**
 * После создания мотивов в библиотеке к этим узлам шаблона добавляются `kg_links.motive_ids`.
 * Ключ — id узла в SCRIPT_FLOW_EXAMPLE_BIOREVITALIZATION, значение — name из семян выше.
 */
export const BIOREVITALIZATION_NODE_MOTIVE_BY_NODE_ID: Record<string, string> = {
  // Presentation
  'bio-eintro':          'Прозрачность стоимости перед записью',
  // Closing / slots
  'bio-eslots':          'Готовность к записи',
  'bio-eslots-noninj':   'Готовность к записи',
  // Injectable branch
  'bio-ecost':           'Прозрачность стоимости перед записью',
  'bio-econsult':        'Доверие к очной консультации',
  'bio-eprice-obj':      'Сравнение цены между клиниками',
  'bio-evar':            'Сравнение цены между клиниками',
  // Trust / retention
  'bio-eface':           'Честный сервис без навязанных продаж',
  'bio-econtact':        'Честный сервис без навязанных продаж',
  'bio-epriceonly':      'Прозрачность стоимости перед записью',
  'bio-epriceonly-later': 'Честный сервис без навязанных продаж',
  // Non-injectable branch
  'bio-enoninj':         'Комфорт и отсутствие боли',
  'bio-ediff':           'Комфорт и отсутствие боли',
  // Experienced client
  'bio-ehasbio':         'Доверие к результату через опыт других',
  'bio-ehasbio-good':    'Доверие к результату через опыт других',
  'bio-ehasbio-bad':     'Доверие к результату через опыт других',
}

export const TEMPLATE_MOTIVE_SEEDS: Record<string, TemplateMotiveSeed[]> = {
  biorevitalization: BIOREVITALIZATION_TEMPLATE_MOTIVES,
}

export const TEMPLATE_NODE_MOTIVE_BY_NODE_ID: Record<string, Record<string, string>> = {
  biorevitalization: BIOREVITALIZATION_NODE_MOTIVE_BY_NODE_ID,
}
