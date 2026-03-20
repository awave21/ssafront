<template>
  <tr
    :class="['border-b border-slate-100 last:border-b-0 hover:bg-slate-50/50 transition-colors duration-150', className]"
    v-bind="attrs"
  >
    <slot />
  </tr>
</template>

<script setup lang="ts">
import { useAttrs } from 'vue'

const props = defineProps<{
  className?: string
}>()

const attrs = useAttrs()
</script>
