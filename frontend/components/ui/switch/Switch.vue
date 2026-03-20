<template>
  <SwitchRoot
    :checked="modelValue"
    @update:checked="$emit('update:modelValue', $event)"
    :disabled="disabled"
    :class="[
      'peer inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors',
      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 focus-visible:ring-offset-2',
      'disabled:cursor-not-allowed disabled:opacity-50',
      modelValue ? 'bg-emerald-500' : 'bg-slate-200',
      className
    ]"
  >
    <SwitchThumb
      :class="[
        'pointer-events-none block h-4 w-4 rounded-full bg-white shadow-lg ring-0 transition-transform',
        modelValue ? 'translate-x-5' : 'translate-x-0.5'
      ]"
    />
  </SwitchRoot>
</template>

<script setup lang="ts">
import { SwitchRoot, SwitchThumb } from 'radix-vue'

defineProps<{
  modelValue?: boolean
  disabled?: boolean
  className?: string
}>()

defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()
</script>
