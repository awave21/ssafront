<template>
  <Teleport to="body">
    <div
      v-if="toasts.length > 0"
      class="fixed top-0 z-[100] flex max-h-screen w-full flex-col-reverse p-4 sm:bottom-0 sm:right-0 sm:top-auto sm:flex-col md:max-w-[420px]"
    >
      <TransitionGroup
        name="toast"
        tag="div"
        class="flex flex-col gap-2"
      >
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="group pointer-events-auto relative flex w-full items-center justify-between space-x-4 overflow-hidden rounded-lg border border-slate-200 bg-white p-6 pr-8 shadow-lg transition-all data-[swipe=cancel]:translate-x-0 data-[swipe=end]:translate-x-[var(--radix-toast-swipe-end-x)] data-[swipe=move]:translate-x-[var(--radix-toast-swipe-move-x)] data-[swipe=move]:transition-none data-[state=open]:animate-in data-[state=closed]:animate-out data-[swipe=end]:animate-out data-[state=closed]:fade-out-80 data-[state=closed]:slide-out-to-right-full data-[state=open]:slide-in-from-top-full data-[state=open]:sm:slide-in-from-bottom-full"
          :class="{
            'border-red-200 bg-red-50': toast.variant === 'destructive',
            'border-green-200 bg-green-50': toast.variant === 'success',
            'border-blue-200 bg-blue-50': toast.variant === 'info',
          }"
        >
          <div class="grid gap-1">
            <div
              v-if="toast.title"
              class="text-sm font-semibold"
              :class="{
                'text-red-900': toast.variant === 'destructive',
                'text-green-900': toast.variant === 'success',
                'text-blue-900': toast.variant === 'info',
                'text-slate-900': !toast.variant,
              }"
            >
              {{ toast.title }}
            </div>
            <div
              v-if="toast.description"
              class="text-sm opacity-90"
              :class="{
                'text-red-800': toast.variant === 'destructive',
                'text-green-800': toast.variant === 'success',
                'text-blue-800': toast.variant === 'info',
                'text-slate-600': !toast.variant,
              }"
            >
              {{ toast.description }}
            </div>
          </div>
          <button
            @click="removeToast(toast.id)"
            class="absolute right-2 top-2 rounded-md p-1 text-slate-950/50 opacity-0 transition-opacity hover:text-slate-950 focus:opacity-100 focus:outline-none focus:ring-2 group-hover:opacity-100"
            :class="{
              'text-red-600 hover:text-red-900': toast.variant === 'destructive',
              'text-green-600 hover:text-green-900': toast.variant === 'success',
              'text-blue-600 hover:text-blue-900': toast.variant === 'info',
            }"
          >
            <X class="h-4 w-4" />
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { X } from 'lucide-vue-next'
import { useToast } from '../../composables/useToast'

const { toasts, removeToast } = useToast()
</script>

<style scoped>
.toast-enter-active,
.toast-leave-active {
  transition: all 0.3s ease;
}

.toast-enter-from {
  opacity: 0;
  transform: translateX(100%);
}

.toast-leave-to {
  opacity: 0;
  transform: translateX(100%);
}

.toast-move {
  transition: transform 0.3s ease;
}
</style>