<script setup lang="ts">
import { CalendarGridBody, type CalendarGridBodyProps, useForwardProps } from 'reka-ui'

const props = defineProps<CalendarGridBodyProps>()
const forwardedProps = useForwardProps(props)
</script>

<template>
  <CalendarGridBody v-bind="forwardedProps">
    <slot />
  </CalendarGridBody>
</template>
