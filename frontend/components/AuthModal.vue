<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity duration-300"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-opacity duration-300"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="isOpen"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50"
        @click="handleOverlayClick"
      >
        <Transition
          enter-active-class="transition-all duration-300"
          enter-from-class="opacity-0 scale-95 translate-y-4"
          enter-to-class="opacity-100 scale-100 translate-y-0"
          leave-active-class="transition-all duration-300"
          leave-from-class="opacity-100 scale-100 translate-y-0"
          leave-to-class="opacity-0 scale-95 translate-y-4"
        >
          <div
            v-if="isOpen"
            class="bg-white rounded-xl shadow-xl max-w-md w-full mx-4"
            @click.stop
          >
            <div class="p-6">
              <div class="flex items-center justify-between mb-6">
                <h2 class="text-xl font-bold text-slate-900">
                  Вход в систему
                </h2>
                <button
                  v-if="!props.disableClose"
                  @click="requestClose"
                  class="p-2 text-slate-400 hover:text-slate-600 transition-colors"
                >
                  <X class="h-5 w-5" />
                </button>
              </div>

              <!-- Табы для разных способов входа -->
              <div class="flex mb-6 bg-slate-100 rounded-lg p-1">
                <button
                  @click="authMethod = 'login'"
                  :class="[
                    'flex-1 py-2 px-3 text-sm font-medium rounded-md transition-colors',
                    authMethod === 'login'
                      ? 'bg-white text-slate-900 shadow-sm'
                      : 'text-slate-600 hover:text-slate-900'
                  ]"
                >
                  Вход
                </button>
                <button
                  @click="authMethod = 'register'"
                  :class="[
                    'flex-1 py-2 px-3 text-sm font-medium rounded-md transition-colors',
                    authMethod === 'register'
                      ? 'bg-white text-slate-900 shadow-sm'
                      : 'text-slate-600 hover:text-slate-900'
                  ]"
                >
                  Регистрация
                </button>
              </div>

              <!-- Форма регистрации -->
              <form v-if="authMethod === 'register'" @submit.prevent="handleRegister" class="space-y-4">
                <div>
                  <label class="block text-sm font-medium text-slate-700 mb-2">
                    Email *
                  </label>
                  <input
                    v-model="registerForm.email"
                    type="email"
                    required
                    :class="[
                      'w-full px-3 py-2 text-slate-900 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500',
                      validationErrors.email ? 'border-red-500' : 'border-slate-300'
                    ]"
                    placeholder="user@example.com"
                  />
                  <div v-if="validationErrors.email" class="mt-1 text-sm text-red-600">
                    {{ validationErrors.email.join(', ') }}
                  </div>
                </div>

                <div>
                  <label class="block text-sm font-medium text-slate-700 mb-2">
                    Пароль *
                  </label>
                  <div class="relative">
                    <input
                      v-model="registerForm.password"
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
                </div>

                <div>
                  <label class="block text-sm font-medium text-slate-700 mb-2">
                    Подтвердить пароль *
                  </label>
                  <div class="relative">
                    <input
                      v-model="registerForm.confirmPassword"
                      :type="showConfirmPassword ? 'text' : 'password'"
                      required
                      minlength="8"
                      maxlength="128"
                      class="w-full px-3 py-2 pr-10 text-slate-900 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                      placeholder="Повторите пароль"
                    />
                    <button
                      type="button"
                      @click="showConfirmPassword = !showConfirmPassword"
                      class="absolute inset-y-0 right-0 pr-3 flex items-center"
                    >
                      <Eye v-if="showConfirmPassword" class="h-4 w-4 text-slate-400" />
                      <EyeOff v-else class="h-4 w-4 text-slate-400" />
                    </button>
                  </div>
                  <div v-if="registerForm.password && registerForm.confirmPassword && registerForm.password !== registerForm.confirmPassword" class="mt-1 text-sm text-red-600">
                    Пароли не совпадают
                  </div>
                  <div v-if="validationErrors.confirmPassword" class="mt-1 text-sm text-red-600">
                    {{ validationErrors.confirmPassword.join(', ') }}
                  </div>
                </div>

                <div>
                  <label class="block text-sm font-medium text-slate-700 mb-2">
                    Полное имя
                  </label>
                  <input
                    v-model="registerForm.full_name"
                    type="text"
                    maxlength="200"
                    class="w-full px-3 py-2 text-slate-900 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    placeholder="Иван Иванов"
                  />
                </div>

                <div>
                  <label class="block text-sm font-medium text-slate-700 mb-2">
                    Название организации
                  </label>
                  <input
                    v-model="registerForm.tenant_name"
                    type="text"
                    maxlength="200"
                    class="w-full px-3 py-2 text-slate-900 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    placeholder="Моя Компания"
                  />
                  <p class="text-xs text-slate-500 mt-1">
                    Если не указано, будет сгенерировано автоматически
                  </p>
                </div>

                <button
                  type="submit"
                  :disabled="isLoading"
                  class="w-full px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
                >
                  <Loader2 v-if="isLoading" class="h-4 w-4 animate-spin" />
                  {{ isLoading ? 'Регистрация...' : 'Зарегистрироваться' }}
                </button>
              </form>

              <!-- Форма входа пользователя -->
              <form v-if="authMethod === 'login'" @submit.prevent="handleUserLogin" class="space-y-4">
                <div>
                  <label class="block text-sm font-medium text-slate-700 mb-2">
                    Email
                  </label>
                  <input
                    v-model="loginForm.email"
                    type="email"
                    required
                    :class="[
                      'w-full px-3 py-2 text-slate-900 border rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500',
                      validationErrors.email ? 'border-red-500' : 'border-slate-300'
                    ]"
                    placeholder="Введите ваш email"
                  />
                  <div v-if="validationErrors.email" class="mt-1 text-sm text-red-600">
                    {{ validationErrors.email.join(', ') }}
                  </div>
                </div>

                <div>
                  <label class="block text-sm font-medium text-slate-700 mb-2">
                    Пароль
                  </label>
                  <div class="relative">
                    <input
                      v-model="loginForm.password"
                      :type="showLoginPassword ? 'text' : 'password'"
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
                      @click="showLoginPassword = !showLoginPassword"
                      class="absolute inset-y-0 right-0 pr-3 flex items-center"
                    >
                      <Eye v-if="showLoginPassword" class="h-4 w-4 text-slate-400" />
                      <EyeOff v-else class="h-4 w-4 text-slate-400" />
                    </button>
                  </div>
                </div>

                <button
                  type="submit"
                  :disabled="isLoading"
                  class="w-full px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
                >
                  <Loader2 v-if="isLoading" class="h-4 w-4 animate-spin" />
                  {{ isLoading ? 'Вход...' : 'Войти' }}
                </button>
              </form>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { X, Loader2, Eye, EyeOff } from 'lucide-vue-next'
