<template>
  <Teleport to="body">
    <Transition name="modal-fade">
      <div
        v-if="open"
        class="fixed inset-0 z-[71] flex items-center justify-center p-4"
        aria-modal="true"
        role="dialog"
      >
        <div class="absolute inset-0 bg-black/50" @click="emit('update:open', false)" />
        <div class="relative bg-white rounded-2xl shadow-xl p-6 max-w-md w-full border border-slate-200">
          <div class="flex items-center justify-between mb-4">
            <h3 class="text-lg font-bold text-slate-900">{{ title }}</h3>
            <button
              type="button"
              class="px-2 py-1 rounded-md text-sm text-slate-500 hover:bg-slate-100"
              :disabled="loading"
              @click="emit('update:open', false)"
            >
              Закрыть
            </button>
          </div>

          <p class="text-sm text-slate-500 mb-3">
            WAPPI запрашивает пароль двухфакторной авторизации (2FA). Введите облачный пароль аккаунта.
          </p>
          <p v-if="detail" class="text-xs text-slate-500 mb-4">
            Ответ сервиса: <span class="font-medium text-slate-700">{{ detail }}</span>
          </p>

          <form class="space-y-3" @submit.prevent="handleSubmit">
            <input
              v-model="pwdCode"
              type="password"
              autocomplete="current-password"
              placeholder="Введите пароль 2FA"
              class="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm text-slate-900 placeholder:text-slate-400 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            />
            <p v-if="errorMessage" class="text-sm text-red-600">
              {{ errorMessage }}
            </p>
            <button
              type="submit"
              :disabled="loading || !pwdCode.trim()"
              class="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-indigo-600 text-white rounded-xl text-sm font-bold hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <span v-if="loading">Отправляем...</span>
              <span v-else>Подтвердить 2FA</span>
            </button>
          </form>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  open: boolean
  title?: string
  detail?: string | null
  errorMessage?: string | null
  loading?: boolean
}>(), {
  title: 'Введите пароль 2FA',
  detail: null,
  errorMessage: null,
  loading: false
})

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'submit', value: string): void
}>()

const pwdCode = ref('')

watch(() => props.open, (isOpen) => {
  if (isOpen) {
    pwdCode.value = ''
  }
})

const handleSubmit = () => {
  const normalized = pwdCode.value.trim()
  if (!normalized) return
  emit('submit', normalized)
}
</script>

<style scoped>
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.2s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}
</style>
