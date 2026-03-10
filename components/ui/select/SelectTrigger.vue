<template>
  <SelectTrigger
    v-bind="filteredAttrs"
    :class="cn(
      'flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/60 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 [&>span]:line-clamp-1',
      props.class
    )"
  >
    <slot />
    <SelectIcon as-child>
      <ChevronDown class="h-4 w-4 opacity-50" />
    </SelectIcon>
  </SelectTrigger>
</template>

<script setup lang="ts">
import { computed, useAttrs } from 'vue'
import type { HTMLAttributes } from 'vue'
import { SelectTrigger, SelectIcon } from 'radix-vue'
import { ChevronDown } from 'lucide-vue-next'
import { cn } from '~/lib/utils'

const props = defineProps<{
  class?: HTMLAttributes['class']
}>()

const attrs = useAttrs()
const filteredAttrs = computed(() => {
  const { class: _, ...rest } = attrs
  return rest
})
</script>
