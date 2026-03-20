<script setup lang="ts">
import { CalendarCellTrigger, type CalendarCellTriggerProps, useForwardProps } from 'reka-ui'
import { computed, type HTMLAttributes } from 'vue'
import { buttonVariants } from '~/components/ui/button'
import { cn } from '~/lib/utils'

const props = defineProps<CalendarCellTriggerProps & { class?: HTMLAttributes['class'] }>()

const delegatedProps = computed(() => {
  const { class: _, ...delegated } = props

  return delegated
})

const forwardedProps = useForwardProps(delegatedProps)
</script>

<template>
  <CalendarCellTrigger
    :class="cn(
      buttonVariants({ variant: 'ghost' }),
      'h-9 w-9 p-0 font-normal aria-selected:opacity-100',
      '[data-today]:bg-accent [data-today]:text-accent-foreground',
      '[data-selected]:bg-primary [data-selected]:text-primary-foreground [data-selected]:hover:bg-primary [data-selected]:hover:text-primary-foreground [data-selected]:focus:bg-primary [data-selected]:focus:text-primary-foreground',
      '[data-outside-view]:text-muted-foreground [data-outside-view]:opacity-50 [data-outside-view]:aria-selected:bg-accent/50 [data-outside-view]:aria-selected:text-muted-foreground [data-outside-view]:aria-selected:opacity-30',
      'disabled:text-muted-foreground disabled:opacity-50',
      'unavailable:text-destructive-foreground unavailable:line-through',
      props.class,
    )"
    v-bind="forwardedProps"
  >
    <slot />
  </CalendarCellTrigger>
</template>
