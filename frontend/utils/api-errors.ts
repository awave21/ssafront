/**
 * Централизованный маппинг ошибок API в читаемые сообщения для пользователя.
 *
 * Использование:
 *   import { getReadableErrorMessage, getReadableApiError } from '~/utils/api-errors'
 *
 *   // Из catch-блока:
 *   error.value = getReadableErrorMessage(err, 'Не удалось загрузить данные')
 *
 *   // Из ответа API с полем error/message:
 *   const msg = getReadableApiError(apiError.error, apiError.message)
 */

// ── HTTP Status → читаемое сообщение ────────────────────────────────

const HTTP_STATUS_MESSAGES: Record<number, string> = {
  400: 'Некорректный запрос. Проверьте введённые данные.',
  401: 'Сессия истекла. Пожалуйста, войдите снова.',
  403: 'Недостаточно прав для выполнения этого действия.',
  404: 'Запрашиваемый ресурс не найден.',
  405: 'Данное действие не поддерживается.',
  408: 'Превышено время ожидания запроса. Попробуйте позже.',
  409: 'Конфликт данных. Возможно, ресурс уже существует.',
  413: 'Слишком большой объём данных. Уменьшите размер файла.',
  422: 'Ошибка валидации. Проверьте правильность заполнения полей.',
  429: 'Слишком много запросов. Подождите немного и попробуйте снова.',
  500: 'Внутренняя ошибка сервера. Попробуйте позже.',
  502: 'Сервер временно недоступен. Попробуйте позже.',
  503: 'Сервис временно недоступен. Ведутся технические работы.',
  504: 'Сервер не ответил вовремя. Попробуйте позже.',
}

// ── API error code → читаемое сообщение ─────────────────────────────

const API_ERROR_MESSAGES: Record<string, string> = {
  // Auth
  invalid_credentials: 'Неверный логин или пароль.',
  account_inactive: 'Аккаунт деактивирован. Обратитесь к администратору.',
  tenant_inactive: 'Организация деактивирована. Обратитесь к администратору.',
  email_exists: 'Пользователь с таким email уже существует.',
  invalid_token: 'Сессия истекла. Пожалуйста, войдите снова.',
  token_expired: 'Сессия истекла. Пожалуйста, войдите снова.',
  invalid_refresh_token: 'Сессия истекла. Пожалуйста, войдите снова.',
  refresh_token_expired: 'Сессия истекла. Пожалуйста, войдите снова.',
  refresh_token_revoked: 'Сессия была завершена. Пожалуйста, войдите снова.',
  refresh_token_not_found: 'Сессия не найдена. Пожалуйста, войдите снова.',

  // Rate limiting
  rate_limit_exceeded: 'Слишком много запросов. Подождите немного и попробуйте снова.',

  // Access
  forbidden: 'Недостаточно прав для выполнения этого действия.',
  insufficient_permissions: 'Недостаточно прав для выполнения этого действия.',

  // Resources
  not_found: 'Запрашиваемый ресурс не найден.',
  already_exists: 'Такой ресурс уже существует.',
  conflict: 'Конфликт данных. Ресурс был изменён другим пользователем.',

  // Validation
  validation_error: 'Ошибка валидации. Проверьте введённые данные.',
  invalid_input: 'Некорректные входные данные.',
  invalid_email: 'Некорректный формат email.',
  weak_password: 'Пароль слишком простой. Используйте не менее 8 символов.',

  // Network / server
  bad_gateway: 'Сервер временно недоступен. Попробуйте позже.',
  service_unavailable: 'Сервис временно недоступен. Попробуйте позже.',
  gateway_timeout: 'Сервер не ответил вовремя. Попробуйте позже.',
  network_error: 'Ошибка сети. Проверьте подключение к интернету.',
  unknown_error: 'Произошла непредвиденная ошибка. Попробуйте позже.',

  // Invitations
  invitation_expired: 'Срок действия приглашения истёк.',
  invitation_already_accepted: 'Приглашение уже было использовано.',
  invitation_not_found: 'Приглашение не найдено или было отменено.',
}

