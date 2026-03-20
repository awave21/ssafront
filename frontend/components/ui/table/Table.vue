<template>
  <div :class="['overflow-x-auto rounded-md border border-slate-200 bg-white', wrapperClass]">
    <table
      class="min-w-full border-collapse text-left table-fixed"
      v-bind="attrs"
    >
      <slot />
    </table>
  </div>
</template>

<script setup lang="ts">
import { useAttrs } from 'vue'

const props = defineProps<{
  wrapperClass?: string
}>()

const attrs = useAttrs()
</script>