import { useAuth, type ApiError } from '../composables/useAuth'
import { useToast } from '../composables/useToast'

interface Props {
  isOpen: boolean
  disableClose?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  disableClose: false
})
const emit = defineEmits<{
  close: []
  authenticated: []
}>()

const { register, login, isLoading, error } = useAuth()
const { error: showError, success: showSuccess } = useToast()

// Ошибки валидации для отображения в формах
const validationErrors = ref<Record<string, string[]>>({})

// Метод аутентификации
const authMethod = ref<'register' | 'login'>('login')
const loginForm = ref({
  email: '',
  password: ''
})
const registerForm = ref({
  email: '',
  password: '',
  confirmPassword: '',
  full_name: '',
  tenant_name: ''
})

// Password visibility states
const showPassword = ref(false)
const showConfirmPassword = ref(false)
const showLoginPassword = ref(false)

const requestClose = () => {
  if (props.disableClose) {
    return
  }
  emit('close')
}

const handleOverlayClick = () => {
  requestClose()
}


// Обработчик регистрации
const handleRegister = async () => {
  // Очищаем предыдущие ошибки
  validationErrors.value = {}
  
  // Проверяем, что пароли совпадают
  if (registerForm.value.password !== registerForm.value.confirmPassword) {
    showError('Ошибка валидации', 'Пароли не совпадают')
    validationErrors.value.confirmPassword = ['Пароли не совпадают']
    return
  }

  try {
    await register(registerForm.value)
    showSuccess('Успешно', 'Вы успешно зарегистрированы')
    emit('authenticated')
    emit('close')
  } catch (err: any) {
    const apiError: ApiError = err.apiError || {
      error: 'unknown_error',
      message: err.message || 'Ошибка регистрации'
    }
    
    // Если есть детали валидации, показываем их под полями
    if (apiError.details) {
      validationErrors.value = apiError.details
      // Показываем toast с общей ошибкой
      showError('Ошибка регистрации', apiError.message)
      } else {
        // Показываем toast с ошибкой
        if (apiError.error === 'email_exists') {
          showError('Ошибка регистрации', 'Пользователь с таким email уже существует')
        } else if (apiError.error === 'rate_limit_exceeded') {
          const retryAfter = apiError.retry_after || 60
          showError(
            'Превышен лимит запросов',
            `Попробуйте снова через ${retryAfter} секунд`
          )
        } else if (apiError.error === 'bad_gateway' || apiError.error === 'service_unavailable' || apiError.error === 'gateway_timeout') {
          showError('Сервер недоступен', apiError.message)
        } else if (apiError.error === 'network_error') {
          showError('Ошибка сети', apiError.message)
        } else {
          showError('Ошибка регистрации', apiError.message)
        }
      }
  }
}

