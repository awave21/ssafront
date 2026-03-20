<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity duration-300"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-opacity duration-200"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="isOpen"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4"
        @click.self="$emit('close')"
      >
        <Transition
          enter-active-class="transition-all duration-300"
          enter-from-class="opacity-0 scale-95"
          enter-to-class="opacity-100 scale-100"
          leave-active-class="transition-all duration-200"
          leave-from-class="opacity-100 scale-100"
          leave-to-class="opacity-0 scale-95"
        >
          <div
            v-if="isOpen"
            class="bg-white rounded-xl shadow-xl max-w-md w-full mx-4"
            @click.stop
          >
            <!-- Invite Form -->
            <div v-if="!inviteLink" class="p-6">
              <div class="flex items-center justify-between mb-6">
                <h2 class="text-xl font-bold text-slate-900">
                  Пригласить пользователя
                </h2>
                <button
                  @click="$emit('close')"
                  class="p-2 text-slate-400 hover:text-slate-600 transition-colors"
                >
                  <X class="h-5 w-5" />
                </button>
              </div>

              <form @submit.prevent="handleInvite" class="space-y-4">
                <div>
                  <label class="block text-sm font-medium text-slate-700 mb-2">
                    Email
                  </label>
                  <input
                    v-model="form.email"
                    type="email"
                    required
                    class="w-full px-3 py-2 text-slate-900 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    placeholder="user@example.com"
                  />
                </div>

                <div>
                  <label class="block text-sm font-medium text-slate-700 mb-2">
                    Роль
                  </label>
                  <select
                    v-model="form.role"
                    required
                    class="w-full px-3 py-2 text-slate-900 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                  >
                    <option value="admin">Администратор</option>
                    <option value="manager">Менеджер</option>
                  </select>
                </div>

                <div v-if="error" class="bg-red-50 border border-red-200 rounded-lg p-3">
                  <p class="text-sm text-red-800">{{ error }}</p>
                </div>

                <div class="flex gap-3 justify-end pt-4">
                  <button
                    type="button"
                    @click="$emit('close')"
                    class="px-4 py-2 text-slate-700 bg-slate-100 rounded-lg hover:bg-slate-200 transition-colors"
                  >
                    Отмена
                  </button>
                  <button
                    type="submit"
                    :disabled="isLoading"
                    class="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
                  >
                    <Loader2 v-if="isLoading" class="h-4 w-4 animate-spin" />
                    {{ isLoading ? 'Создание...' : 'Создать приглашение' }}
                  </button>
                </div>
              </form>
            </div>

            <!-- Invite Link Display -->
            <div v-else class="p-6">
              <div class="flex items-center justify-between mb-6">
                <h2 class="text-xl font-bold text-slate-900">
                  Приглашение создано
                </h2>
                <button
                  @click="handleClose"
                  class="p-2 text-slate-400 hover:text-slate-600 transition-colors"
                >
                  <X class="h-5 w-5" />
                </button>
              </div>

              <div class="space-y-4">
                <div>
                  <label class="block text-sm font-medium text-slate-700 mb-2">
                    Ссылка для приглашения
                  </label>
                  <div class="flex gap-2">
                    <input
                      :value="inviteLink"
                      readonly
                      class="flex-1 px-3 py-2 text-slate-900 border border-slate-300 rounded-lg bg-slate-50 text-sm"
                    />
                    <button
                      @click="copyLink"
                      :disabled="copied"
                      class="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors whitespace-nowrap"
                    >
                      {{ copied ? 'Скопировано' : 'Копировать' }}
                    </button>
                  </div>
                </div>

                <div class="bg-blue-50 border border-blue-200 rounded-lg p-3">
                  <p class="text-sm text-blue-800">
                    <strong>Важно:</strong> Email не отправляется автоматически. Скопируйте ссылку и отправьте её пользователю вручную.
                  </p>
                </div>

                <div class="flex justify-end pt-4">
                  <button
                    @click="handleClose"
                    class="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
                  >
                    Готово
                  </button>
                </div>
              </div>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { X, Loader2 } from 'lucide-vue-next'
import { useApiFetch } from '../../composables/useApiFetch'
import { useToast } from '../../composables/useToast'
import { getReadableErrorMessage } from '~/utils/api-errors'

interface Props {
  isOpen: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  close: []
  invited: []
}>()

const apiFetch = useApiFetch()
const toast = useToast()
// @ts-ignore - Nuxt 3 auto-imports useRuntimeConfig
const { public: { siteUrl } } = useRuntimeConfig()

const form = ref({
  email: '',
  role: 'manager' as 'admin' | 'manager'
})

const isLoading = ref(false)
const error = ref<string | null>(null)
const inviteLink = ref<string | null>(null)
const copied = ref(false)

const getInviteBaseUrl = (): string => {
  if (siteUrl && !siteUrl.includes('localhost') && !siteUrl.includes('127.0.0.1')) return siteUrl
  if (typeof window !== 'undefined') return window.location.origin
  return siteUrl || ''
}

const resolveInviteLink = (rawLink: string): string => {
  if (!rawLink) return rawLink

  const baseUrl = getInviteBaseUrl()
  try {
    const resolved = baseUrl ? new URL(rawLink, baseUrl) : new URL(rawLink)

    if (baseUrl) {
      const base = new URL(baseUrl)
      if (resolved.host && base.host && resolved.host !== base.host) {
        resolved.protocol = base.protocol
        resolved.host = base.host
      }
    }

    return resolved.toString()
  } catch {
    return rawLink
  }
}

const handleInvite = async () => {
  isLoading.value = true
  error.value = null

  try {
    const response = await apiFetch<{
      id: string
      email: string
      role: string
      expires_at: string
      invited_by_user_id: string
      created_at: string
      invite_link: string
    }>('/invitations', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: {
        email: form.value.email,
        role: form.value.role
      }
    })

    inviteLink.value = resolveInviteLink(response.invite_link)
    toast.success('Приглашение создано', 'Ссылка для приглашения готова к использованию')
  } catch (err: any) {
    const status = err?.status || err?.statusCode || err?.response?.status
    
    const errorMessage = status === 409
      ? 'Приглашение для этого email уже существует. Удалите старое или используйте другой email.'
      : getReadableErrorMessage(err, 'Не удалось создать приглашение')
    
    error.value = errorMessage
    toast.error('Ошибка', errorMessage)
  } finally {
    isLoading.value = false
  }
}

const copyLink = async () => {
  if (!inviteLink.value) return

  try {
    await navigator.clipboard.writeText(inviteLink.value)
    copied.value = true
    toast.success('Скопировано', 'Ссылка скопирована в буфер обмена')
    
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch (err) {
    toast.error('Ошибка', 'Не удалось скопировать ссылку')
  }
}

const handleClose = () => {
  // Reset form and state
  form.value = {
    email: '',
    role: 'manager'
  }
  error.value = null
  inviteLink.value = null
  copied.value = false
  emit('close')
}
</script>
