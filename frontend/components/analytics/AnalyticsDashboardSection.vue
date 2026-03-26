<template>
  <div class="space-y-10">
    <AnalyticsFiltersBar
      :filters="filters"
      :agents="agents"
      :channels="channels"
      :tags="tags"
      :loading="loading"
      @update-filters="value => emit('update-filters', value)"
      @refresh="emit('refresh')"
      @reset="emit('reset')"
    />
    <slot />
  </div>
</template>

<script setup lang="ts">
import AnalyticsFiltersBar from '~/components/analytics/AnalyticsFiltersBar.vue'
import type {
  AnalyticsAgentOption,
  AnalyticsFilterOption,
  AnalyticsFilters,
} from '~/types/analytics'

defineProps<{
  filters: AnalyticsFilters
  agents: AnalyticsAgentOption[]
  channels: AnalyticsFilterOption[]
  tags: AnalyticsFilterOption[]
  loading: boolean
}>()

const emit = defineEmits<{
  (event: 'update-filters', value: Partial<AnalyticsFilters>): void
  (event: 'refresh'): void
  (event: 'reset'): void
}>()
</script>