// Обработчик входа пользователя
const handleUserLogin = async () => {
  // Очищаем предыдущие ошибки
  validationErrors.value = {}
  
  // Валидация на frontend
  if (!loginForm.value.email || !loginForm.value.password) {
    showError('Ошибка валидации', 'Пожалуйста, заполните все поля')
    return
  }

  if (loginForm.value.password.length < 8) {
    showError('Ошибка валидации', 'Пароль должен содержать минимум 8 символов')
    validationErrors.value.password = ['Пароль должен содержать минимум 8 символов']
    return
  }

  // Простая валидация email
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  if (!emailRegex.test(loginForm.value.email)) {
    showError('Ошибка валидации', 'Пожалуйста, введите корректный email адрес')
    validationErrors.value.email = ['Некорректный формат email']
    return
  }

  try {
    await login({
      email: loginForm.value.email,
      password: loginForm.value.password
    })
    showSuccess('Успешно', 'Вы успешно вошли в систему')
    emit('authenticated')
    emit('close')
  } catch (err: any) {
    const apiError: ApiError = err.apiError || {
      error: 'unknown_error',
      message: err.message || 'Ошибка входа'
    }
    
    // Если есть детали валидации, показываем их под полями
    if (apiError.details) {
      validationErrors.value = apiError.details
      showError('Ошибка входа', apiError.message)
      } else {
        // Показываем toast с ошибкой
        if (apiError.error === 'invalid_credentials') {
          showError('Ошибка входа', 'Неверный логин или пароль')
        } else if (apiError.error === 'account_inactive') {
          showError('Ошибка входа', 'Аккаунт неактивен')
        } else if (apiError.error === 'rate_limit_exceeded') {
          const retryAfter = apiError.retry_after || 60
          showError(
            'Превышен лимит запросов',
            `Слишком много попыток входа. Попробуйте снова через ${retryAfter} секунд`
          )
        } else if (apiError.error === 'bad_gateway' || apiError.error === 'service_unavailable' || apiError.error === 'gateway_timeout') {
          showError('Сервер недоступен', apiError.message)
        } else if (apiError.error === 'network_error') {
          showError('Ошибка сети', apiError.message)
        } else {
          showError('Ошибка входа', apiError.message)
        }
      }
  }
}

// Сброс формы при закрытии
watch(() => props.isOpen, (isOpen) => {
  if (!isOpen) {
    loginForm.value = {
      email: '',
      password: ''
    }
    registerForm.value = {
      email: '',
      password: '',
      confirmPassword: '',
      full_name: '',
      tenant_name: ''
    }
    validationErrors.value = {}
    showPassword.value = false
    showConfirmPassword.value = false
    showLoginPassword.value = false
    authMethod.value = 'login'
  }
})
</script>