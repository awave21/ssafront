<template>
  <DialogDescription :class="['text-sm text-slate-500 mt-0.5', className]">
    <slot />
  </DialogDescription>
</template>

<script setup lang="ts">
import { DialogDescription } from 'radix-vue'

defineProps<{ className?: string }>()
</script>
