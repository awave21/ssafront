<template>
  <SelectItem
    :value="value"
    :disabled="disabled"
    :text-value="textValue"
    :as-child="asChild"
    :as="as"
    class="relative flex w-full cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-none transition-colors focus:bg-accent/70 focus:text-accent-foreground data-[highlighted]:bg-accent/70 data-[highlighted]:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
    :class="cn(props.class)"
  >
    <span class="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
      <SelectItemIndicator>
        <Check class="h-4 w-4" />
      </SelectItemIndicator>
    </span>
    <SelectItemText>
      <slot />
    </SelectItemText>
  </SelectItem>
</template>

<script setup lang="ts">
import type { HTMLAttributes } from 'vue'
import { SelectItem, SelectItemIndicator, SelectItemText } from 'radix-vue'
import { Check } from 'lucide-vue-next'
import { cn } from '~/lib/utils'

interface Props {
  value: string
  disabled?: boolean
  textValue?: string
  asChild?: boolean
  as?: unknown
  class?: HTMLAttributes['class']
}

const props = defineProps<Props>()
</script>
