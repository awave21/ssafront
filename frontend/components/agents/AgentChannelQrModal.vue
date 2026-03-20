<template>
  <Teleport to="body">
    <Transition name="modal-fade">
      <div
        v-if="open"
        class="fixed inset-0 z-[70] flex items-center justify-center p-4"
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
              @click="emit('update:open', false)"
            >
              Закрыть
            </button>
          </div>

          <p class="text-sm text-slate-500 mb-4">
            Откройте приложение мессенджера и отсканируйте QR-код для завершения авторизации.
          </p>

          <div class="rounded-xl border border-slate-200 bg-slate-50 p-4 flex items-center justify-center min-h-[280px]">
            <img
              v-if="qrCode"
              :src="qrCode"
              alt="QR код для авторизации"
              class="w-64 h-64 object-contain bg-white rounded-lg border border-slate-200 p-2"
            />
            <span v-else class="text-sm text-slate-500">
              QR-код пока недоступен
            </span>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  open: boolean
  title?: string
  qrCode?: string | null
}>(), {
  title: 'Авторизация по QR',
  qrCode: null
})

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
}>()
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
