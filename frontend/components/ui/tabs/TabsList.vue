<template>
  <div :class="['flex gap-2 flex-wrap', className]" v-bind="attrs">
    <slot />
  </div>
</template>

<script setup lang="ts">
import { useAttrs } from 'vue'

const props = defineProps<{
  className?: string
}>()

const attrs = useAttrs()
</script>
