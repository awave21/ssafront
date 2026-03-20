import {
  clearStoredAuthData,
  ensureFreshAccessToken,
  getStoredAccessToken,
  isAccessTokenExpired
} from '../composables/authSessionManager'

export default defineNuxtRouteMiddleware(async (to) => {
  const publicPaths = new Set(['/login', '/'])
  const publicPrefixes = ['/invite/accept']
  const isPublicRoute =
    publicPaths.has(to.path) ||
    publicPrefixes.some((prefix) => to.path.startsWith(prefix))

  if (isPublicRoute) {
    return
  }

  // Проверяем токен только на клиентской стороне
  if (process.client) {
    const accessToken = getStoredAccessToken()

    if (accessToken && !isAccessTokenExpired(accessToken)) {
      return
    }

    const ensuredToken = await ensureFreshAccessToken({ forceRefresh: true })
    if (ensuredToken.token) {
      return
    }

    // Для защищенных страниц работаем в fail-closed режиме:
    // если валидный токен не получен, показываем только /login.
    clearStoredAuthData()
    return navigateTo('/login')
  }
})
