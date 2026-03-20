import { ref, computed, onMounted, readonly } from 'vue'
import { useApiFetch } from './useApiFetch'
import {
  clearStoredAuthData,
  ensureFreshAccessToken,
  getStoredAccessToken,
  isAccessTokenExpired,
  refreshAuthSession,
  setStoredAccessToken
} from '~/composables/authSessionManager'
import { getReadableErrorMessage, getReadableApiError, getHttpStatusMessage } from '~/utils/api-errors'

// Auth interfaces
export type User = {
  id: string
  tenant_id: string
  email: string
  full_name: string
  role: string
  scopes: string[]
  is_active: boolean
  last_login_at: string | null
  created_at: string
  updated_at: string | null
}

export type Tenant = {
  id: string
  name: string
  is_active: boolean
  created_at: string
  updated_at: string | null
}

export type AuthTokenResponse = {
  token: string // access token
  user?: User // опционально, может отсутствовать при получении токена по API ключу
  tenant?: Tenant // опционально, может отсутствовать при получении токена по API ключу
}

export type UserRegister = {
  email: string
  password: string
  full_name?: string
  tenant_name?: string
}

export type UserLogin = {
  email: string
  password: string
}

// Типы ошибок API
export type ApiError = {
  error: string
  message: string
  details?: Record<string, string[]>
  retry_after?: number
}

const extractErrorPayload = (err: any): Record<string, unknown> => {
  const data = err?.data || err?.response?._data || err?.response?.data
  if (!data || typeof data !== 'object') {
    return {}
  }

  const detail = (data as { detail?: unknown }).detail
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) {
    return detail as Record<string, unknown>
  }

  return data as Record<string, unknown>
}

const extractRetryAfter = (payload: Record<string, unknown>, err: any): number | undefined => {
  const retryAfterRaw = payload.retry_after

  if (typeof retryAfterRaw === 'number' && Number.isFinite(retryAfterRaw)) {
    return retryAfterRaw
  }

  if (typeof retryAfterRaw === 'string') {
    const parsed = Number.parseInt(retryAfterRaw, 10)
    if (Number.isFinite(parsed)) return parsed
  }

  const retryAfterHeader = err?.response?.headers?.get?.('retry-after')
  if (typeof retryAfterHeader === 'string') {
    const parsed = Number.parseInt(retryAfterHeader, 10)
    if (Number.isFinite(parsed)) return parsed
  }

  return undefined
}

// Функция для парсинга ошибок API
const parseApiError = (err: any): ApiError => {
  const status = err?.status || err?.statusCode || err?.response?.status || 0
  const payload = extractErrorPayload(err)

  // Извлекаем код ошибки и детали из ответа
  const errorCode = typeof payload.error === 'string' ? payload.error : ''
  const details = payload.details && typeof payload.details === 'object' && !Array.isArray(payload.details)
    ? (payload.details as Record<string, string[]>)
    : undefined
  const retryAfter = extractRetryAfter(payload, err)

  // Определяем error code по статусу, если нет явного кода
  const resolvedCode = errorCode
    || (status === 403 ? 'forbidden' : '')
    || (status === 502 ? 'bad_gateway' : '')
    || (status === 503 ? 'service_unavailable' : '')
    || (status === 504 ? 'gateway_timeout' : '')
    || (!err.response && !err.data && err.message &&
        (err.message.includes('fetch') || err.message.includes('network') || err.message.includes('Failed to fetch'))
          ? 'network_error' : '')
    || 'unknown_error'

  // Используем централизованный маппинг для получения читаемого сообщения
  const message = getReadableErrorMessage(err, 'Произошла ошибка. Попробуйте позже.')

  return {
    error: resolvedCode,
    message,
    details,
    retry_after: retryAfter
  }
}

// Типы для JWT payload
export type JWTPayload = {
  sub: string
  tenant_id: string
  scopes: string[]
  iss?: string
  aud?: string
  exp?: number
  iat?: number
  jti?: string
}

// Функция для декодирования JWT токена (без проверки подписи)
const decodeJWT = (token: string): JWTPayload | null => {
  try {
    const parts = token.split('.')
    if (parts.length !== 3) {
      return null
    }
    
    // Декодируем payload (вторая часть)
    const payload = parts[1]
    // Заменяем URL-safe base64 на обычный base64
    const base64 = payload.replace(/-/g, '+').replace(/_/g, '/')
    // Декодируем base64
    const decoded = atob(base64)
    // Парсим JSON
    return JSON.parse(decoded) as JWTPayload
  } catch (error) {
    console.error('Failed to decode JWT token:', error)
    return null
  }
}

// Функция для проверки срока действия токена
const isTokenExpired = (token: string): boolean => isAccessTokenExpired(token)

// Функция для проверки валидности токена
const isTokenValid = (token: string | null): boolean => {
  if (!token) {
    return false
  }
  
  // Проверяем формат токена
  if (token.split('.').length !== 3) {
    return false
  }
  
  // Проверяем срок действия
  if (isTokenExpired(token)) {
    return false
  }
  
  return true
}

