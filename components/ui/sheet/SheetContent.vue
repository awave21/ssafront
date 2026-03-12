<template>
  <DialogPortal>
    <DialogOverlay
      class="fixed inset-0 z-[10000] bg-black/40 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:pointer-events-none"
    />
    <DialogContent
      :class="[
        'fixed z-[10001] bg-white shadow-xl flex flex-col',
        'duration-300 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:pointer-events-none',
        sideClasses,
        className
      ]"
      v-bind="{ ...forwarded, ...$attrs }"
    >
      <slot />
    </DialogContent>
  </DialogPortal>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  type DialogContentEmits,
  type DialogContentProps,
  DialogContent,
  DialogOverlay,
  DialogPortal,
  useForwardPropsEmits,
} from 'radix-vue'

type SheetSide = 'top' | 'bottom' | 'left' | 'right'

const props = withDefaults(defineProps<DialogContentProps & { side?: SheetSide; className?: string }>(), {
  side: 'right',
  className: ''
})

const emits = defineEmits<DialogContentEmits>()
const forwarded = useForwardPropsEmits(props, emits)

const sideClasses = computed(() => {
  const base: Record<SheetSide, string> = {
    right: 'right-0 top-0 bottom-0 w-full data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right',
    left: 'left-0 top-0 bottom-0 w-full data-[state=closed]:slide-out-to-left data-[state=open]:slide-in-from-left',
    top: 'top-0 left-0 right-0 data-[state=closed]:slide-out-to-top data-[state=open]:slide-in-from-top',
    bottom: 'bottom-0 left-0 right-0 data-[state=closed]:slide-out-to-bottom data-[state=open]:slide-in-from-bottom',
  }
  return base[props.side]
})
</script>
