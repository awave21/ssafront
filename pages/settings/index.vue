<template>
  <div class="w-full px-5 py-5 flex flex-col gap-5">
    <!-- Auth Status Banner -->
    <div v-if="!isAuthenticated" class="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <div class="flex items-center justify-between">
              <div class="flex items-center">
                <AlertCircle class="h-5 w-5 text-yellow-400 mr-3" />
                <div>
                  <h3 class="text-sm font-medium text-yellow-800">
                    Требуется аутентификация
                  </h3>
                  <p class="text-sm text-yellow-700 mt-1">
                    Зарегистрируйтесь или войдите в систему для доступа к настройкам
                  </p>
                </div>
              </div>
              <div class="flex gap-2">
                <button
                  @click="showAuthModal = true"
                  class="px-4 py-2 bg-yellow-600 text-white text-sm font-medium rounded-lg hover:bg-yellow-700 transition-colors"
                >
                  Войти
                </button>
              </div>
            </div>
          </div>


    <!-- Settings Sections -->
    <div class="flex flex-col gap-4">
      <!-- Organization Name -->
      <div
        v-if="canManageOrganization"
        class="bg-background rounded-xl border border-border p-6"
      >
        <div class="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h3 class="text-lg font-semibold text-foreground mb-1">
              Название организации
            </h3>
            <p class="text-sm text-muted-foreground">
              Это имя отображается в боковом меню и настройках команды
            </p>
          </div>
        </div>

        <div class="mt-4 flex flex-col sm:flex-row gap-3">
          <input
            v-model="organizationName"
            type="text"
            placeholder="Введите название организации"
            class="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm focus:ring-2 focus:ring-ring focus:border-transparent outline-none transition-colors"
            :disabled="isSavingOrganization || !isAuthenticated"
            maxlength="200"
          />
          <button
            class="inline-flex items-center justify-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            :disabled="isSaveOrganizationDisabled"
            @click="handleSaveOrganizationName"
          >
            <Loader2 v-if="isSavingOrganization" class="h-4 w-4 animate-spin" />
            <span>{{ isSavingOrganization ? 'Сохранение...' : 'Сохранить' }}</span>
          </button>
        </div>
        <p v-if="organizationNameError" class="mt-2 text-xs text-red-500">
          {{ organizationNameError }}
        </p>
      </div>

      <!-- Team Management Section -->
      <NuxtLink
        v-if="canManageMembers"
        to="/settings/team"
        class="block bg-background rounded-xl border border-border p-6 hover:border-primary/50 hover:shadow-md transition-all"
      >
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-4">
            <div class="w-12 h-12 bg-primary/10 rounded-lg flex items-center justify-center">
              <Users class="h-6 w-6 text-primary" />
            </div>
            <div>
              <h3 class="text-lg font-semibold text-foreground mb-1">
                Участники организации
              </h3>
              <p class="text-sm text-muted-foreground">
                Управление участниками и их ролями
              </p>
            </div>
          </div>
          <svg class="h-5 w-5 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
          </svg>
        </div>
      </NuxtLink>

      <!-- LLM Key Settings -->
      <NuxtLink
        v-if="canManageApiKeys"
        to="/settings/llm-key"
        class="block bg-background rounded-xl border border-border p-6 hover:border-primary/50 hover:shadow-md transition-all"
      >
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-4">
            <div class="w-12 h-12 bg-primary/10 rounded-lg flex items-center justify-center">
              <KeyRound class="h-6 w-6 text-primary" />
            </div>
            <div>
              <h3 class="text-lg font-semibold text-foreground mb-1">
                API-ключ OpenAI
              </h3>
              <p class="text-sm text-muted-foreground">
                Собственный ключ для генерации ответов агентами
              </p>
            </div>
          </div>
          <svg class="h-5 w-5 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
          </svg>
        </div>
      </NuxtLink>
    </div>

    <!-- Auth Modal -->
    <AuthModal
      :is-open="showAuthModal"
      @close="showAuthModal = false"
      @authenticated="handleAuthenticated"
    />
  </div>
</template>

<script setup lang="ts">
// @ts-ignore - definePageMeta is auto-imported in Nuxt 3
definePageMeta({
  middleware: 'auth'
})

import { ref, computed, onMounted, watch } from 'vue'
import { AlertCircle, Users, KeyRound, Loader2 } from 'lucide-vue-next'
import { useAuth } from '../../composables/useAuth'
import { usePermissions } from '../../composables/usePermissions'
import { useApiFetch } from '../../composables/useApiFetch'
import { useToast } from '../../composables/useToast'
import { getReadableErrorMessage } from '../../utils/api-errors'

type UpdateTenantNameRequest = {
  name: string
}

type TenantRead = {
  id: string
  name: string
  plan: string
  is_active: boolean
  owner_user_id: string | null
  created_at: string
  updated_at: string | null
}

