<script setup lang="ts">
import { CalendarNextButton, type CalendarNextButtonProps, useForwardProps } from 'reka-ui'
import { computed, type HTMLAttributes } from 'vue'
import { ChevronRight } from 'lucide-vue-next'
import { buttonVariants } from '~/components/ui/button'
import { cn } from '~/lib/utils'

const props = defineProps<CalendarNextButtonProps & { class?: HTMLAttributes['class'] }>()

const delegatedProps = computed(() => {
  const { class: _, ...delegated } = props

  return delegated
})

const forwardedProps = useForwardProps(delegatedProps)
</script>

<template>
  <CalendarNextButton
    :class="cn(
      buttonVariants({ variant: 'outline' }),
      'h-7 w-7 bg-transparent p-0 opacity-50 hover:opacity-100',
      props.class,
    )"
    v-bind="forwardedProps"
  >
    <slot>
      <ChevronRight class="h-4 w-4" />
    </slot>
  </CalendarNextButton>
</template>
