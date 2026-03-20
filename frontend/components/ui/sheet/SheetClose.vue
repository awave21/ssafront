<template>
  <DialogClose
    :class="[
      'p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors',
      'focus:outline-none focus:ring-2 focus:ring-indigo-400',
      className
    ]"
  >
    <slot>
      <X class="h-5 w-5" />
    </slot>
    <span class="sr-only">Закрыть</span>
  </DialogClose>
</template>

<script setup lang="ts">
import { DialogClose } from 'radix-vue'
import { X } from 'lucide-vue-next'

defineProps<{ className?: string }>()
</script>
