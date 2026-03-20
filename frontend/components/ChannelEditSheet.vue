<template>
  <Teleport to="body">
    <!-- Overlay with fade -->
    <Transition name="overlay-fade">
      <div
        v-if="open"
        class="fixed inset-0 z-[60] bg-black/40"
        aria-hidden="true"
        @click="emit('update:open', false)"
      />
    </Transition>

    <!-- Panel with slide -->
    <Transition name="panel-slide">
      <div
        v-if="open"
        class="fixed right-0 top-0 bottom-0 z-[61] w-full max-w-md sm:max-w-lg bg-white shadow-xl border-l border-slate-200 flex flex-col max-h-full overflow-hidden"
        aria-modal="true"
        role="dialog"
        @click.stop
      >
          <!-- Header -->
          <div class="flex items-center justify-between shrink-0 px-6 py-4 border-b border-slate-200">
            <div>
              <h2 class="text-lg font-bold text-slate-900">Настройки Telegram</h2>
              <p class="text-sm text-slate-500 mt-0.5">Изменить токен или отключить канал</p>
            </div>
            <button
              type="button"
              aria-label="Закрыть"
              class="p-2 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
              @click="emit('update:open', false)"
            >
              <X class="h-5 w-5" />
            </button>
          </div>

          <!-- Content -->
          <div class="flex-1 overflow-y-auto px-6 py-6 space-y-8">
            <!-- Изменить токен -->
            <section>
              <h3 class="text-sm font-bold text-slate-900 mb-2">Токен бота</h3>
              <p class="text-xs text-slate-500 mb-3">
                Введите новый токен от @BotFather, чтобы обновить подключение.
              </p>
              <form @submit.prevent="handleSaveToken" class="space-y-3">
                <input
                  v-model="localToken"
                  type="text"
                  autocomplete="off"
                  placeholder="7123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"
                  class="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm text-slate-900 placeholder:text-slate-400 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
                <button
                  type="submit"
                  :disabled="!localToken.trim() || saving"
                  class="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-indigo-600 text-white rounded-xl text-sm font-bold hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  <Loader2 v-if="saving" class="w-4 h-4 animate-spin" />
                  <Check v-else class="w-4 h-4" />
                  Сохранить токен
                </button>
                <p v-if="saveError" class="text-sm text-red-600">{{ saveError }}</p>
                <p v-if="saveSuccess" class="text-sm text-green-600 font-medium">Токен сохранён.</p>
              </form>
            </section>

            <!-- Удалить подключение -->
            <section class="pt-6 border-t border-slate-200">
              <h3 class="text-sm font-bold text-slate-900 mb-2">Удалить подключение</h3>
              <p class="text-xs text-slate-500 mb-4">
                Канал Telegram будет отключён от агента. Подключить его можно снова в любой момент.
              </p>
              <button
                type="button"
                :disabled="deleting"
                class="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-white border border-red-200 text-red-600 rounded-xl text-sm font-bold hover:bg-red-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                @click="confirmDelete"
              >
                <Loader2 v-if="deleting" class="w-4 h-4 animate-spin" />
                <Trash2 v-else class="w-4 h-4" />
                {{ deleting ? 'Удаление...' : 'Удалить подключение' }}
              </button>
              <p v-if="deleteError" class="mt-2 text-sm text-red-600">{{ deleteError }}</p>
            </section>
          </div>
      </div>
    </Transition>
  </Teleport>

  <!-- Confirm delete -->
  <Teleport to="body">
    <Transition name="modal-fade">
      <div
        v-if="showDeleteConfirm"
        class="fixed inset-0 z-[70] flex items-center justify-center p-4"
        aria-modal="true"
        role="alertdialog"
      >
        <div class="absolute inset-0 bg-black/50" @click="showDeleteConfirm = false" />
        <div class="relative bg-white rounded-2xl shadow-xl p-6 max-w-sm w-full border border-slate-200">
          <h3 class="text-lg font-bold text-slate-900 mb-2">Удалить канал Telegram?</h3>
          <p class="text-sm text-slate-500 mb-6">
            Подключение будет отключено. Вы сможете подключить канал снова позже.
          </p>
          <div class="flex gap-3">
            <button
              type="button"
              class="flex-1 px-4 py-2.5 rounded-xl text-sm font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 transition-colors"
              @click="showDeleteConfirm = false"
            >
              Отмена
            </button>
            <button
              type="button"
              :disabled="deleting"
              class="flex-1 px-4 py-2.5 rounded-xl text-sm font-bold text-white bg-red-600 hover:bg-red-700 disabled:opacity-50 transition-colors"
              @click="handleDelete"
            >
              Удалить
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { X, Check, Loader2, Trash2 } from 'lucide-vue-next'
import { useApiFetch } from '../composables/useApiFetch'
import { useAuth } from '../composables/useAuth'

