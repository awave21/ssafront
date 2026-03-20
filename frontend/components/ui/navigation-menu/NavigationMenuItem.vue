<script setup lang="ts">
import type { NavigationMenuItemProps } from 'reka-ui'
import { NavigationMenuItem, useForwardProps } from 'reka-ui'

const props = defineProps<NavigationMenuItemProps>()
const forwarded = useForwardProps(props)
</script>

<template>
  <NavigationMenuItem v-bind="forwarded">
    <slot />
  </NavigationMenuItem>
</template>
