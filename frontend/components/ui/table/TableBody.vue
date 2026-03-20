<template>
  <tbody
    :class="['bg-white', className]"
    v-bind="attrs"
  >
    <slot />
  </tbody>
</template>

<script setup lang="ts">
import { useAttrs } from 'vue'

const props = defineProps<{
  className?: string
}>()

const attrs = useAttrs()
</script>
