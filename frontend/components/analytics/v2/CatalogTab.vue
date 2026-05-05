<template>
  <div class="space-y-6">
    <div class="flex gap-1 rounded-2xl border border-slate-100 bg-slate-50 p-1">
      <button
        v-for="tab in subtabs"
        :key="tab.key"
        type="button"
        class="flex-1 rounded-xl px-4 py-2 text-sm font-bold transition-all"
        :class="activeSubtab === tab.key
          ? 'bg-white text-slate-900 shadow-sm'
          : 'text-slate-400 hover:text-slate-600'"
        @click="activeSubtab = tab.key"
      >
        {{ tab.label }}
      </button>
    </div>

    <template v-if="activeSubtab === 'services'">
      <slot name="services" />
    </template>
    <template v-else>
      <slot name="commodities" />
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

type SubtabKey = 'services' | 'commodities'
const subtabs: { key: SubtabKey; label: string }[] = [
  { key: 'services', label: 'Услуги' },
  { key: 'commodities', label: 'Товары' },
]

const activeSubtab = ref<SubtabKey>('services')
</script>
