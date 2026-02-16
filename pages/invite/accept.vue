<template>
  <div class="min-h-screen flex items-center justify-center bg-slate-50 px-4 py-12">
    <div class="max-w-md w-full">
      <!-- Error State - Invalid/Expired Token -->
      <div v-if="tokenError" class="bg-white rounded-xl shadow-lg border border-red-200 p-8 text-center">
        <div class="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <AlertCircle class="h-8 w-8 text-red-600" />
        </div>
        <h1 class="text-2xl font-bold text-slate-900 mb-2">
          Недействительная ссылка
        </h1>
        <p class="text-slate-600 mb-6">
          {{ tokenError }}
        </p>
        <NuxtLink
          to="/login"
          class="inline-flex items-center px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
        >
          Вернуться на главную
        </NuxtLink>
      </div>

      <!-- Success State -->
      <div v-else-if="success" class="bg-white rounded-xl shadow-lg border border-green-200 p-8 text-center">
        <div class="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <CheckCircle class="h-8 w-8 text-green-600" />
        </div>
        <h1 class="text-2xl font-bold text-slate-900 mb-2">
          Добро пожаловать!
        </h1>
        <p class="text-slate-600 mb-6">
          Вы успешно присоединились к организации. Перенаправление...
        </p>
        <Loader2 class="h-6 w-6 text-indigo-600 animate-spin mx-auto" />
      </div>

      <!-- Registration Form -->
      <div v-else class="bg-white rounded-xl shadow-lg border border-slate-200 p-8">
        <div class="text-center mb-8">
          <h1 class="text-2xl font-bold text-slate-900 mb-2">
            Присоединиться к организации
          </h1>
          <p class="text-slate-600">
            Завершите регистрацию, чтобы получить доступ
          </p>
        </div>

        <form @submit.prevent="handleAccept" class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-slate-700 mb-2">
              Пароль
            </label>
            <div class="relative">
              <input
                v-model="form.password"
                :type="showPassword ? 'text' : 'password'"
                required
                minlength="8"
                maxlength="128"
                :class="[
                  'w-full px-3 py-2 pr-10 text-slate-900 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500',
                  validationErrors.password ? 'border-red-500' : 'border-slate-300'
                ]"
                placeholder="Минимум 8 символов"
              />
              <button
                type="button"
                @click="showPassword = !showPassword"
                class="absolute inset-y-0 right-0 pr-3 flex items-center"
              >
                <Eye v-if="showPassword" class="h-4 w-4 text-slate-400" />
                <EyeOff v-else class="h-4 w-4 text-slate-400" />
              </button>
            </div>
            <p v-if="validationErrors.password" class="mt-1 text-sm text-red-600">
              {{ validationErrors.password }}
            </p>
          </div>

          <div>
            <label class="block text-sm font-medium text-slate-700 mb-2">
              Подтверждение пароля
            </label>
            <div class="relative">
              <input
                v-model="form.passwordConfirmation"
                :type="showPasswordConfirmation ? 'text' : 'password'"
                required
                minlength="8"
                maxlength="128"
                :class="[
                  'w-full px-3 py-2 pr-10 text-slate-900 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500',
                  validationErrors.passwordConfirmation ? 'border-red-500' : 'border-slate-300'
                ]"
                placeholder="Повторите пароль"
              />
              <button
                type="button"
                @click="showPasswordConfirmation = !showPasswordConfirmation"
                class="absolute inset-y-0 right-0 pr-3 flex items-center"
              >
                <Eye v-if="showPasswordConfirmation" class="h-4 w-4 text-slate-400" />
                <EyeOff v-else class="h-4 w-4 text-slate-400" />
              </button>
            </div>
            <p v-if="validationErrors.passwordConfirmation" class="mt-1 text-sm text-red-600">
              {{ validationErrors.passwordConfirmation }}
            </p>
          </div>

          <div>
            <label class="block text-sm font-medium text-slate-700 mb-2">
              Имя (необязательно)
            </label>
            <input
              v-model="form.full_name"
              type="text"
              maxlength="255"
              class="w-full px-3 py-2 text-slate-900 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              placeholder="Ваше имя"
            />
          </div>

          <div v-if="error" class="bg-red-50 border border-red-200 rounded-lg p-3">
            <p class="text-sm text-red-800">{{ error }}</p>
          </div>

          <button
            type="submit"
            :disabled="isLoading"
            class="w-full px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
          >
            <Loader2 v-if="isLoading" class="h-4 w-4 animate-spin" />
            {{ isLoading ? 'Регистрация...' : 'Присоединиться' }}
          </button>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { AlertCircle, CheckCircle, Loader2, Eye, EyeOff } from 'lucide-vue-next'
