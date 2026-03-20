type RefreshSuccess = {
  success: true
  token: string
}

type RefreshFailure = {
  success: false
  shouldLogout: boolean
  reason: string
}

export type RefreshResult = RefreshSuccess | RefreshFailure

export type EnsureAccessTokenResult = {
  token: string | null
  refreshed: boolean
  shouldLogout: boolean
}

const LEGACY_STORAGE_KEYS = [
  'auth_token',
  'auth_refresh_token',
  'auth_user',
  'auth_tenant',
  'auth_cookie_refresh_capability'
] as const

const EXPIRY_BUFFER_MS = 30_000
const PROACTIVE_REFRESH_WINDOW_MS = 3 * 60 * 1000
const ACTIVITY_WINDOW_MS = 15 * 60 * 1000
const CONFLICT_RETRY_MIN_DELAY_MS = 200
const CONFLICT_RETRY_MAX_DELAY_MS = 500
const CONFLICT_MAX_RETRIES = 3

const INVALID_REFRESH_ERRORS = new Set([
  'invalid_refresh_token',
  'refresh_token_expired',
  'refresh_token_revoked',
  'refresh_token_not_found'
])

let refreshPromise: Promise<RefreshResult> | null = null
let accessTokenMemory: string | null = null
let activityTrackingInitialized = false
let lastActivityAt = 0

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms))

const getRandomConflictDelay = () =>
  CONFLICT_RETRY_MIN_DELAY_MS +
  Math.floor(Math.random() * (CONFLICT_RETRY_MAX_DELAY_MS - CONFLICT_RETRY_MIN_DELAY_MS + 1))

const parseJwtPayload = (token: string): Record<string, unknown> | null => {
  try {
    const parts = token.split('.')
    if (parts.length !== 3) return null

    const payload = parts[1]
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/')
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=')
    const decoded = atob(padded)
    return JSON.parse(decoded) as Record<string, unknown>
  } catch {
    return null
  }
}

export const getTokenExpiryMs = (token: string): number | null => {
  const payload = parseJwtPayload(token)
  const exp = payload?.exp
  if (typeof exp !== 'number') return null
  return exp * 1000
}

export const isAccessTokenExpired = (token: string, bufferMs = EXPIRY_BUFFER_MS): boolean => {
  const expiryMs = getTokenExpiryMs(token)
  if (!expiryMs) return true
  return Date.now() >= expiryMs - bufferMs
}

export const getStoredAccessToken = (): string | null => accessTokenMemory

// В strict режиме refresh-токен хранится только в HttpOnly cookie.
export const getStoredRefreshToken = (): string | null => null

export const setStoredAccessToken = (token: string) => {
  accessTokenMemory = token
}

// Оставлено для совместимости интерфейса, но ничего не сохраняет.
export const setStoredRefreshToken = (_token: string) => {}

export const clearStoredAuthData = () => {
  accessTokenMemory = null
  if (!process.client) return
  for (const key of LEGACY_STORAGE_KEYS) {
    localStorage.removeItem(key)
  }
}

export const isCookieRefreshEnabled = (): boolean => true

const isInvalidRefreshResponse = (status: number, data: unknown): boolean => {
  if (status === 401 || status === 403) return true
  if (!data || typeof data !== 'object') return false
  const error = (data as { error?: unknown }).error
  return typeof error === 'string' && INVALID_REFRESH_ERRORS.has(error)
}

const getRefreshFailureReason = (status: number, data: unknown): string => {
  if (data && typeof data === 'object') {
    const error = (data as { error?: unknown }).error
    if (typeof error === 'string' && error.length > 0) {
      return error
    }
  }
  return `http_${status}`
}

const parseRefreshResponseBody = async (response: Response): Promise<unknown> => {
  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    return response.json().catch(() => null)
  }

  const text = await response.text().catch(() => '')
  if (!text) return null

  try {
    return JSON.parse(text)
  } catch {
    return { message: text }
  }
}

const trackActivity = () => {
  lastActivityAt = Date.now()
}

