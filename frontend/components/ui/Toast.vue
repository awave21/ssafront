<template>
  <Teleport to="body">
    <div
      v-if="toasts.length > 0"
      class="pointer-events-none fixed inset-x-0 top-0 z-[100] flex max-h-screen flex-col-reverse p-4 sm:inset-x-auto sm:bottom-0 sm:right-0 sm:top-auto sm:flex-col sm:pb-24 md:max-w-[400px]"
    >
      <TransitionGroup name="toast" tag="div" class="flex flex-col gap-2.5">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="group pointer-events-auto relative flex w-full items-start gap-3 overflow-hidden rounded-2xl border border-slate-100 bg-white p-4 pr-10 shadow-[0_20px_40px_-12px_rgba(0,0,0,0.14)]"
        >
          <!-- Цветная полоса слева: тип видно боковым зрением, но карточка
               остаётся белой и читается так же, как остальной интерфейс. -->
          <span class="absolute inset-y-0 left-0 w-1" :class="accent(toast.variant).bar" />

          <span
            class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl"
            :class="accent(toast.variant).icon"
          >
            <component :is="accent(toast.variant).component" class="h-4 w-4" />
          </span>

          <div class="min-w-0 flex-1 pt-0.5">
            <div v-if="toast.title" class="text-sm font-semibold leading-snug text-slate-900">
              {{ toast.title }}
            </div>
            <div
              v-if="toast.description"
              class="mt-0.5 break-words text-xs leading-relaxed text-slate-500"
            >
              {{ toast.description }}
            </div>
          </div>

          <button
            type="button"
            class="absolute right-2 top-2 flex h-7 w-7 items-center justify-center rounded-lg text-slate-300 transition-colors hover:bg-slate-100 hover:text-slate-600"
            aria-label="Закрыть уведомление"
            @click="removeToast(toast.id)"
          >
            <X class="h-3.5 w-3.5" />
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { CheckCircle2, Info, X, XCircle } from 'lucide-vue-next'
import { useToast, type ToastVariant } from '../../composables/useToast'

const { toasts, removeToast } = useToast()

/** Цвет полосы и подложки иконки по типу уведомления. */
const accent = (variant?: ToastVariant) => {
  if (variant === 'success') {
    return { bar: 'bg-emerald-500', icon: 'bg-emerald-50 text-emerald-600', component: CheckCircle2 }
  }
  if (variant === 'destructive') {
    return { bar: 'bg-red-500', icon: 'bg-red-50 text-red-600', component: XCircle }
  }
  return { bar: 'bg-primary', icon: 'bg-primary/10 text-primary', component: Info }
}
</script>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.toast-enter-from {
  opacity: 0;
  transform: translateX(24px) scale(0.98);
}

.toast-leave-to {
  opacity: 0;
  transform: translateX(24px) scale(0.98);
}

.toast-move {
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}
</style>
