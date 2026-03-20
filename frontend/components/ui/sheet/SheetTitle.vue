<template>
  <DialogTitle :class="['text-lg font-bold text-slate-900', className]">
    <slot />
  </DialogTitle>
</template>

<script setup lang="ts">
import { DialogTitle } from 'radix-vue'

defineProps<{ className?: string }>()
</script>
