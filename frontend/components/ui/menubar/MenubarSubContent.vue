<script setup lang="ts">
import type { MenubarSubContentProps } from 'reka-ui'
import type { HTMLAttributes } from 'vue'
import { reactiveOmit } from '@vueuse/core'
import { MenubarPortal, MenubarSubContent, useForwardProps } from 'reka-ui'
import { cn } from '~/lib/utils'

const props = withDefaults(
  defineProps<MenubarSubContentProps & { class?: HTMLAttributes['class'] }>(),
  { sideOffset: 6 }
)
const delegatedProps = reactiveOmit(props, 'class')
const forwarded = useForwardProps(delegatedProps)
</script>

<template>
  <MenubarPortal>
    <MenubarSubContent
      v-bind="forwarded"
      :class="cn('z-50 min-w-48 overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md data-[state=open]:animate-in data-[state=closed]:animate-out', props.class)"
    >
      <slot />
    </MenubarSubContent>
  </MenubarPortal>
</template>