// ── Singleton reactive state (shared across all useAuth() invocations) ──
const _token = ref<string | null>(null)
const _refreshToken = ref<string | null>(null)
const _user = ref<User | null>(null)
const _tenant = ref<Tenant | null>(null)
const _isLoading = ref(false)
const _error = ref<string | null>(null)
let _authInitialized = false
let _authInitPromise: Promise<void> | null = null

export const useAuth = () => {
  const apiFetch = useApiFetch()
  // Use shared singleton state
  const token = _token
  const refreshToken = _refreshToken
  const user = _user
  const tenant = _tenant
  const isLoading = _isLoading
  const error = _error

  // Регистрация нового пользователя
  const register = async (userData: UserRegister) => {
    try {
      isLoading.value = true
      error.value = null

      const response = await apiFetch<AuthTokenResponse>('/auth/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: userData
      })

      token.value = response.token
      refreshToken.value = null
      
      // Убеждаемся, что scopes всегда является массивом
      if (response.user) {
        const parsedUserData = {
          ...response.user,
          scopes: Array.isArray(response.user.scopes) ? response.user.scopes : []
        }
        user.value = parsedUserData
      }
      
      if (response.tenant) {
        tenant.value = response.tenant
      }

      // Access-токен храним только в памяти.
      if (process.client) {
        setStoredAccessToken(response.token)
      }
      
      // Логируем структуру ответа для отладки
      if (process.client) {
        console.log('Register response structure:', {
          has_token: !!response.token,
          has_user: !!response.user,
          has_tenant: !!response.tenant
        })
      }

      // После успешной регистрации обновляем данные через /auth/me для актуализации role и scopes
      if (response.token) {
        await fetchCurrentUser()
      }

      return response
    } catch (err: any) {
      const apiError = parseApiError(err)
      
      // Формируем сообщение об ошибке
      let errorMessage = apiError.message
      
      // Если есть детали валидации, добавляем их
      if (apiError.details) {
        const detailsMessages = Object.entries(apiError.details)
          .map(([field, messages]) => `${field}: ${messages.join(', ')}`)
          .join('; ')
        errorMessage = `${errorMessage}. ${detailsMessages}`
      }
      
      error.value = errorMessage
      
      // Добавляем информацию об ошибке в объект ошибки для компонента
      err.apiError = apiError
      throw err
    } finally {
      isLoading.value = false
    }
  }

  // Вход по email и паролю
  const login = async (loginData: UserLogin) => {
    try {
      isLoading.value = true
      error.value = null

      const response = await apiFetch<AuthTokenResponse>('/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: loginData
      })

      token.value = response.token
      refreshToken.value = null
      
      // Убеждаемся, что scopes всегда является массивом
      if (response.user) {
        const parsedUserData = {
          ...response.user,
          scopes: Array.isArray(response.user.scopes) ? response.user.scopes : []
        }
        user.value = parsedUserData
      }
      
      if (response.tenant) {
        tenant.value = response.tenant
      }

      // Access-токен храним только в памяти.
      if (process.client) {
        setStoredAccessToken(response.token)
      }
      
      // Логируем структуру ответа для отладки
      if (process.client) {
        console.log('Login response structure:', {
          has_token: !!response.token,
          has_user: !!response.user,
          has_tenant: !!response.tenant
        })
      }

      // После успешного входа обновляем данные через /auth/me для актуализации role и scopes
      if (response.token) {
        await fetchCurrentUser()
      }

      return response
    } catch (err: any) {
      const apiError = parseApiError(err)
      
      // Формируем сообщение об ошибке
      let errorMessage = apiError.message
      
      // Если есть детали валидации, добавляем их
      if (apiError.details) {
        const detailsMessages = Object.entries(apiError.details)
          .map(([field, messages]) => `${field}: ${messages.join(', ')}`)
          .join('; ')
        errorMessage = `${errorMessage}. ${detailsMessages}`
      }
      
      error.value = errorMessage
      
      // Добавляем информацию об ошибке в объект ошибки для компонента
      err.apiError = apiError
      throw err
    } finally {
      isLoading.value = false
    }
  }

  // Получение токена по API-ключу
  const loginWithApiKey = async (apiKey: string) => {
    try {
      isLoading.value = true
      error.value = null

      const response = await apiFetch<{
        token: string
      }>('/auth/token', {
        method: 'POST',
        headers: {
          'x-api-key': apiKey,
          'Content-Type': 'application/json'
        },
        body: { api_key: apiKey }
      })

      token.value = response.token
      refreshToken.value = null

      // Access-токен храним только в памяти.
      if (process.client) {
        setStoredAccessToken(response.token)
      }
      
      // Логируем структуру ответа для отладки
      if (process.client) {
        console.log('API Key token response structure:', {
          has_token: !!response.token,
          full_response: response
        })
      }

      return response
    } catch (err: any) {
      const apiError = parseApiError(err)
      error.value = apiError.message
      
      // Добавляем информацию об ошибке в объект ошибки для компонента
      err.apiError = apiError
      throw err
    } finally {
      isLoading.value = false
    }
  }

  // Получение текущего пользователя через /auth/me
  const fetchCurrentUser = async () => {
    if (process.client) {
      const ensuredToken = await ensureFreshAccessToken()
      if (!ensuredToken.token) {
        if (ensuredToken.shouldLogout) {
          resetAuthState(false)
        }
        return null
      }
      token.value = ensuredToken.token
      refreshToken.value = null
    }

    if (!token.value || !isTokenValid(token.value)) {
      return null
    }

    try {
      const response = await apiFetch<{
        user: User
        tenant: Tenant
      }>('/auth/me', {
        method: 'GET'
      })

      // Обновляем данные пользователя и организации
      if (response.user) {
        const parsedUserData = {
          ...response.user,
          scopes: Array.isArray(response.user.scopes) ? response.user.scopes : []
        }
        user.value = parsedUserData
      }

      if (response.tenant) {
        tenant.value = response.tenant
      }

      return response
    } catch (err: any) {
      const apiError = parseApiError(err)
      console.error('Failed to fetch current user:', apiError)
      // Не выбрасываем ошибку, чтобы не ломать инициализацию
      return null
    }
  }
  const syncTokensFromStorage = () => {
    if (!process.client) return
    token.value = getStoredAccessToken()
    refreshToken.value = null
  }

  const resetAuthState = (shouldRedirect: boolean) => {
    token.value = null
    refreshToken.value = null
    user.value = null
    tenant.value = null
    _authInitialized = false
    _authInitPromise = null
    clearStoredAuthData()
    if (shouldRedirect && process.client) {
      window.location.href = '/login'
    }
  }

  // Обновление токена через refresh token
  const refreshAccessToken = async (): Promise<boolean> => {
    if (!process.client) return false

    isLoading.value = true
    error.value = null

    try {
      const refreshResult = await refreshAuthSession()
      if (!refreshResult.success) {
        if (refreshResult.shouldLogout) {
          resetAuthState(false)
        }
        return false
      }

      syncTokensFromStorage()
      return true
    } finally {
      isLoading.value = false
    }
  }

  // Выход
  const logout = async () => {
    try {
      await apiFetch('/auth/logout', {
        method: 'POST'
      })
    } catch {
      // Игнорируем сетевые/серверные ошибки logout и завершаем локальную сессию.
    } finally {
      resetAuthState(true)
      error.value = null
    }
  }

  // Восстановление данных при инициализации (вызывается один раз благодаря _authInitialized)
  const initializeAuth = async () => {
    if (!process.client) return

    // Singleton guard: only initialize once across all useAuth() instances
    if (_authInitialized) return
    if (_authInitPromise) {
      await _authInitPromise
      return
    }

    _authInitPromise = (async () => {
      syncTokensFromStorage()

      const ensuredToken = await ensureFreshAccessToken()
      if (ensuredToken.token) {
        token.value = ensuredToken.token
        refreshToken.value = null
      } else if (ensuredToken.shouldLogout) {
        resetAuthState(false)
        return
      }

      // Если есть валидный токен, обновляем данные пользователя через /auth/me
      if (token.value && isTokenValid(token.value)) {
        await fetchCurrentUser()
      }

      _authInitialized = true
    })()

    await _authInitPromise
    _authInitPromise = null
  }

  // Выполняется при монтировании composable
  onMounted(() => {
    initializeAuth()
  })

  return {
    token: readonly(token),
    refreshToken: readonly(refreshToken),
    user: readonly(user),
    tenant: readonly(tenant),
    isLoading: readonly(isLoading),
    error: readonly(error),
    register,
    login,
    loginWithApiKey,
    refreshAccessToken,
    logout,
    fetchCurrentUser,
    isAuthenticated: computed(() => {
      if (process.client) {
        const currentStoredToken = getStoredAccessToken()
        if (currentStoredToken !== token.value) {
          token.value = currentStoredToken
        }
      }

      if (!token.value) return false
      // Проверяем валидность токена при каждом обращении
      if (!isTokenValid(token.value)) {
        // Токен истек - пробуем обновить через cookie refresh.
        if (process.client) {
          // Асинхронное обновление токена (не блокируем computed)
          refreshAccessToken().catch(() => {
            resetAuthState(false)
          })
          // Пока обновляем, считаем авторизованным.
          return true
        } else {
          resetAuthState(false)
          return false
        }
      }
      return true
    }),
    // Функции для работы с JWT
    decodeToken: (token: string | null) => token ? decodeJWT(token) : null,
    isTokenExpired: (token: string | null) => token ? isTokenExpired(token) : true,
    isTokenValid: (token: string | null) => isTokenValid(token)
  }
}