/**
 * Учётные данные (tenant credentials) — только agents:write, как в API /credentials.
 */
export default defineNuxtRouteMiddleware(async () => {
  const { fetchCurrentUser, user } = useAuth()
  await fetchCurrentUser()

  const { canEditAgents } = usePermissions()
  if (user.value && !canEditAgents.value) {
    return navigateTo('/dashboard')
  }
})
