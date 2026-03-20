<template>
  <thead
    :class="['bg-slate-50/50 border-b border-slate-200', className]"
    v-bind="attrs"
  >
    <slot />
  </thead>
</template>

<script setup lang="ts">
import { useAttrs } from 'vue'

const props = defineProps<{
  className?: string
}>()

const attrs = useAttrs()
</script>
