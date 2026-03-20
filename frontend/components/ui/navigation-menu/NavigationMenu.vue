<script setup lang="ts">
import type { NavigationMenuRootEmits, NavigationMenuRootProps } from 'reka-ui'
import type { HTMLAttributes } from 'vue'
import { reactiveOmit } from '@vueuse/core'
import { NavigationMenuRoot, useForwardPropsEmits } from 'reka-ui'
import { cn } from '~/lib/utils'
import NavigationMenuViewport from './NavigationMenuViewport.vue'

const props = withDefaults(
  defineProps<NavigationMenuRootProps & { class?: HTMLAttributes['class'], viewport?: boolean }>(),
  {
    viewport: true
  }
)
const emits = defineEmits<NavigationMenuRootEmits>()

const delegatedProps = reactiveOmit(props, 'class', 'viewport')
const forwarded = useForwardPropsEmits(delegatedProps, emits)
</script>

<template>
  <NavigationMenuRoot
    v-bind="forwarded"
    :class="cn('relative z-10 flex max-w-max flex-1 items-center justify-center', props.class)"
  >
    <slot />
    <NavigationMenuViewport v-if="props.viewport" />
  </NavigationMenuRoot>
</template>
