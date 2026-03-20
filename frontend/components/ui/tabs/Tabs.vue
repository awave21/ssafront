<template>
  <div :class="['space-y-4', className]" v-bind="attrs">
    <slot />
  </div>
</template>

<script setup lang="ts">
import { provide, ref, watch, useAttrs } from 'vue'
import { tabsContextKey, type TabsContext } from './context'

const props = defineProps<{
  value?: string
  defaultValue?: string
  className?: string
}>()

const emit = defineEmits<{
  (e: 'update:value', value: string): void
}>()

const attrs = useAttrs()

const internalValue = ref(props.value ?? props.defaultValue ?? 'services')

watch(
  () => props.value,
  (value) => {
    if (value) {
      internalValue.value = value
    }
  }
)

const setValue = (next: string) => {
  if (internalValue.value === next) return
  internalValue.value = next
  emit('update:value', next)
}

const context: TabsContext = {
  value: internalValue,
  setValue,
}

provide(tabsContextKey, context)
</script>
