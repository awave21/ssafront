<template>
  <div class="w-full px-5 py-5 flex flex-col gap-5">
          <!-- Permission Check -->
          <div v-if="!canManageMembers" class="bg-white rounded-xl border border-border p-8 text-center">
            <div class="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <AlertCircle class="h-8 w-8 text-red-600" />
            </div>
            <h3 class="text-lg font-semibold text-foreground mb-2">
              Недостаточно прав
            </h3>
            <p class="text-muted-foreground text-sm">
              У вас нет доступа к управлению участниками организации
            </p>
          </div>

          <!-- Content for authorized users -->
          <div v-else>

            <!-- Loading State -->
            <div v-if="isLoading" class="bg-white rounded-xl border border-border p-12 text-center">
              <Loader2 class="h-8 w-8 text-indigo-600 animate-spin mx-auto mb-4" />
              <p class="text-muted-foreground">Загрузка участников...</p>
            </div>

            <!-- Error State -->
            <div v-else-if="error" class="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
              <div class="flex items-center">
                <AlertCircle class="h-5 w-5 text-red-400 mr-3" />
                <div>
                  <h3 class="text-sm font-medium text-red-800">Ошибка загрузки</h3>
                  <p class="text-sm text-red-700 mt-1">{{ error }}</p>
                </div>
              </div>
            </div>

            <!-- Members Table -->
            <div v-else-if="members.length > 0" class="bg-white rounded-xl border border-border overflow-hidden">
              <div class="overflow-x-auto">
                <table class="w-full">
                  <thead class="bg-muted border-b border-border">
                    <tr>
                      <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                        Пользователь
                      </th>
                      <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                        Роль
                      </th>
                      <th class="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                        Дата входа
                      </th>
                      <th class="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">
                        Действия
                      </th>
                    </tr>
                  </thead>
                  <tbody class="bg-white divide-y divide-slate-200">
                    <tr v-for="member in members" :key="member.id" class="hover:bg-muted">
                      <td class="px-6 py-4 whitespace-nowrap">
                        <div class="flex items-center">
                          <div class="w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-full flex items-center justify-center shrink-0">
                            <span class="text-primary-foreground font-bold text-sm">
                              {{ member.full_name ? member.full_name.split(' ').map(n => n.charAt(0)).join('').toUpperCase() : member.email.charAt(0).toUpperCase() }}
                            </span>
                          </div>
                          <div class="ml-4">
                            <div class="text-sm font-medium text-foreground">
                              {{ member.full_name || 'Без имени' }}
                            </div>
                            <div class="text-sm text-slate-500">
                              {{ member.email }}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td class="px-6 py-4 whitespace-nowrap">
                        <div class="flex items-center gap-2">
                          <span
                            v-if="member.role === 'owner'"
                            class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800"
                          >
                            Владелец
                          </span>
                          <select
                            v-else
                            :value="member.role"
                            @change="updateRole(member.id, ($event.target as HTMLSelectElement).value)"
                            :disabled="updatingRoles.has(member.id)"
                            class="text-sm border border-slate-300 rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
                          >
                            <option value="admin">Администратор</option>
                            <option value="manager">Менеджер</option>
                          </select>
                          <Loader2
                            v-if="updatingRoles.has(member.id)"
                            class="h-4 w-4 text-indigo-600 animate-spin"
                          />
                        </div>
                      </td>
                      <td class="px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                        {{ formatDate(member.last_login_at) }}
                      </td>
                      <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <button
                          v-if="member.role !== 'owner' && member.id !== currentUserId"
                          @click="confirmDelete(member)"
                          :disabled="deletingUsers.has(member.id)"
                          class="text-red-600 hover:text-red-900 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          <Loader2
                            v-if="deletingUsers.has(member.id)"
                            class="h-4 w-4 animate-spin inline"
                          />
                          <span v-else>Удалить</span>
                        </button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <!-- Empty State for Members -->
            <div v-else class="bg-white rounded-xl border border-border p-12 text-center">
              <div class="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <Users class="h-8 w-8 text-slate-400" />
              </div>
              <h3 class="text-lg font-semibold text-foreground mb-2">
                Нет участников
              </h3>
              <p class="text-muted-foreground text-sm mb-4">
                Пригласите первого участника в организацию
              </p>
              <button
                @click="showInviteModal = true"
                class="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors"
              >
                <Plus class="h-4 w-4" />
                <span>Пригласить</span>
              </button>
            </div>

            <!-- Pending Invitations Section -->
            <div v-if="invitations.length > 0" class="mt-8">
              <h2 class="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
                <Mail class="h-5 w-5 text-slate-500" />
                Ожидающие приглашения
                <span class="text-sm font-normal text-slate-500">({{ invitations.length }})</span>
              </h2>
              <div class="bg-white rounded-xl border border-border overflow-hidden">
                <div class="divide-y divide-slate-200">
                  <div
                    v-for="invitation in invitations"
                    :key="invitation.id"
                    class="p-4 hover:bg-muted transition-colors"
                  >
                    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                      <div class="flex-1 min-w-0">
                        <div class="flex items-center gap-2 mb-1">
                          <span class="font-medium text-foreground truncate">{{ invitation.email }}</span>
                          <span
                            :class="[
                              'inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium',
                              isExpired(invitation.expires_at)
                                ? 'bg-red-100 text-red-800'
                                : 'bg-yellow-100 text-yellow-800'
                            ]"
                          >
                            {{ isExpired(invitation.expires_at) ? 'Истекло' : 'Ожидает' }}
                          </span>
                        </div>
                        <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-500">
                          <span>Роль: {{ getRoleLabel(invitation.role) }}</span>
                          <span class="flex items-center gap-1">
                            <Clock class="h-3.5 w-3.5" />
                            {{ isExpired(invitation.expires_at) ? 'Истекло' : 'До' }}: {{ formatDate(invitation.expires_at) }}
                          </span>
                        </div>
                      </div>
                      <div class="flex items-center gap-2 shrink-0">
                        <button
                          v-if="!isExpired(invitation.expires_at)"
                          @click="copyInviteLink(invitation)"
                          :disabled="copiedInviteId === invitation.id"
                          class="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm text-indigo-600 bg-indigo-50 rounded-lg hover:bg-indigo-100 disabled:opacity-50 transition-colors"
                        >
                          <Copy class="h-4 w-4" />
                          {{ copiedInviteId === invitation.id ? 'Скопировано' : 'Копировать' }}
                        </button>
                        <button
                          @click="deleteInvitation(invitation.id)"
                          :disabled="deletingInvitations.has(invitation.id)"
                          class="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm text-red-600 bg-red-50 rounded-lg hover:bg-red-100 disabled:opacity-50 transition-colors"
                        >
                          <Loader2
                            v-if="deletingInvitations.has(invitation.id)"
                            class="h-4 w-4 animate-spin"
                          />
                          <Trash2 v-else class="h-4 w-4" />
                          Удалить
                        </button>
                      </div>
                    </div>
                    <!-- Invite Link (collapsible or always visible) -->
                    <div v-if="!isExpired(invitation.expires_at)" class="mt-2">
                      <div class="flex items-center gap-2">
                        <input
                          :value="invitation.invite_link"
                          readonly
                          class="flex-1 px-3 py-1.5 text-xs text-muted-foreground bg-muted border border-border rounded-lg truncate"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Loading Invitations -->
            <div v-else-if="isLoadingInvitations" class="mt-8">
              <div class="flex items-center gap-2 text-slate-500">
                <Loader2 class="h-4 w-4 animate-spin" />
                <span class="text-sm">Загрузка приглашений...</span>
              </div>
      </div>
    </div>

    <!-- Invite Modal -->
    <InviteUserModal
      :is-open="showInviteModal"
      @close="showInviteModal = false"
      @invited="handleInvited"
    />

    <!-- Delete Confirmation Modal -->
    <div
      v-if="memberToDelete"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50"
      @click.self="memberToDelete = null"
    >
      <div class="bg-white rounded-xl shadow-xl max-w-md w-full mx-4">
        <div class="p-6">
          <h2 class="text-xl font-bold text-foreground mb-4">
            Подтверждение удаления
          </h2>
          <p class="text-muted-foreground mb-6">
            Вы уверены, что хотите удалить участника
            <strong>{{ memberToDelete.full_name || memberToDelete.email }}</strong>?
            Это действие нельзя отменить.
          </p>
          <div class="flex gap-3 justify-end">
            <button
              @click="memberToDelete = null"
              class="px-4 py-2 text-slate-700 bg-slate-100 rounded-lg hover:bg-slate-200 transition-colors"
            >
              Отмена
            </button>
            <button
              @click="deleteMember(memberToDelete.id)"
              :disabled="deletingUsers.has(memberToDelete.id)"
              class="px-4 py-2 bg-red-600 text-primary-foreground rounded-lg hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
            >
              <Loader2
                v-if="deletingUsers.has(memberToDelete.id)"
                class="h-4 w-4 animate-spin"
              />
              Удалить
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
// @ts-ignore - definePageMeta is auto-imported in Nuxt 3
definePageMeta({
  middleware: 'auth'
})

