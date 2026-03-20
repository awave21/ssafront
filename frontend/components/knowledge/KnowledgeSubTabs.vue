<template>
  <div class="flex items-center gap-1 border-b border-slate-200 mb-6">
    <button
      v-for="tab in tabs"
      :key="tab.id"
      @click="$emit('update:modelValue', tab.id)"
      class="px-4 py-2.5 text-sm font-medium transition-all relative"
      :class="[
        modelValue === tab.id
          ? 'text-indigo-600'
          : 'text-slate-500 hover:text-slate-700'
      ]"
    >
      <span class="flex items-center gap-2">
        {{ tab.label }}
        <span 
          v-if="tab.count !== undefined"
          class="text-xs px-1.5 py-0.5 rounded-full"
          :class="[
            modelValue === tab.id 
              ? 'bg-indigo-100 text-indigo-600' 
              : 'bg-slate-100 text-slate-500'
          ]"
        >
          {{ tab.count }}
        </span>
      </span>
      <div
        v-if="modelValue === tab.id"
        class="absolute bottom-0 left-0 right-0 h-0.5 bg-indigo-600"
      ></div>
    </button>
  </div>
</template>

<script setup lang="ts">
type SubTab = {
  id: string
  label: string
  count?: number
}

defineProps<{
  modelValue: string
  tabs: SubTab[]
}>()

defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()
</script>