export const initAuthActivityTracking = () => {
  if (!process.client || activityTrackingInitialized) return

  activityTrackingInitialized = true
  lastActivityAt = Date.now()

  const events: Array<keyof WindowEventMap> = [
    'click',
    'keydown',
    'mousemove',
    'scroll',
    'touchstart',
    'focus'
  ]

  for (const eventName of events) {
    window.addEventListener(eventName, trackActivity, { passive: true })
  }

  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      trackActivity()
    }
  })
}

export const isUserSessionActive = () => {
  if (!process.client) return false
  if (document.visibilityState !== 'visible') return false
  return Date.now() - lastActivityAt <= ACTIVITY_WINDOW_MS
}

export const shouldRefreshProactively = (
  token: string,
  thresholdMs = PROACTIVE_REFRESH_WINDOW_MS
) => {
  const expiryMs = getTokenExpiryMs(token)
  if (!expiryMs) return true
  return expiryMs - Date.now() <= thresholdMs
}

const performRefresh = async (): Promise<RefreshResult> => {
  // @ts-ignore Nuxt auto-import
  const { public: { apiBase } } = useRuntimeConfig()

  for (let attempt = 0; attempt <= CONFLICT_MAX_RETRIES; attempt++) {
    try {
      const response = await fetch(`${apiBase}/auth/refresh`, {
        method: 'POST',
        credentials: 'include'
      })

      const responseBody = await parseRefreshResponseBody(response)

      if (response.status === 409) {
        if (attempt < CONFLICT_MAX_RETRIES) {
          await sleep(getRandomConflictDelay())
          continue
        }

        return {
          success: false,
          shouldLogout: false,
          reason: 'refresh_token_in_use'
        }
      }

      if (!response.ok) {
        return {
          success: false,
          shouldLogout: isInvalidRefreshResponse(response.status, responseBody),
          reason: getRefreshFailureReason(response.status, responseBody)
        }
      }

      if (
        !responseBody ||
        typeof responseBody !== 'object' ||
        typeof (responseBody as { token?: unknown }).token !== 'string'
      ) {
        return {
          success: false,
          shouldLogout: false,
          reason: 'invalid_refresh_response'
        }
      }

      const newAccessToken = (responseBody as { token: string }).token
      setStoredAccessToken(newAccessToken)

      return {
        success: true,
        token: newAccessToken
      }
    } catch {
      return {
        success: false,
        shouldLogout: false,
        reason: 'refresh_network_error'
      }
    }
  }

  return {
    success: false,
    shouldLogout: false,
    reason: 'refresh_failed'
  }
}

export const refreshAuthSession = async (): Promise<RefreshResult> => {
  if (!process.client) {
    return {
      success: false,
      shouldLogout: false,
      reason: 'server_context'
    }
  }

  if (refreshPromise) {
    return refreshPromise
  }

  const promise = performRefresh()
  refreshPromise = promise

  try {
    return await promise
  } finally {
    if (refreshPromise === promise) {
      refreshPromise = null
    }
  }
}

export const ensureFreshAccessToken = async (options?: {
  forceRefresh?: boolean
  proactiveWindowMs?: number
}): Promise<EnsureAccessTokenResult> => {
  if (!process.client) {
    return { token: null, refreshed: false, shouldLogout: false }
  }

  initAuthActivityTracking()

  const currentAccessToken = getStoredAccessToken()
  const forceRefresh = options?.forceRefresh === true
  const proactiveWindowMs = options?.proactiveWindowMs ?? PROACTIVE_REFRESH_WINDOW_MS

  const shouldRefresh =
    forceRefresh ||
    !currentAccessToken ||
    isAccessTokenExpired(currentAccessToken) ||
    (shouldRefreshProactively(currentAccessToken, proactiveWindowMs) && isUserSessionActive())

  if (!shouldRefresh && currentAccessToken) {
    return {
      token: currentAccessToken,
      refreshed: false,
      shouldLogout: false
    }
  }

  const refreshResult = await refreshAuthSession()
  if (refreshResult.success) {
    return {
      token: refreshResult.token,
      refreshed: true,
      shouldLogout: false
    }
  }

  const fallbackToken = getStoredAccessToken()
  if (fallbackToken && !isAccessTokenExpired(fallbackToken)) {
    return {
      token: fallbackToken,
      refreshed: false,
      shouldLogout: false
    }
  }

  return {
    token: null,
    refreshed: false,
    shouldLogout: refreshResult.shouldLogout
  }
}