import { ref, onMounted, computed, watch } from 'vue'
import { AlertCircle, Plus, Loader2, Users, Copy, Trash2, Clock, Mail } from 'lucide-vue-next'
import { useAuth, type User } from '../../composables/useAuth'
import { usePermissions } from '../../composables/usePermissions'
import { useApiFetch } from '../../composables/useApiFetch'
import { useToast } from '../../composables/useToast'
import InviteUserModal from '../../components/settings/InviteUserModal.vue'
import { getReadableErrorMessage } from '~/utils/api-errors'

// Layout state
const { pageTitle } = useLayoutState()

// Types
type Invitation = {
  id: string
  email: string
  role: string
  expires_at: string
  invited_by_user_id: string
  created_at: string
  invite_link: string
  status?: 'pending' | 'accepted' | 'expired'
}

// State
const showInviteModal = ref(false)
const members = ref<User[]>([])
const invitations = ref<Invitation[]>([])
const isLoading = ref(false)
const isLoadingInvitations = ref(false)
const error = ref<string | null>(null)
const updatingRoles = ref<Set<string>>(new Set())
const deletingUsers = ref<Set<string>>(new Set())
const deletingInvitations = ref<Set<string>>(new Set())
const memberToDelete = ref<User | null>(null)
const copiedInviteId = ref<string | null>(null)

