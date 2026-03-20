<template>
  <button
    type="button"
    :class="[
      'px-4 py-2 rounded-xl text-sm font-bold transition-colors',
      isActive ? 'bg-indigo-600 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
    ]"
    @click="setValue(propsValue)"
    v-bind="attrs"
  >
    <slot />
  </button>
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
  throw new Error('TabsTrigger must be used inside Tabs')
}

const { value, setValue } = context

const isActive = computed(() => value.value === props.value)

const propsValue = props.value
</script>
