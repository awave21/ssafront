<template>
  <span
    class="text-[9px] font-medium"
    :class="{
      'text-emerald-600': tone === 'ok',
      'text-amber-600': tone === 'warn',
      'text-destructive': tone === 'danger',
    }"
  >
    {{ label }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  tone: 'ok' | 'warn' | 'danger'
}>()

const label = computed(() => {
  if (props.tone === 'ok') return 'готово'
  if (props.tone === 'warn') return 'проверить'
  return 'не готово'
})
</script>