import { useAuth, type AuthTokenResponse } from '../../composables/useAuth'
import { useApiFetch } from '../../composables/useApiFetch'
import { useToast } from '../../composables/useToast'
import { setStoredAccessToken } from '../../composables/authSessionManager'
import { getReadableErrorMessage } from '~/utils/api-errors'

// No auth middleware - this is a public page
definePageMeta({
  layout: false
})

const route = useRoute()
const router = useRouter()
const apiFetch = useApiFetch()
const { login } = useAuth()
const toast = useToast()

const token = computed(() => route.query.token as string | undefined)

const form = ref({
  password: '',
  passwordConfirmation: '',
  full_name: ''
})

const isLoading = ref(false)
const error = ref<string | null>(null)
const tokenError = ref<string | null>(null)
const success = ref(false)
const showPassword = ref(false)
const showPasswordConfirmation = ref(false)
const validationErrors = ref<Record<string, string>>({})

// Validate form
const validateForm = (): boolean => {
  validationErrors.value = {}

  if (form.value.password.length < 8) {
    validationErrors.value.password = 'Пароль должен содержать минимум 8 символов'
    return false
  }

  if (form.value.password !== form.value.passwordConfirmation) {
    validationErrors.value.passwordConfirmation = 'Пароли не совпадают'
    return false
  }

  return true
}

// Handle accept invitation
const handleAccept = async () => {
  if (!token.value) {
    tokenError.value = 'Отсутствует токен приглашения'
    return
  }

  if (!validateForm()) {
    return
  }

  isLoading.value = true
  error.value = null

  try {
    // Try /invitations/accept first, fallback to /auth/register-by-invite
    let response: AuthTokenResponse

    try {
      response = await apiFetch<AuthTokenResponse>('/invitations/accept', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: {
          token: token.value,
          password: form.value.password,
          full_name: form.value.full_name || undefined
        }
      })
    } catch (err: any) {
      // If /invitations/accept fails, try /auth/register-by-invite
      if (err?.status === 404 || err?.statusCode === 404) {
        response = await apiFetch<AuthTokenResponse>('/auth/register-by-invite', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: {
            token: token.value,
            password: form.value.password,
            full_name: form.value.full_name || undefined
          }
        })
      } else {
        throw err
      }
    }

    // Save auth data
    if (response.token) {
      if (process.client) {
        setStoredAccessToken(response.token)
      }

      // Update auth state
      await login({
        email: response.user?.email || '',
        password: form.value.password
      }).catch(() => {
        // Если повторный login не сработал, access token уже сохранен в памяти.
      })

      success.value = true
      toast.success('Добро пожаловать!', 'Вы успешно присоединились к организации')

      // Redirect to dashboard after a short delay
      setTimeout(() => {
        router.push('/dashboard')
      }, 2000)
    } else {
      throw new Error('Не получен токен авторизации')
    }
  } catch (err: any) {
    const status = err?.status || err?.statusCode || err?.response?.status

    if (status === 400 || status === 404 || status === 410) {
      tokenError.value = getReadableErrorMessage(err, 'Ссылка приглашения недействительна или истекла')
    } else {
      error.value = getReadableErrorMessage(err, 'Не удалось завершить регистрацию')
      toast.error('Ошибка', error.value)
    }
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  if (!token.value) {
    tokenError.value = 'Отсутствует токен приглашения в URL'
  }
})
</script>