// Технические сообщения из бэкенда, которые нужно подменить
const RAW_MESSAGE_OVERRIDES: Array<[RegExp, string]> = [
  [/fetch failed/i, 'Ошибка сети. Проверьте подключение к интернету.'],
  [/failed to fetch/i, 'Ошибка сети. Проверьте подключение к интернету.'],
  [/network\s*(error|request)/i, 'Ошибка сети. Проверьте подключение к интернету.'],
  [/invalid credentials/i, 'Неверный логин или пароль.'],
  [/invalid (email|username|login) or password/i, 'Неверный логин или пароль.'],
  [/timeout/i, 'Превышено время ожидания. Попробуйте позже.'],
  [/aborted/i, 'Запрос был отменён. Попробуйте снова.'],
  [/econnrefused/i, 'Сервер недоступен. Попробуйте позже.'],
  [/enotfound/i, 'Сервер не найден. Проверьте подключение к интернету.'],
  [/socket hang up/i, 'Соединение с сервером было прервано. Попробуйте позже.'],
  [/internal server error/i, 'Внутренняя ошибка сервера. Попробуйте позже.'],
  [/bad gateway/i, 'Сервер временно недоступен. Попробуйте позже.'],
  [/service unavailable/i, 'Сервис временно недоступен. Попробуйте позже.'],
  [/gateway timeout/i, 'Сервер не ответил вовремя. Попробуйте позже.'],
  // HTTP status in message, e.g. "Stream error: 502", "Ошибка экспорта: 503"
  [/:\s*50[0-4]$/i, 'Сервер временно недоступен. Попробуйте позже.'],
  [/:\s*40[13]$/i, 'Сессия истекла или недостаточно прав. Попробуйте войти снова.'],
  [/:\s*429$/i, 'Слишком много запросов. Подождите немного и попробуйте снова.'],
  [/:\s*404$/i, 'Запрашиваемый ресурс не найден.'],
]

/**
 * Определяет, содержит ли сообщение технические детали,
 * которые не стоит показывать пользователю.
 */
const isTechnicalMessage = (message: string): boolean => {
  if (!message) return false
  const lower = message.toLowerCase()
  // HTTP коды в сыром виде
  if (/^(get|post|put|patch|delete|head|options)\s/i.test(message)) return true
  if (/^\[?\d{3}\]?\s/.test(message)) return true
  if (lower.includes('status code') || lower.includes('statuscode')) return true
  // Stack traces / file paths
  if (message.includes(' at ') && message.includes('(')) return true
  if (/\.(js|ts|vue|mjs):\d+/.test(message)) return true
  // JSON blobs
  if (message.startsWith('{') && message.endsWith('}')) return true
  return false
}

/**
 * Возвращает читаемое сообщение по коду ошибки API.
 * Если код не известен — возвращает переданное сообщение от API или дефолт.
 */
export const getReadableApiError = (
  errorCode: string | undefined | null,
  apiMessage?: string | null,
  fallback = 'Произошла ошибка. Попробуйте позже.'
): string => {
  // 1) Маппинг по коду ошибки
  if (errorCode && API_ERROR_MESSAGES[errorCode]) {
    return API_ERROR_MESSAGES[errorCode]
  }

  // 2) Если есть читаемое сообщение от API (на русском или понятном английском) — вернуть его
  if (apiMessage && !isTechnicalMessage(apiMessage)) {
    // Проверяем на сырые шаблоны
    for (const [pattern, replacement] of RAW_MESSAGE_OVERRIDES) {
      if (pattern.test(apiMessage)) return replacement
    }
    return apiMessage
  }

  return fallback
}

/**
 * Возвращает читаемое сообщение по HTTP-статусу.
 */
export const getHttpStatusMessage = (
  status: number,
  fallback = 'Произошла ошибка. Попробуйте позже.'
): string => {
  return HTTP_STATUS_MESSAGES[status] || fallback
}

/**
 * Извлекает HTTP-статус из объекта ошибки (ofetch / nuxt / axios-like).
 */
const extractHttpStatus = (err: any): number | null => {
  const status = err?.status || err?.statusCode || err?.response?.status || err?.response?.statusCode
  return typeof status === 'number' && status >= 100 ? status : null
}

