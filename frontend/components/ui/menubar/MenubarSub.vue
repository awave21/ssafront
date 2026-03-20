<script setup lang="ts">
import type { MenubarSubProps } from 'reka-ui'
import { MenubarSub, useForwardProps } from 'reka-ui'

const props = defineProps<MenubarSubProps>()
const forwarded = useForwardProps(props)
</script>

<template>
  <MenubarSub v-bind="forwarded">
    <slot />
  </MenubarSub>
</template>
