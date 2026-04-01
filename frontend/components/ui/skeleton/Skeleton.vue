<script setup lang="ts">
import { computed } from 'vue'
import type { HTMLAttributes } from 'vue'
import { cn } from '~/lib/utils'

interface Props {
  class?: HTMLAttributes['class']
  /** Диагональная «волна» (аналитика, плейсхолдеры карточек) */
  diagonalShimmer?: boolean
  /** Сдвиг фазы анимации между соседними карточками, мс */
  shimmerDelayMs?: number
}

const props = defineProps<Props>()

const shimmerStyle = computed(() => {
  if (!props.diagonalShimmer) return undefined
  const d = props.shimmerDelayMs
  if (d == null || d <= 0) return undefined
  return { animationDelay: `${d}ms` }
})
</script>

<template>
  <div
    :class="
      cn(
        props.diagonalShimmer
          ? 'relative isolate overflow-hidden'
          : 'animate-pulse rounded-md bg-muted',
        props.class,
      )
    "
  >
    <template v-if="props.diagonalShimmer">
      <span class="pointer-events-none absolute inset-0 z-0 bg-slate-100" aria-hidden="true" />
      <span
        class="pointer-events-none absolute -left-[25%] top-0 z-[1] h-full w-[60%] skew-x-[-17deg] bg-[linear-gradient(106deg,transparent_0%,rgba(255,255,255,0.08)_38%,rgba(255,255,255,0.92)_50%,rgba(255,255,255,0.08)_62%,transparent_100%)] will-change-transform motion-safe:animate-analytics-shimmer-wave motion-reduce:hidden"
        :style="shimmerStyle"
        aria-hidden="true"
      />
    </template>
  </div>
</template>