const props = defineProps<{
  open: boolean
  agentId: string
  currentToken?: string // Токен, сохранённый ранее (с бэкенда)
}>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'saved'): void
  (e: 'deleted'): void
}>()

const apiFetch = useApiFetch()
const { token } = useAuth()

const localToken = ref('')
const saving = ref(false)
const saveError = ref<string | null>(null)
const saveSuccess = ref(false)
const deleting = ref(false)
const deleteError = ref<string | null>(null)
const showDeleteConfirm = ref(false)

// Regex для валидации формата Telegram Bot Token: 7123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw
const TELEGRAM_TOKEN_REGEX = /^\d{9,12}:[A-Za-z0-9_-]{30,50}$/

const isValidToken = (token: string): boolean => {
  return TELEGRAM_TOKEN_REGEX.test(token.trim())
}

watch(
  () => [props.open, props.currentToken] as const,
  ([isOpen, tokenVal]) => {
    if (isOpen) {
      // Заполняем поле сохранённым токеном, если есть
      localToken.value = tokenVal ?? ''
      saveError.value = null
      saveSuccess.value = false
      deleteError.value = null
    }
  },
  { immediate: true }
)

const handleSaveToken = async () => {
  const trimmedToken = localToken.value.trim()
  
  if (!props.agentId || !trimmedToken) return
  
  // Валидация формата токена
  if (!isValidToken(trimmedToken)) {
    saveError.value = 'Неверный формат токена. Пример: 7123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw'
    return
  }
  saving.value = true
  saveError.value = null
  saveSuccess.value = false
  try {
    await apiFetch(`/agents/${props.agentId}/channels`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token.value}`,
        'Content-Type': 'application/json'
      },
      body: {
        type: 'Telegram_Bot',
        telegram_bot_token: trimmedToken,
        whatsapp_phone: null
      }
    })
    saveSuccess.value = true
    emit('saved')
  } catch (err: any) {
    const msg = err?.data?.detail ?? err?.data?.message ?? err?.message ?? 'Не удалось сохранить'
    saveError.value = typeof msg === 'string' ? msg : JSON.stringify(msg)
  } finally {
    saving.value = false
  }
}

const confirmDelete = () => {
  showDeleteConfirm.value = true
  deleteError.value = null
}

const handleDelete = async () => {
  if (!props.agentId) return
  deleting.value = true
  deleteError.value = null
  try {
    await apiFetch(`/agents/${props.agentId}/channels/telegram`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token.value}` }
    })
    showDeleteConfirm.value = false
    emit('deleted')
    emit('update:open', false)
  } catch (err: any) {
    const msg = err?.data?.detail ?? err?.data?.message ?? err?.message ?? 'Не удалось удалить'
    deleteError.value = typeof msg === 'string' ? msg : JSON.stringify(msg)
  } finally {
    deleting.value = false
  }
}
</script>

<style scoped>
/* Overlay fades */
.overlay-fade-enter-active,
.overlay-fade-leave-active {
  transition: opacity 0.25s ease;
}
.overlay-fade-enter-from,
.overlay-fade-leave-to {
  opacity: 0;
}

/* Panel slides from right */
.panel-slide-enter-active,
.panel-slide-leave-active {
  transition: transform 0.25s ease;
}
.panel-slide-enter-from,
.panel-slide-leave-to {
  transform: translateX(100%);
}

.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.2s ease;
}
.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}
</style>
