<template>
  <div :class="['overflow-x-auto rounded-md border border-slate-200 bg-white', wrapperClass]">
    <table class="w-max min-w-full border-collapse text-left table-auto" v-bind="attrs">
      <slot />
    </table>
  </div>
</template>

<script setup lang="ts">
import { useAttrs } from 'vue'

defineOptions({ inheritAttrs: false })

defineProps<{
  wrapperClass?: string
}>()

const attrs = useAttrs()
</script>
