<template>
  <div class="w-full px-4 py-10 flex flex-col gap-8 bg-[#f8fafc] min-h-screen">
    <div class="max-w-7xl mx-auto w-full space-y-8">
      <AnalyticsDashboardSection
        :filters="filters"
        :agents="agentOptions"
        :channels="availableChannels"
        :tags="availableTags"
        :resources="analyticsResources"
        :loading="dashboardContentBusy"
        @update-filters="updateFilters"
        @refresh="refreshAll"
        @reset="resetFilters"
      >
        <MotivationTab
          :overview="motivation.overview.value"
          :pending="motivation.pending.value"
          :save-rule="motivation.saveRule"
          @open-detail="openDetail"
        />
      </AnalyticsDashboardSection>

      <StaffDetailDrawer
        :resource-id="selectedMember?.resource_external_id ?? null"
        :agent-id="filters.agentId"
        :date-from="filters.dateFrom"
        :date-to="filters.dateTo"
        :timezone="filters.timezone"
        :motivation="selectedMember"
        @close="selectedMember = null"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
definePageMeta({
  middleware: 'auth',
})

import { computed, onMounted, ref } from 'vue'

import AnalyticsDashboardSection from '~/components/analytics/AnalyticsDashboardSection.vue'
import MotivationTab from '~/components/analytics/v2/MotivationTab.vue'
import StaffDetailDrawer from '~/components/analytics/v2/StaffDetailDrawer.vue'

import { useDashboardData } from '~/composables/useDashboardData'
import { useMotivationData } from '~/composables/useMotivationData'
import type { MotivationMember } from '~/types/analytics'

const { pageTitle } = useLayoutState()

const {
  pending,
  filters,
  agentOptions,
  availableChannels,
  availableTags,
  analyticsResources,
  isBootstrapping,
  initialize,
  refresh,
  updateFilters,
  resetFilters,
} = useDashboardData()

const dashboardContentBusy = computed(() => pending.value || isBootstrapping.value)

const motivation = useMotivationData(filters)

const selectedMember = ref<MotivationMember | null>(null)
const openDetail = (member: MotivationMember) => { selectedMember.value = member }

const refreshAll = async () => {
  await Promise.allSettled([refresh(), motivation.fetchAll()])
}

onMounted(() => {
  pageTitle.value = 'Мотивация'
  void initialize()
})
</script>
