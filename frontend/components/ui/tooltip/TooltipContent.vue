<script setup lang="ts">
import { TooltipContent, TooltipPortal, type TooltipContentProps } from 'radix-vue'
import { computed } from 'vue'

const props = withDefaults(defineProps<TooltipContentProps & { class?: string }>(), {
  side: 'right',
  sideOffset: 8,
})

const delegatedProps = computed(() => {
  const { class: _, ...delegated } = props
  return delegated
})
</script>

<template>
  <TooltipPortal>
    <TooltipContent
      v-bind="delegatedProps"
      class="z-[9999] overflow-hidden rounded-md bg-white border border-slate-200 px-3 py-1.5 text-sm text-slate-700 shadow-md animate-in fade-in-0 zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[side=right]:slide-in-from-left-2"
    >
      <slot />
    </TooltipContent>
  </TooltipPortal>
</template>
