<template>
  <ScrollAreaRoot :class="cn('relative overflow-hidden', $attrs.class)">
    <ScrollAreaViewport class="h-full w-full rounded-[inherit]">
      <slot />
    </ScrollAreaViewport>
    <ScrollAreaScrollbar
      class="flex touch-none select-none transition-colors"
      orientation="vertical"
    >
      <ScrollAreaThumb class="relative flex-1 rounded-full bg-slate-200" />
    </ScrollAreaScrollbar>
    <ScrollAreaCorner />
  </ScrollAreaRoot>
</template>

<script setup lang="ts">
import {
  ScrollAreaRoot,
  ScrollAreaViewport,
  ScrollAreaScrollbar,
  ScrollAreaThumb,
  ScrollAreaCorner,
} from 'radix-vue'
import { cn } from '~/lib/utils'
</script>