const extractResponsePayload = (err: any): Record<string, unknown> | null => {
  const data = err?.data || err?.response?._data || err?.response?.data
  if (!data || typeof data !== 'object') return null

  const detail = (data as { detail?: unknown }).detail
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    return detail as Record<string, unknown>
  }

  return data as Record<string, unknown>
}

/**
 * Извлекает код ошибки и сообщение из данных ответа.
 */
const extractApiErrorData = (err: any): { code: string | null; message: string | null } => {
  const payload = extractResponsePayload(err)
  if (!payload) return { code: null, message: null }

  const code = typeof payload.error === 'string' ? payload.error : null
  const message = payload.message ?? payload.detail ?? null

  return { code, message: typeof message === 'string' ? message : null }
}

/**
 * Главная функция: получить читаемое сообщение из любого объекта ошибки.
 *
 * @param err       - объект ошибки из catch-блока (ofetch, axios, Error, etc.)
 * @param fallback  - сообщение по умолчанию (контекстное, например «Не удалось загрузить агентов»)
 */
export const getReadableErrorMessage = (
  err: any,
  fallback = 'Произошла ошибка. Попробуйте позже.'
): string => {
  if (!err) return fallback

  // 1) Извлекаем структурированные данные ответа
  const { code, message: apiMessage } = extractApiErrorData(err)

  // 2) Если есть код ошибки API — ищем по нему
  if (code) {
    const mapped = getReadableApiError(code, apiMessage, '')
    if (mapped) return mapped
  }

  // 3) Если есть HTTP-статус — ищем по нему
  const httpStatus = extractHttpStatus(err)
  if (httpStatus) {
    // Для 422 подставляем детали валидации, если есть
    if (httpStatus === 422 && apiMessage) {
      return `Ошибка валидации: ${apiMessage}`
    }
    // Текст из ответа API (часто `detail` у FastAPI при 400/403/502) важнее общего маппинга по статусу,
    // иначе пользователь видит «Некорректный запрос» вместо реальной причины.
    if (apiMessage && !isTechnicalMessage(apiMessage)) {
      return apiMessage
    }
    const httpMsg = HTTP_STATUS_MESSAGES[httpStatus]
    if (httpMsg) return httpMsg
  }

  // 4) Проверяем сырое сообщение err.message
  const rawMessage = apiMessage || (typeof err?.message === 'string' ? err.message : '')
  if (rawMessage) {
    for (const [pattern, replacement] of RAW_MESSAGE_OVERRIDES) {
      if (pattern.test(rawMessage)) return replacement
    }
    // Если сообщение на русском и выглядит как пользовательское — возвращаем
    if (!isTechnicalMessage(rawMessage) && /[а-яА-ЯёЁ]/.test(rawMessage)) {
      return rawMessage
    }
  }

  // 5) Fallback
  return fallback
}

/**
 * Формирует заголовок для toast-уведомления об ошибке на основе HTTP-статуса.
 */
export const getErrorTitle = (err: any, defaultTitle = 'Ошибка'): string => {
  const httpStatus = extractHttpStatus(err)
  const { code } = extractApiErrorData(err)

  if (code === 'rate_limit_exceeded' || httpStatus === 429) return 'Превышен лимит запросов'
  if (code === 'forbidden' || code === 'insufficient_permissions' || httpStatus === 403) return 'Доступ запрещён'
  if (code === 'invalid_credentials') return 'Ошибка входа'
  if (httpStatus === 401) return 'Сессия истекла'
  if (httpStatus === 404) return 'Не найдено'
  if (httpStatus === 409) return 'Конфликт данных'
  if (httpStatus === 422) return 'Ошибка валидации'
  if (httpStatus && httpStatus >= 500) return 'Ошибка сервера'
  if (code === 'network_error') return 'Ошибка сети'

  return defaultTitle
}

/**
 * Получить retry_after из ошибки (для rate-limiting).
 */
export const getRetryAfter = (err: any): number | null => {
  const data = err?.data || err?.response?._data
  if (data?.retry_after && typeof data.retry_after === 'number') return data.retry_after
  const header = err?.response?.headers?.get?.('retry-after')
  if (header) {
    const parsed = parseInt(header, 10)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}
