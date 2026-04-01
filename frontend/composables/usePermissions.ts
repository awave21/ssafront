import { computed } from 'vue'
import { useAuth } from './useAuth'

// Матрица прав по ролям (fallback если бэкенд не вернул scopes)
const ROLE_PERMISSIONS = {
  owner: [
    'agents:read',
    'agents:write',
    'billing:write',
    'members:manage',
    'dialogs:read',
    'dialogs:write',
    'dialogs:delete',
    'analytics:view',
    'organization:manage',
    'settings:read',
    'settings:write'
  ],
  admin: [
    'agents:read',
    'agents:write',
    'members:manage',
    'dialogs:read',
    'dialogs:write',
    'dialogs:delete',
    'analytics:view',
    'organization:manage',
    'settings:read',
    'settings:write'
  ],
  manager: [
    'agents:read',
    'dialogs:read',
    'dialogs:write',
    'analytics:view',
  ]
} as const

export const usePermissions = () => {
  const { user, tenant } = useAuth()

  // Текущая роль пользователя
  const role = computed(() => user.value?.role ?? null)

  // Проверка роли
  const isOwner = computed(() => role.value === 'owner')
  const isAdmin = computed(() => role.value === 'admin')
  const isManager = computed(() => role.value === 'manager')
  const isOwnerOrAdmin = computed(() => isOwner.value || isAdmin.value)

  // Получение прав для текущей роли
  const rolePermissions = computed(() => {
    if (!role.value) return []
    return ROLE_PERMISSIONS[role.value as keyof typeof ROLE_PERMISSIONS] ?? []
  })

  // Проверка наличия scope (приоритет: scopes из бэкенда, затем fallback по роли)
  const hasScope = (scope: string): boolean => {
    if (!user.value) return false
    
    // Если бэкенд вернул scopes — используем их (основной источник)
    if (user.value.scopes && user.value.scopes.length > 0) {
      return user.value.scopes.includes(scope)
    }
    
    // Fallback: права по роли (если бэкенд не вернул scopes)
    return (rolePermissions.value as readonly string[]).includes(scope)
  }

  // Проверка наличия хотя бы одного scope из списка
  const hasAnyScope = (scopes: string[]): boolean => {
    return scopes.some(scope => hasScope(scope))
  }

  // Проверка наличия всех scopes из списка
  const hasAllScopes = (scopes: string[]): boolean => {
    return scopes.every(scope => hasScope(scope))
  }

  // Готовые флаги прав (по спецификации)
  const canViewAgentsList = computed(() => hasScope('agents:read'))
  const canEditAgents = computed(() => hasScope('agents:write'))
  const canManageMembers = computed(() => hasScope('members:manage'))
  const canViewAnalytics = computed(() => hasScope('analytics:view'))
  const canDeleteDialogs = computed(() => hasScope('dialogs:delete'))
  const canManageOrganization = computed(() => hasScope('organization:manage'))
  const canReadSettings = computed(() => hasScope('settings:read'))
  const canManageApiKeys = computed(() => hasScope('settings:write'))
  /** Только владелец организации (tenant.owner_user_id); при отсутствии поля — роль owner. */
  const canManageTenantBalance = computed(() => {
    const u = user.value
    if (!u) return false
    const ownerId = tenant.value?.owner_user_id
    if (ownerId != null && ownerId !== '') {
      return u.id === ownerId
    }
    return u.role === 'owner'
  })

  return {
    // Роли
    role,
    isOwner,
    isAdmin,
    isManager,
    isOwnerOrAdmin,
    
    // Проверка scopes
    hasScope,
    hasAnyScope,
    hasAllScopes,
    
    // Готовые флаги прав
    canViewAgentsList,
    canEditAgents,
    canManageMembers,
    canViewAnalytics,
    canDeleteDialogs,
    canManageOrganization,
    canReadSettings,
    canManageApiKeys,
    canManageTenantBalance,
    
    // Для отладки
    rolePermissions
  }
}