type ApiDetailObject = {
  error?: string
  message?: string
}

type ValidationErrorDetail = {
  loc?: unknown
  msg?: string
  type?: string
}

// Layout state
const { pageTitle } = useLayoutState()

// Auth state
const { isAuthenticated, tenant, fetchCurrentUser } = useAuth()
const { canManageMembers, canManageApiKeys, canManageOrganization } = usePermissions()
const showAuthModal = ref(false)
const apiFetch = useApiFetch()
const toast = useToast()
const updateTenantNameUri = '/tenant-settings/name'

const organizationName = ref('')
const isSavingOrganization = ref(false)
const organizationNameError = ref<string | null>(null)

const trimmedOrganizationName = computed(() => organizationName.value.trim())
const currentOrganizationName = computed(() => tenant.value?.name?.trim() ?? '')
const isSaveOrganizationDisabled = computed(() =>
  !isAuthenticated.value
  || isSavingOrganization.value
  || trimmedOrganizationName.value.length < 2
  || trimmedOrganizationName.value.length > 200
  || trimmedOrganizationName.value === currentOrganizationName.value,
)

watch(
  () => tenant.value?.name,
  (value) => {
    organizationName.value = value ?? ''
  },
  { immediate: true },
)

// Set page title
onMounted(() => {
  pageTitle.value = 'Настройки'
})

// Auth handler
const handleAuthenticated = () => {
  showAuthModal.value = false
}

const getHttpStatus = (err: unknown): number | null => {
  if (!err || typeof err !== 'object') return null
  const candidate = err as {
    status?: unknown
    statusCode?: unknown
    response?: { status?: unknown; statusCode?: unknown }
  }
  const status = candidate.status ?? candidate.statusCode ?? candidate.response?.status ?? candidate.response?.statusCode
  return typeof status === 'number' ? status : null
}

const getApiDetail = (err: unknown): unknown => {
  if (!err || typeof err !== 'object') return null
  const candidate = err as {
    data?: unknown
    response?: { _data?: unknown; data?: unknown }
  }
  const data = candidate.data ?? candidate.response?._data ?? candidate.response?.data
  if (!data || typeof data !== 'object') return null
  return (data as { detail?: unknown }).detail ?? null
}

const getUpdateOrganizationErrorMessage = (err: unknown): string => {
  const status = getHttpStatus(err)
  const detail = getApiDetail(err)

  if (status === 401) {
    const errorCode = detail && typeof detail === 'object'
      ? (detail as ApiDetailObject).error
      : null
    if (errorCode === 'not_authenticated' || errorCode === 'invalid_token') {
      return 'Сессия истекла. Войдите снова, чтобы сохранить изменения.'
    }
    return 'Требуется авторизация для изменения названия организации.'
  }

  if (status === 403) {
    const errorCode = detail && typeof detail === 'object'
      ? (detail as ApiDetailObject).error
      : null
    if (errorCode === 'missing_scope') {
      return 'Недостаточно прав для изменения названия организации.'
    }
    return 'Доступ к изменению названия организации запрещён.'
  }

  if (status === 404) {
    if (typeof detail === 'string' && detail === 'Tenant not found') {
      return 'Организация не найдена.'
    }
    return 'Эндпоинт обновления названия организации не найден.'
  }

  if (status === 422) {
    if (typeof detail === 'string' && detail.length > 0) {
      return detail
    }

    if (Array.isArray(detail)) {
      const nameValidationError = detail.find((item): item is ValidationErrorDetail => {
        if (!item || typeof item !== 'object') return false
        const loc = (item as ValidationErrorDetail).loc
        return Array.isArray(loc) && loc.includes('name')
      })

      if (nameValidationError?.msg) return nameValidationError.msg
    }

    return 'Ошибка валидации названия организации.'
  }

  return getReadableErrorMessage(err, 'Не удалось обновить название организации')
}

const updateOrganizationName = async (name: string) => {
  const payload: UpdateTenantNameRequest = { name }
  return apiFetch<TenantRead>(updateTenantNameUri, {
    method: 'PATCH',
    body: payload,
  })
}

const handleSaveOrganizationName = async () => {
  organizationNameError.value = null
  const newName = trimmedOrganizationName.value

  if (newName.length < 2) {
    organizationNameError.value = 'Название должно содержать минимум 2 символа'
    return
  }

  if (newName.length > 200) {
    organizationNameError.value = 'Название должно содержать не более 200 символов'
    return
  }

  isSavingOrganization.value = true

  try {
    await updateOrganizationName(newName)
    await fetchCurrentUser()
    toast.success('Сохранено', 'Название организации обновлено')
  } catch (err: unknown) {
    const errorMessage = getUpdateOrganizationErrorMessage(err)
    organizationNameError.value = errorMessage
    toast.error('Ошибка', errorMessage)
  } finally {
    isSavingOrganization.value = false
  }
}
</script>
