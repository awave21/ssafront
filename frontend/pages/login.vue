<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Eye, EyeOff, ArrowRight, Loader2 } from 'lucide-vue-next'
import { useAuth, type ApiError } from '~/composables/useAuth'
import { useToast } from '~/composables/useToast'
import {
  ensureFreshAccessToken,
  getStoredAccessToken,
  isAccessTokenExpired,
} from '~/composables/authSessionManager'

definePageMeta({ layout: false })

useHead({
  title: 'Вход — chatmedbot',
  link: [
    { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
    { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' },
  ],
})

const router = useRouter()
const { register, login, isLoading } = useAuth()
const { error: showError, success: showSuccess } = useToast()

const authMethod = ref<'login' | 'register'>('login')
const validationErrors = ref<Record<string, string[]>>({})

const loginForm = ref({ email: '', password: '' })
const registerForm = ref({ email: '', password: '', confirmPassword: '', full_name: '', tenant_name: '' })

const showLoginPassword = ref(false)
const showPassword = ref(false)
const showConfirmPassword = ref(false)

const redirectToDashboard = async () => { await router.replace('/dashboard') }

onMounted(async () => {
  const token = getStoredAccessToken()
  if (token && !isAccessTokenExpired(token)) { await redirectToDashboard(); return }
  const ensured = await ensureFreshAccessToken({ forceRefresh: true })
  if (ensured.token) await redirectToDashboard()
})

const handleLogin = async () => {
  validationErrors.value = {}
  try {
    await login({ email: loginForm.value.email, password: loginForm.value.password })
    showSuccess('Добро пожаловать', 'Вы успешно вошли в систему')
    await redirectToDashboard()
  } catch (err: any) {
    const apiError: ApiError = err.apiError || { error: 'unknown_error', message: err.message || 'Ошибка входа' }
    if (apiError.details) validationErrors.value = apiError.details
    if (apiError.error === 'invalid_credentials') showError('Ошибка входа', 'Неверный логин или пароль')
    else if (apiError.error === 'rate_limit_exceeded') showError('Превышен лимит', `Попробуйте через ${apiError.retry_after || 60} с`)
    else if (apiError.error === 'account_inactive') showError('Ошибка', 'Аккаунт неактивен')
    else showError('Ошибка входа', apiError.message)
  }
}

const handleRegister = async () => {
  validationErrors.value = {}
  if (registerForm.value.password !== registerForm.value.confirmPassword) {
    validationErrors.value.confirmPassword = ['Пароли не совпадают']
    showError('Ошибка', 'Пароли не совпадают')
    return
  }
  try {
    await register(registerForm.value)
    showSuccess('Аккаунт создан', 'Добро пожаловать в chatmedbot')
    await redirectToDashboard()
  } catch (err: any) {
    const apiError: ApiError = err.apiError || { error: 'unknown_error', message: err.message || 'Ошибка регистрации' }
    if (apiError.details) validationErrors.value = apiError.details
    if (apiError.error === 'email_exists') showError('Ошибка', 'Пользователь с таким email уже существует')
    else showError('Ошибка регистрации', apiError.message)
  }
}

const BRAND_STATS = [
  { value: '+47%', label: 'конверсия\nв запись' },
  { value: '70%', label: 'рутины\nавтоматизировано' },
  { value: '3 дня', label: 'до первого\nдиалога агента' },
]
</script>

<template>
  <div class="welcome-root entry-layout">

    <!-- ─── Левая панель: брендинг ─────────────────── -->
    <div class="entry-brand">
      <!-- Атмосфера -->
      <div class="entry-brand__glow" />
      <div class="entry-brand__grid" aria-hidden="true" />

      <!-- Логотип -->
      <a href="https://chatmedbot.ru" class="entry-brand__logo relative z-10">
        <span class="display text-[26px]" style="color:#FAF7F2;">chatmedbot</span>
        <span class="entry-dot" />
      </a>

      <!-- Центральный текст -->
      <div class="relative z-10 flex-1 flex flex-col justify-center">
        <div class="mono mb-5" style="color:rgba(250,247,242,0.45);">— личный кабинет</div>
        <h2 class="display text-[clamp(38px,3.8vw,62px)]" style="color:#FAF7F2; line-height:1.0;">
          <span style="font-style:normal; font-variation-settings:'opsz' 96,'SOFT' 30; font-weight:350;">
            Управляйте<br />вашими
          </span><br />
          <span style="background:linear-gradient(to right,#4A9B7F,#F5A962);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">
            ИИ-агентами.
          </span>
        </h2>
        <p class="mt-5 text-[15px] leading-[1.65]" style="color:rgba(250,247,242,0.55); max-width:340px;">
          Аналитика, сценарии, каналы, база знаний — всё в одном рабочем пространстве.
        </p>

        <!-- Метрики -->
        <div class="mt-10 grid grid-cols-3 gap-5">
          <div v-for="s in BRAND_STATS" :key="s.value">
            <div class="numeral text-[28px]" style="color:#F5A962; white-space:nowrap;">{{ s.value }}</div>
            <div class="mono mt-1.5" style="color:rgba(250,247,242,0.4); font-size:9px; white-space:pre-line; line-height:1.5;">{{ s.label }}</div>
          </div>
        </div>
      </div>

      <!-- Подпись -->
      <div class="relative z-10">
        <div class="entry-brand__hairline" />
        <p class="serif text-[13px] italic mt-4" style="color:rgba(250,247,242,0.4);">
          «Наш администратор не может работать 24/7. А этот — может.»
        </p>
      </div>

      <!-- Декоративная кавычка -->
      <div aria-hidden="true" class="display absolute -bottom-16 -right-4 text-[280px] leading-none select-none pointer-events-none" style="color:rgba(255,255,255,0.03); font-style:italic;">&ldquo;</div>
    </div>

    <!-- ─── Правая панель: форма ──────────────────── -->
    <div class="entry-form-panel">
      <!-- Мобильный логотип -->
      <div class="flex items-baseline gap-1.5 mb-10 lg:hidden">
        <span class="display text-[22px]" style="color:var(--w-ink);">chatmedbot</span>
        <span class="h-1.5 w-1.5 rounded-full" style="background:linear-gradient(to right,#4A9B7F,#F5A962); transform:translateY(-4px);" />
      </div>

      <div class="entry-form-inner">
        <!-- Заголовок -->
        <div class="mb-8">
          <div class="mono mb-2" style="color:var(--w-ink-soft);">— точка входа · lk.chatmedbot.ru</div>
          <h1 class="display text-[clamp(30px,3.5vw,44px)]" style="color:var(--w-ink); line-height:1.05;">
            <span style="font-style:normal; font-variation-settings:'opsz' 96,'SOFT' 30; font-weight:350;">{{ authMethod === 'login' ? 'Войти в кабинет' : 'Создать' }}</span><span v-if="authMethod === 'register'" style="background:linear-gradient(to right,#4A9B7F,#F5A962);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;"> аккаунт</span>
          </h1>
        </div>

        <!-- Переключатель Вход / Регистрация -->
        <div class="entry-tabs">
          <button
            type="button"
            :class="['entry-tab', { 'entry-tab--active': authMethod === 'login' }]"
            @click="authMethod = 'login'; validationErrors = {}"
          >вход</button>
          <button
            type="button"
            :class="['entry-tab', { 'entry-tab--active': authMethod === 'register' }]"
            @click="authMethod = 'register'; validationErrors = {}"
          >регистрация</button>
        </div>

        <!-- ── Форма входа ── -->
        <form v-if="authMethod === 'login'" @submit.prevent="handleLogin" class="entry-fields">
          <div>
            <label class="entry-label">email</label>
            <input
              v-model="loginForm.email"
              type="email"
              required
              :class="['entry-input', { 'entry-input--err': validationErrors.email }]"
              placeholder="you@clinic.ru"
            />
            <p v-if="validationErrors.email" class="entry-err-msg">{{ validationErrors.email.join(', ') }}</p>
          </div>

          <div>
            <label class="entry-label">пароль</label>
            <div class="relative">
              <input
                v-model="loginForm.password"
                :type="showLoginPassword ? 'text' : 'password'"
                required
                minlength="8"
                maxlength="128"
                :class="['entry-input pr-11', { 'entry-input--err': validationErrors.password }]"
                placeholder="••••••••"
              />
              <button type="button" @click="showLoginPassword = !showLoginPassword" class="entry-eye-btn">
                <component :is="showLoginPassword ? EyeOff : Eye" :size="15" />
              </button>
            </div>
            <p v-if="validationErrors.password" class="entry-err-msg">{{ validationErrors.password.join(', ') }}</p>
          </div>

          <button type="submit" :disabled="isLoading" class="entry-cta">
            <Loader2 v-if="isLoading" :size="15" class="animate-spin" />
            <span>{{ isLoading ? 'Входим...' : 'Войти' }}</span>
            <ArrowRight v-if="!isLoading" :size="15" />
          </button>
        </form>

        <!-- ── Форма регистрации ── -->
        <form v-else @submit.prevent="handleRegister" class="entry-fields">
          <div>
            <label class="entry-label">email</label>
            <input
              v-model="registerForm.email"
              type="email"
              required
              :class="['entry-input', { 'entry-input--err': validationErrors.email }]"
              placeholder="you@clinic.ru"
            />
            <p v-if="validationErrors.email" class="entry-err-msg">{{ validationErrors.email.join(', ') }}</p>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="entry-label">пароль</label>
              <div class="relative">
                <input
                  v-model="registerForm.password"
                  :type="showPassword ? 'text' : 'password'"
                  required
                  minlength="8"
                  maxlength="128"
                  :class="['entry-input pr-11', { 'entry-input--err': validationErrors.password }]"
                  placeholder="••••••••"
                />
                <button type="button" @click="showPassword = !showPassword" class="entry-eye-btn">
                  <component :is="showPassword ? EyeOff : Eye" :size="15" />
                </button>
              </div>
            </div>
            <div>
              <label class="entry-label">повторить</label>
              <div class="relative">
                <input
                  v-model="registerForm.confirmPassword"
                  :type="showConfirmPassword ? 'text' : 'password'"
                  required
                  minlength="8"
                  maxlength="128"
                  :class="['entry-input pr-11', { 'entry-input--err': validationErrors.confirmPassword }]"
                  placeholder="••••••••"
                />
                <button type="button" @click="showConfirmPassword = !showConfirmPassword" class="entry-eye-btn">
                  <component :is="showConfirmPassword ? EyeOff : Eye" :size="15" />
                </button>
              </div>
              <p v-if="validationErrors.confirmPassword" class="entry-err-msg">{{ validationErrors.confirmPassword.join(', ') }}</p>
            </div>
          </div>

          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="entry-label">имя</label>
              <input
                v-model="registerForm.full_name"
                type="text"
                maxlength="200"
                class="entry-input"
                placeholder="Иван Иванов"
              />
            </div>
            <div>
              <label class="entry-label">организация</label>
              <input
                v-model="registerForm.tenant_name"
                type="text"
                maxlength="200"
                class="entry-input"
                placeholder="Клиника"
              />
            </div>
          </div>

          <button type="submit" :disabled="isLoading" class="entry-cta">
            <Loader2 v-if="isLoading" :size="15" class="animate-spin" />
            <span>{{ isLoading ? 'Создаём аккаунт...' : 'Зарегистрироваться' }}</span>
            <ArrowRight v-if="!isLoading" :size="15" />
          </button>
        </form>

        <!-- Ссылка на лендинг -->
        <p class="mt-8 mono" style="color:var(--w-ink-soft); font-size:10px;">
          ИИ-агенты для медицинских клиник ·
          <a href="https://chatmedbot.ru" target="_blank" rel="noopener"
             class="hover:text-[var(--w-ink)] transition-colors underline underline-offset-2">
            chatmedbot.ru
          </a>
        </p>
      </div>
    </div>
  </div>
</template>

<style src="~/assets/css/welcome.css"></style>

<style scoped>
/* Layout */
.entry-layout {
  min-height: 100dvh;
  display: grid;
  grid-template-columns: 1fr;
}
@media (min-width: 1024px) {
  .entry-layout { grid-template-columns: 1fr 1fr; }
}

/* Brand panel */
.entry-brand {
  position: relative;
  display: none;
  flex-direction: column;
  padding: 3rem;
  background: var(--w-ink);
  overflow: hidden;
}
@media (min-width: 1024px) {
  .entry-brand { display: flex; }
}

.entry-brand__glow {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(ellipse 70% 55% at 15% 15%, rgba(74,155,127,0.18) 0%, transparent 65%),
    radial-gradient(ellipse 60% 45% at 85% 85%, rgba(245,169,98,0.14) 0%, transparent 60%);
  pointer-events: none;
}

.entry-brand__grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(to right, rgba(255,255,255,0.04) 1px, transparent 1px),
    linear-gradient(to bottom, rgba(255,255,255,0.04) 1px, transparent 1px);
  background-size: 24px 24px;
  pointer-events: none;
}

.entry-brand__logo {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  text-decoration: none;
}

.entry-dot {
  display: block;
  height: 8px;
  width: 8px;
  border-radius: 50%;
  background: linear-gradient(to right, #4A9B7F, #F5A962);
  transform: translateY(-5px);
  flex-shrink: 0;
}

.entry-brand__hairline {
  height: 1px;
  background: rgba(250,247,242,0.12);
}

/* Form panel */
.entry-form-panel {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 2.5rem 1.5rem;
  background: var(--w-paper);
}
@media (min-width: 640px) {
  .entry-form-panel { padding: 3rem 2.5rem; }
}
@media (min-width: 1024px) {
  .entry-form-panel { padding: 3rem 4rem; }
}

.entry-form-inner {
  width: 100%;
  max-width: 400px;
  margin: 0 auto;
}
@media (min-width: 1024px) {
  .entry-form-inner { margin: 0; }
}

/* Tab switcher */
.entry-tabs {
  display: flex;
  gap: 2px;
  padding: 3px;
  border-radius: 999px;
  background: var(--w-paper-deep);
  margin-bottom: 2rem;
}

.entry-tab {
  flex: 1;
  padding: 8px 16px;
  border-radius: 999px;
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--w-ink-soft);
  border: none;
  cursor: pointer;
  transition: all 200ms ease;
  background: transparent;
}

.entry-tab--active {
  background: var(--w-surface);
  color: var(--w-ink);
  box-shadow: 0 1px 4px rgba(31,36,33,0.10);
}

/* Form fields */
.entry-fields {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.entry-label {
  display: block;
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--w-ink-soft);
  margin-bottom: 6px;
}

.entry-input {
  width: 100%;
  padding: 10px 14px;
  border-radius: 10px;
  border: 1px solid var(--w-rule);
  background: var(--w-surface);
  color: var(--w-ink);
  font-family: 'Instrument Sans', system-ui, sans-serif;
  font-size: 14px;
  transition: border-color 200ms ease, box-shadow 200ms ease;
  outline: none;
  -webkit-appearance: none;
}

.entry-input:focus {
  border-color: #4A9B7F;
  box-shadow: 0 0 0 3px rgba(74,155,127,0.12);
}

.entry-input--err {
  border-color: #C56666 !important;
}

.entry-input::placeholder {
  color: var(--w-ink-soft);
  opacity: 0.5;
}

.entry-eye-btn {
  position: absolute;
  inset-block: 0;
  right: 0;
  padding: 0 12px;
  display: flex;
  align-items: center;
  color: var(--w-ink-soft);
  border: none;
  background: transparent;
  cursor: pointer;
  transition: color 150ms ease;
}
.entry-eye-btn:hover { color: var(--w-ink); }

.entry-err-msg {
  margin-top: 4px;
  font-size: 12px;
  color: #C56666;
  font-family: 'Instrument Sans', system-ui, sans-serif;
}

/* CTA button */
.entry-cta {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 12px 24px;
  border-radius: 999px;
  font-family: 'Instrument Sans', system-ui, sans-serif;
  font-size: 14px;
  font-weight: 500;
  color: #fff;
  background: linear-gradient(to right, #4A9B7F, #F5A962);
  border: none;
  cursor: pointer;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.18), 0 1px 3px rgba(31,36,33,0.15);
  transition: opacity 200ms ease, transform 200ms ease, box-shadow 200ms ease;
  margin-top: 0.5rem;
}

.entry-cta:hover:not(:disabled) {
  opacity: 0.92;
  transform: translateY(-1px);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.22), 0 8px 28px rgba(74,155,127,0.32);
}

.entry-cta:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
