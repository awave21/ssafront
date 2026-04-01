/**
 * Раздел /settings (организация, команда, LLM-ключ и т.д.) — только settings:write.
 * Менеджер не видит пункт в меню и не должен открывать страницы по прямой ссылке.
 */
export default defineNuxtRouteMiddleware(async () => {
  const { fetchCurrentUser, user } = useAuth()
  await fetchCurrentUser()

  const { canManageApiKeys } = usePermissions()
  if (user.value && !canManageApiKeys.value) {
    return navigateTo('/dashboard')
  }
})
