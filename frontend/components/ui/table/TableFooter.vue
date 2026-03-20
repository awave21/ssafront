<template>
  <tfoot
    :class="['bg-slate-50/80', className]"
    v-bind="attrs"
  >
    <slot />
  </tfoot>
</template>

<script setup lang="ts">
import { useAttrs } from 'vue'

const props = defineProps<{
  className?: string
}>()

const attrs = useAttrs()
</script>
