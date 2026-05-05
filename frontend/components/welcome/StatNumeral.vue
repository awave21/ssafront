<script setup lang="ts">
import { computed } from 'vue'
import { useCountUp } from '~/composables/useCountUp'

interface Props {
  value: number
  prefix?: string
  suffix?: string
  decimals?: number
  size?: 'lg' | 'xl' | '2xl'
}

const props = withDefaults(defineProps<Props>(), {
  prefix: '',
  suffix: '',
  decimals: 0,
  size: 'lg',
})

const { value: animated, el } = useCountUp({
  to: props.value,
  decimals: props.decimals,
  durationMs: 1400,
})

const display = computed(() => {
  const n = animated.value
  if (props.decimals > 0) return n.toFixed(props.decimals)
  return Math.round(n).toString()
})

const sizeClass = computed(() => {
  if (props.size === '2xl') return 'text-[clamp(96px,14vw,184px)]'
  if (props.size === 'xl') return 'text-[clamp(72px,10vw,128px)]'
  return 'text-[clamp(56px,7vw,96px)]'
})
</script>

<template>
  <span ref="el" :class="['numeral inline-flex items-baseline', sizeClass]">
    <span v-if="prefix" class="numeral text-[0.55em] mr-0.5 align-baseline">{{ prefix }}</span>
    <span>{{ display }}</span>
    <span v-if="suffix" class="numeral text-[0.45em] ml-1">{{ suffix }}</span>
  </span>
</template>