// Composables
const { user: currentUser, tenant } = useAuth()
const { canManageMembers } = usePermissions()
const apiFetch = useApiFetch()
const toast = useToast()
// @ts-ignore - Nuxt 3 auto-imports useRuntimeConfig
const { public: { siteUrl } } = useRuntimeConfig()

const currentUserId = computed(() => currentUser.value?.id ?? null)

// Helper to resolve invite link to correct domain
const resolveInviteLink = (rawLink: string): string => {
  if (!rawLink) return rawLink
  const baseUrl = (siteUrl && !siteUrl.includes('localhost')) ? siteUrl : (typeof window !== 'undefined' ? window.location.origin : '')
  try {
    const resolved = baseUrl ? new URL(rawLink, baseUrl) : new URL(rawLink)
    if (baseUrl) {
      const base = new URL(baseUrl)
      if (resolved.host !== base.host) {
        resolved.protocol = base.protocol
        resolved.host = base.host
      }
    }
    return resolved.toString()
  } catch {
    return rawLink
  }
}

// Check if invitation is expired
const isExpired = (expiresAt: string): boolean => {
  return new Date(expiresAt) < new Date()
}

// Format date helper
const formatDate = (date: string | null): string => {
  if (!date) return 'Никогда'
  try {
    return new Date(date).toLocaleDateString('ru-RU', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  } catch {
    return 'Неизвестно'
  }
}

// Fetch members
const fetchMembers = async () => {
  if (!canManageMembers.value) return

  isLoading.value = true
  error.value = null

  try {
    const response = await apiFetch<User[]>('/users', {
      method: 'GET'
    })
    members.value = response || []
  } catch (err: any) {
    const errorMessage = getReadableErrorMessage(err, 'Не удалось загрузить список участников')
    error.value = errorMessage
    toast.error('Ошибка', errorMessage)
  } finally {
    isLoading.value = false
  }
}

// Fetch invitations
const fetchInvitations = async () => {
  if (!canManageMembers.value) return

  isLoadingInvitations.value = true

  try {
    const response = await apiFetch<Invitation[]>('/invitations', {
      method: 'GET'
    })
    invitations.value = (response || []).map(inv => ({
      ...inv,
      invite_link: resolveInviteLink(inv.invite_link)
    }))
  } catch (err: any) {
    // Silently fail - invitations list is optional
    console.warn('Failed to fetch invitations:', err)
    invitations.value = []
  } finally {
    isLoadingInvitations.value = false
  }
}

// Copy invite link
const copyInviteLink = async (invitation: Invitation) => {
  try {
    await navigator.clipboard.writeText(invitation.invite_link)
    copiedInviteId.value = invitation.id
    toast.success('Скопировано', 'Ссылка скопирована в буфер обмена')
    setTimeout(() => {
      copiedInviteId.value = null
    }, 2000)
  } catch {
    toast.error('Ошибка', 'Не удалось скопировать ссылку')
  }
}

// Delete invitation
const deleteInvitation = async (invitationId: string) => {
  deletingInvitations.value.add(invitationId)

  try {
    await apiFetch(`/invitations/${invitationId}`, {
      method: 'DELETE'
    })
    invitations.value = invitations.value.filter(i => i.id !== invitationId)
    toast.success('Приглашение удалено', 'Приглашение успешно отменено')
  } catch (err: any) {
    toast.error('Ошибка', getReadableErrorMessage(err, 'Не удалось удалить приглашение'))
  } finally {
    deletingInvitations.value.delete(invitationId)
  }
}

// Update role
const updateRole = async (userId: string, newRole: string) => {
  if (newRole !== 'admin' && newRole !== 'manager') {
    toast.error('Ошибка', 'Некорректная роль')
    return
  }

  updatingRoles.value.add(userId)

  try {
    await apiFetch(`/users/${userId}/role`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json'
      },
      body: {
        role: newRole
      }
    })

    // Update local state
    const member = members.value.find(m => m.id === userId)
    if (member) {
      member.role = newRole
    }

    toast.success('Роль обновлена', `Роль участника успешно изменена на "${newRole === 'admin' ? 'Администратор' : 'Менеджер'}"`)
  } catch (err: any) {
    toast.error('Ошибка', getReadableErrorMessage(err, 'Не удалось обновить роль'))
  } finally {
    updatingRoles.value.delete(userId)
  }
}

