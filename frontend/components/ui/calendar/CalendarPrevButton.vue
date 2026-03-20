<script setup lang="ts">
import { CalendarPrevButton, type CalendarPrevButtonProps, useForwardProps } from 'reka-ui'
import { computed, type HTMLAttributes } from 'vue'
import { ChevronLeft } from 'lucide-vue-next'
import { buttonVariants } from '~/components/ui/button'
import { cn } from '~/lib/utils'

const props = defineProps<CalendarPrevButtonProps & { class?: HTMLAttributes['class'] }>()

const delegatedProps = computed(() => {
  const { class: _, ...delegated } = props

  return delegated
})

const forwardedProps = useForwardProps(delegatedProps)
</script>

<template>
  <CalendarPrevButton
    :class="cn(
      buttonVariants({ variant: 'outline' }),
      'h-7 w-7 bg-transparent p-0 opacity-50 hover:opacity-100',
      props.class,
    )"
    v-bind="forwardedProps"
  >
    <slot>
      <ChevronLeft class="h-4 w-4" />
    </slot>
  </CalendarPrevButton>
</template>
