<script setup lang="ts">
import type { NavigationMenuContentProps } from 'reka-ui'
import type { HTMLAttributes } from 'vue'
import { reactiveOmit } from '@vueuse/core'
import { NavigationMenuContent, useForwardProps } from 'reka-ui'
import { cn } from '~/lib/utils'

const props = defineProps<NavigationMenuContentProps & { class?: HTMLAttributes['class'] }>()
const delegatedProps = reactiveOmit(props, 'class')
const forwarded = useForwardProps(delegatedProps)
</script>

<template>
  <NavigationMenuContent
    v-bind="forwarded"
    :class="cn('absolute left-0 top-full z-50 mt-1 w-max min-w-[220px] data-[motion^=from-]:animate-in data-[motion^=to-]:animate-out data-[motion^=from-]:fade-in data-[motion^=to-]:fade-out data-[motion=from-end]:slide-in-from-right-2 data-[motion=from-start]:slide-in-from-left-2 data-[motion=to-end]:slide-out-to-right-2 data-[motion=to-start]:slide-out-to-left-2', props.class)"
  >
    <slot />
  </NavigationMenuContent>
</template>
