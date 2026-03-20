<template>
  <div v-show="isActive" v-bind="attrs">
    <slot />
  </div>
</template>

<script setup lang="ts">
import { computed, inject, useAttrs } from 'vue'
import { tabsContextKey, type TabsContext } from './context'

const props = defineProps<{
  value: string
}>()

const attrs = useAttrs()

const context = inject<TabsContext>(tabsContextKey)

if (!context) {
  throw new Error('TabsContent must be used inside Tabs')
}

const { value } = context

const isActive = computed(() => value.value === props.value)
</script>
