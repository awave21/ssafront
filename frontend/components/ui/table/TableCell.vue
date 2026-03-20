<template>
  <td
    :class="['px-2 py-2 text-sm text-slate-600 border-r border-slate-100 last:border-r-0 align-top text-left', className]"
    v-bind="attrs"
  >
    <slot />
  </td>
</template>

<script setup lang="ts">
import { useAttrs } from 'vue'

const props = defineProps<{
  className?: string
}>()

const attrs = useAttrs()
</script>
