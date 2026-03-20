<template>
  <div :class="['flex-shrink-0 bg-white border-t border-slate-100 px-6 py-4', className]">
    <slot />
  </div>
</template>

<script setup lang="ts">
defineProps<{ className?: string }>()
</script>
