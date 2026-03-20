<template>
  <Teleport to="body">
    <Transition name="modal-fade">
      <div
        v-if="isOpen"
        class="fixed inset-0 z-[60] flex items-center justify-center px-4 py-6 sm:px-6"
        aria-modal="true"
        role="dialog"
      >
        <div class="fixed inset-0 bg-black/40 backdrop-blur-sm" @click="emitClose"></div>
        <div
          class="relative w-full max-w-lg overflow-hidden rounded-2xl bg-white py-8 px-6 shadow-xl shadow-indigo-900/20 ring-1 ring-indigo-100"
          @click.stop
        >
          <div class="flex items-center justify-between mb-6">
            <div>
              <h2 class="text-lg font-bold text-slate-900">Включить SQNS</h2>
              <p class="text-sm text-slate-500 mt-1">Подключите CRM через защищённый ключ</p>
            </div>
            <button aria-label="Закрыть" class="text-slate-400 hover:text-slate-600" @click="emitClose">
              <XIcon class="h-5 w-5" />
            </button>
          </div>

          <form @submit.prevent="handleSubmit" class="space-y-5">
            <div>
              <label class="text-sm font-medium text-slate-700">Email*</label>
              <input
                v-model.trim="email"
                type="email"
                required
                placeholder="admin@clinic.com"
                class="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
              />
            </div>

            <div>
              <label class="text-sm font-medium text-slate-700">Пароль*</label>
              <input
                v-model="password"
                type="password"
                autocomplete="new-password"
                required
                placeholder="••••••••"
                class="mt-1 w-full rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-900 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
              />
              <p class="mt-1 text-xs text-slate-500">
                Учетные данные используются для получения токена доступа.
              </p>
            </div>

            <p v-if="validationError" class="text-sm text-red-600">{{ validationError }}</p>

            <div class="flex items-center justify-between gap-3">
              <button
                type="button"
                class="flex-1 rounded-xl border border-slate-200 px-4 py-3 text-sm font-medium text-slate-600 hover:bg-slate-100"
                @click="emitClose"
              >
                Отмена
              </button>
              <button
                type="submit"
                class="flex-1 rounded-xl bg-indigo-600 px-4 py-3 text-sm font-medium text-white shadow hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
                :disabled="props.isSubmitting"
              >
                <span v-if="props.isSubmitting">Сохраняем...</span>
                <span v-else>Включить SQNS</span>
              </button>
            </div>
          </form>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { X as XIcon } from 'lucide-vue-next'

const props = defineProps<{
  isOpen: boolean
  isSubmitting?: boolean
}>()

const emit = defineEmits<{
  (event: 'close'): void
  (event: 'submit', payload: { email: string; password: string }): void
}>()

const email = ref('')
const password = ref('')
const validationError = ref('')

const emitClose = () => {
  resetForm()
  emit('close')
}

const resetForm = () => {
  email.value = ''
  password.value = ''
  validationError.value = ''
}

const handleSubmit = () => {
  validationError.value = ''
  if (!email.value.trim()) {
    validationError.value = 'Введите email'
    return
  }

  if (!password.value.trim()) {
    validationError.value = 'Введите пароль'
    return
  }

  emit('submit', {
    email: email.value,
    password: password.value
  })
}

watch(
  () => props.isOpen,
  (value) => {
    if (!value) {
      resetForm()
    }
  }
)
</script>
