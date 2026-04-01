import { $fetch } from 'ofetch'
import {
  clearStoredAuthData,
  ensureFreshAccessToken,
  getStoredAccessToken,
  initAuthActivityTracking,
  isRefreshFailure,
  refreshAuthSession
} from '~/composables/authSessionManager'
import { getReadableErrorMessage, getErrorTitle } from '~/utils/api-errors'

let navigateTo: any = null

const AUTH_WITHOUT_BEARER_ENDPOINTS = [
  '/auth/login',
  '/auth/register',
  '/auth/token',
  '/auth/refresh',
  '/auth/logout',
  '/auth/register-by-invite',
  '/invitations/accept'
]

const getRequestUrl = (request: Request | string): string =>
  typeof request === 'string' ? request : request.url

const isRequestWithoutBearer = (url: string): boolean =>
  AUTH_WITHOUT_BEARER_ENDPOINTS.some((endpoint) => url.includes(endpoint))

const getResponseErrorCode = (response: any): string | null => {
  const responseData = response?._data
  if (!responseData || typeof responseData !== 'object') return null

  const detail = (responseData as { detail?: unknown }).detail
  const normalizedData = detail && typeof detail === 'object' && !Array.isArray(detail)
    ? (detail as { error?: unknown })
    : (responseData as { error?: unknown })
  const errorCode = normalizedData.error
  return typeof errorCode === 'string' && errorCode.length > 0 ? errorCode : null
}

const redirectToLogin = () => {
  clearStoredAuthData()
  if (navigateTo) {
    navigateTo('/login', { replace: true })
    return
  }
  window.location.href = '/login'
}

