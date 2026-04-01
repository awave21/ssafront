<template>
  <div
    class="mb-8 flex items-start gap-3 rounded-3xl border border-rose-100 bg-rose-50/50 p-4 text-sm text-rose-600 shadow-sm"
    role="alert"
  >
    <span class="mt-0.5 h-2 w-2 shrink-0 animate-pulse rounded-full bg-rose-500" />
    <span class="font-bold">{{ message }}</span>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  message: string
}>()
</script>
