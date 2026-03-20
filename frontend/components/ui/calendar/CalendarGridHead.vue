<script setup lang="ts">
import { CalendarGridHead, type CalendarGridHeadProps, useForwardProps } from 'reka-ui'

const props = defineProps<CalendarGridHeadProps>()
const forwardedProps = useForwardProps(props)
</script>

<template>
  <CalendarGridHead v-bind="forwardedProps">
    <slot />
  </CalendarGridHead>
</template>