export const useApiFetch = () => {
  // @ts-ignore - Nuxt 3 auto-imports
  const { public: { apiBase } } = useRuntimeConfig()

  // Инициализируем navigateTo только один раз
  if (!navigateTo && typeof window !== 'undefined') {
    initAuthActivityTracking()
    try {
      // @ts-ignore - Nuxt 3 auto-imports
      navigateTo = useNuxtApp().$router?.push || (() => window.location.href = '/login')
    } catch {
      navigateTo = () => window.location.href = '/login'
    }
  }

  const apiFetch = $fetch.create({
    baseURL: apiBase,
    /** 204 No Content и пустое тело: иначе JSON.parse('') падает → «Failed to fetch» в UI. */
    parseResponse: (responseText) => {
      if (responseText === '' || responseText == null) return null
      const trimmed = String(responseText).trim()
      if (!trimmed) return null
      try {
        return JSON.parse(responseText)
      } catch {
        return responseText
      }
    },
    async onRequest({ request, options }) {
      ;(options as any).credentials = (options as any).credentials || 'include'

      // Автоматически добавляем токен авторизации, если он есть
      if (typeof window !== 'undefined') {
        const reqUrl = getRequestUrl(request as Request | string)
        if (isRequestWithoutBearer(reqUrl)) return

        const ensuredToken = await ensureFreshAccessToken()
        if (!ensuredToken.token) {
          if (ensuredToken.shouldLogout) {
            redirectToLogin()
          }
          return
        }

        const existingHeaders = (options.headers as unknown as Record<string, string>) || {}
        ;(options as any).headers = {
          ...existingHeaders,
          Authorization: `Bearer ${ensuredToken.token}`
        }
      }
    },
    async onResponseError({ request, response, options }) {
      const retryOptions = options as any

      // Определяем URL запроса для проверки типа
      const requestUrl = getRequestUrl(request as Request | string)

      // Если получили 401, пробуем обновить токен и повторить запрос
      // НО: для auth-эндпоинтов без Bearer не делаем retry
      const isAuthWithoutBearer = isRequestWithoutBearer(requestUrl)
      const responseErrorCode = getResponseErrorCode(response)

      if (
        response.status === 401 &&
        typeof window !== 'undefined' &&
        (responseErrorCode === 'invalid_refresh_token' || responseErrorCode === 'refresh_token_expired')
      ) {
        redirectToLogin()
        return
      }

      if (response.status === 401 && typeof window !== 'undefined' && !isAuthWithoutBearer) {
        // Обновляем токен только для кейса "invalid_token".
        if (responseErrorCode && responseErrorCode !== 'invalid_token') {
          return
        }

        // Защита от бесконечного цикла ретраев
        if (retryOptions?._retry) {
          return
        } else {
          retryOptions._retry = true
        }

        const refreshResult = await refreshAuthSession()

        if (refreshResult.success) {
          const newToken = getStoredAccessToken()
          if (newToken) {
            const existingHeaders = (options.headers as unknown as Record<string, string>) || {}
            ;(options as any).headers = {
              ...existingHeaders,
              Authorization: `Bearer ${newToken}`
            }
            ;(options as any).credentials = (options as any).credentials || 'include'
            return await apiFetch(request as any, options as any)
          }
        } else if (isRefreshFailure(refreshResult)) {
          // На 409 не разлогиниваем сразу: даем короткий шанс дочитать новый токен.
          if (refreshResult.reason === 'refresh_token_in_use') {
            await new Promise((resolve) => setTimeout(resolve, 300))
            const tokenAfterWait = getStoredAccessToken()
            if (tokenAfterWait) {
              const existingHeaders = (options.headers as unknown as Record<string, string>) || {}
              ;(options as any).headers = {
                ...existingHeaders,
                Authorization: `Bearer ${tokenAfterWait}`
              }
              ;(options as any).credentials = (options as any).credentials || 'include'
              return await apiFetch(request as any, options as any)
            }
          }

          if (refreshResult.shouldLogout) {
            redirectToLogin()
          }
        }
      }

      // Обработка 403 (Forbidden) - недостаточно прав
      if (response.status === 403 && typeof window !== 'undefined') {
        const isAuthRequestFor403 = requestUrl.includes('/auth/') || requestUrl.includes('/invitations/')
        
        // Для не-auth запросов показываем сообщение о недостаточных правах
        if (!isAuthRequestFor403) {
          try {
            const { useToast } = await import('./useToast')
            const toast = useToast()
            toast.error(
              getErrorTitle({ status: 403 }, 'Доступ запрещён'),
              getReadableErrorMessage({ status: 403, data: response._data }, 'У вас нет доступа к выполнению этого действия.')
            )
          } catch (err) {
            console.error('Failed to show 403 error toast:', err)
          }
        }
        
        // Не очищаем токены для 403 (в отличие от 401)
        // Пользователь авторизован, но не имеет прав на действие
        console.warn('🔒 Access forbidden (403):', {
          url: requestUrl,
          message: 'Insufficient permissions'
        })
      }

      // Обработка 429 (Rate Limiting)
      // Ошибка будет обработана в компоненте через apiError.retry_after
      // Здесь только логируем для отладки
      if (response.status === 429 && typeof window !== 'undefined') {
        const retryAfter = response.headers?.get('retry-after') || '60'
        console.warn(`Rate limit exceeded. Retry after ${retryAfter} seconds`)
      }

      // Обработка 502, 503, 504 - Gateway/Server errors
      if ([502, 503, 504].includes(response.status) && typeof window !== 'undefined') {
        const statusText = response.status === 502 ? 'Bad Gateway' 
                         : response.status === 503 ? 'Service Unavailable'
                         : 'Gateway Timeout'
        console.error(`❌ ${statusText} (${response.status}):`, {
          url: request,
          status: response.status,
          statusText: response.statusText,
          message: `Backend server is not responding. Please try again later.`
        })
      }

      // Логируем все остальные ошибки для отладки
      if (typeof window !== 'undefined' && response.status >= 500) {
        console.error(`❌ Server error (${response.status}):`, {
          url: request,
          status: response.status,
          statusText: response.statusText
        })
      }
    }
  })

  return apiFetch
}

export const getAuthHeaders = (token?: string | null): Record<string, string> =>
  token ? { Authorization: `Bearer ${token}` } : {}
