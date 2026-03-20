<template>
  <th
    :class="['px-2 py-2.5 text-[11px] font-bold uppercase tracking-wider text-slate-500 border-r border-slate-200 last:border-r-0 bg-slate-50/50 text-left', className]"
    scope="col"
    v-bind="attrs"
  >
    <slot />
  </th>
</template>

<script setup lang="ts">
import { useAttrs } from 'vue'

const props = defineProps<{
  className?: string
}>()

const attrs = useAttrs()
</script>