// Confirm delete
const confirmDelete = (member: User) => {
  memberToDelete.value = member
}

// Delete member
const deleteMember = async (userId: string) => {
  deletingUsers.value.add(userId)

  try {
    await apiFetch(`/users/${userId}`, {
      method: 'DELETE'
    })

    // Remove from local state
    members.value = members.value.filter(m => m.id !== userId)
    memberToDelete.value = null

    toast.success('Участник удален', 'Участник успешно удален из организации')
  } catch (err: any) {
    toast.error('Ошибка', getReadableErrorMessage(err, 'Не удалось удалить участника'))
  } finally {
    deletingUsers.value.delete(userId)
  }
}

// Handle invited
const handleInvited = () => {
  showInviteModal.value = false
  // Refresh members and invitations list
  fetchMembers()
  fetchInvitations()
}

// Get role label
const getRoleLabel = (role: string): string => {
  const labels: Record<string, string> = {
    admin: 'Администратор',
    manager: 'Менеджер',
    owner: 'Владелец'
  }
  return labels[role] || role
}

// Track whether we've already started loading team data
const hasFetchedTeamData = ref(false)

const loadTeamData = () => {
  if (canManageMembers.value && !hasFetchedTeamData.value) {
    hasFetchedTeamData.value = true
    fetchMembers()
    fetchInvitations()
  }
}

onMounted(() => {
  pageTitle.value = 'Участники организации'
  loadTeamData()
})

// Watch for when auth loads asynchronously and canManageMembers becomes true
watch(canManageMembers, (newValue) => {
  if (newValue) {
    loadTeamData()
  }
})
</script>
