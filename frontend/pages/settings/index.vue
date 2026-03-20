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

      <!-- Organization Balance -->
      <div class="bg-background rounded-xl border border-border p-6">
        <div class="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h3 class="text-lg font-semibold text-foreground mb-1">
              Баланс организации
            </h3>
            <p class="text-sm text-muted-foreground">
              Стартовый баланс отображается в рублях (курс: 1 USD = 101 RUB)
            </p>
          </div>
        </div>

        <div v-if="isBalanceLoading" class="mt-4 space-y-3">
          <Skeleton class="h-10 w-40 rounded-md" />
          <Skeleton class="h-24 w-full rounded-md" />
        </div>

        <div v-else-if="balanceError" class="mt-4 rounded-lg border border-red-200 bg-red-50 p-4">
          <p class="text-sm text-red-600">
            {{ balanceError }}
          </p>
          <button
            class="mt-3 inline-flex items-center justify-center gap-2 px-4 py-2 bg-background border border-border text-foreground rounded-lg hover:bg-muted transition-colors"
            @click="loadBalanceData"
          >
            Повторить
          </button>
        </div>

        <div v-else class="mt-4 flex flex-col gap-4">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div class="rounded-lg border border-border bg-muted/30 p-3">
              <p class="text-xs text-muted-foreground mb-1">Потрачено</p>
              <p class="text-lg font-semibold text-foreground">
                {{ formatRubAmountFromUsd(tenantBalance.spent_usd, 2, 2) }}
              </p>
            </div>
            <div class="rounded-lg border border-border bg-muted/30 p-3">
              <p class="text-xs text-muted-foreground mb-1">Остаток</p>
              <p class="text-lg font-semibold" :class="remainingUsdValue < 0 ? 'text-red-600' : 'text-foreground'">
                {{ formatRubAmountFromUsd(tenantBalance.remaining_usd, 2, 2) }}
              </p>
            </div>
          </div>

          <div class="flex flex-col sm:flex-row gap-3">
            <input
              v-model="initialBalanceInput"
              type="text"
              autocomplete="off"
              inputmode="decimal"
              placeholder="Введите стартовый баланс в RUB"
              class="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm focus:ring-2 focus:ring-ring focus:border-transparent outline-none transition-colors disabled:cursor-not-allowed disabled:opacity-60"
              :disabled="!canEditBalance || isBalanceSaving || !isAuthenticated"
            />
            <button
              v-if="canEditBalance"
              class="inline-flex items-center justify-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              :disabled="isSaveBalanceDisabled"
              @click="handleSaveBalance"
            >
              <Loader2 v-if="isBalanceSaving" class="h-4 w-4 animate-spin" />
              <span>{{ isBalanceSaving ? 'Сохранение...' : 'Сохранить' }}</span>
            </button>
          </div>

          <p v-if="balanceInputError" class="text-xs text-red-500">
            {{ balanceInputError }}
          </p>
          <p v-else-if="!canEditBalance" class="text-xs text-muted-foreground">
            У вас нет прав на изменение стартового баланса.
          </p>
        </div>
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
import { formatRubAmountFromUsd, rubInputToUsdFixed, usdToRubDisplayValue, useTenantBalance } from '../../composables/useTenantBalance'
import { useToast } from '../../composables/useToast'
import { getReadableErrorMessage } from '../../utils/api-errors'
import Skeleton from '~/components/ui/skeleton/Skeleton.vue'

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
const { canManageMembers, canManageApiKeys, canManageOrganization, isOwnerOrAdmin, hasScope } = usePermissions()
const showAuthModal = ref(false)
const apiFetch = useApiFetch()
const toast = useToast()
const updateTenantNameUri = '/tenant-settings/name'
const {
  balance: tenantBalance,
  error: balanceError,
  isLoading: isBalanceLoading,
  isSaving: isBalanceSaving,
  fetchBalance,
  updateInitialBalance,
  remainingUsdValue,
} = useTenantBalance()

const organizationName = ref('')
const isSavingOrganization = ref(false)
const organizationNameError = ref<string | null>(null)
const initialBalanceInput = ref('0')
const balanceInputError = ref<string | null>(null)

const trimmedOrganizationName = computed(() => organizationName.value.trim())
const currentOrganizationName = computed(() => tenant.value?.name?.trim() ?? '')
const isSaveOrganizationDisabled = computed(() =>
  !isAuthenticated.value
  || isSavingOrganization.value
  || trimmedOrganizationName.value.length < 2
  || trimmedOrganizationName.value.length > 200
  || trimmedOrganizationName.value === currentOrganizationName.value,
)
const canEditBalance = computed(() => isOwnerOrAdmin.value && hasScope('settings:write'))

const toNormalizedRubInput = (rawValue: string | number): string | null => {
  if (rawValue === null || rawValue === undefined) return null
  const value = String(rawValue).trim().replace(',', '.')
  if (value.length === 0) return null
  const parsed = Number.parseFloat(value)
  if (!Number.isFinite(parsed) || parsed < 0) return null
  return value
}

const normalizedInputBalance = computed(() => rubInputToUsdFixed(toNormalizedRubInput(initialBalanceInput.value) ?? ''))
const isBalanceChanged = computed(() => normalizedInputBalance.value !== tenantBalance.value.initial_balance_usd)
const isSaveBalanceDisabled = computed(() =>
  !isAuthenticated.value
  || !canEditBalance.value
  || isBalanceSaving.value
  || !normalizedInputBalance.value
  || !isBalanceChanged.value,
)

watch(
  () => tenant.value?.name,
  (value) => {
    organizationName.value = value ?? ''
  },
  { immediate: true },
)

watch(
  () => tenantBalance.value.initial_balance_usd,
  (value) => {
    initialBalanceInput.value = usdToRubDisplayValue(value)
  },
  { immediate: true },
)

// Set page title
onMounted(() => {
  pageTitle.value = 'Настройки'
  loadBalanceData()
})

// Auth handler
const handleAuthenticated = () => {
  showAuthModal.value = false
  loadBalanceData()
}

watch(isAuthenticated, (value) => {
  if (value) {
    loadBalanceData()
  }
})

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

const loadBalanceData = async () => {
  if (!isAuthenticated.value) return
  balanceInputError.value = null
  try {
    await fetchBalance()
  } catch {
    // Ошибка отображается внутри карточки.
  }
}

const handleSaveBalance = async () => {
  if (!canEditBalance.value || isBalanceSaving.value) return

  balanceInputError.value = null
  const normalizedValue = normalizedInputBalance.value

  if (!normalizedValue) {
    balanceInputError.value = 'Введите корректный баланс в рублях (число >= 0).'
    return
  }

  try {
    const updatedBalance = await updateInitialBalance(normalizedValue)
    initialBalanceInput.value = usdToRubDisplayValue(updatedBalance.initial_balance_usd)
    toast.success('Сохранено', 'Стартовый баланс обновлён')
  } catch (err: unknown) {
    const errorMessage = getReadableErrorMessage(err, 'Не удалось обновить стартовый баланс')
    balanceInputError.value = errorMessage
    toast.error('Ошибка', errorMessage)
  }
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
