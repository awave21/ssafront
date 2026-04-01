<template>
  <div class="w-full px-4 py-10 flex flex-col gap-8 bg-[#f8fafc] min-h-screen">
    <div class="max-w-7xl mx-auto w-full space-y-10">
      <div
        v-if="error && activeTab === 'dashboard'"
        class="rounded-3xl border border-rose-100 bg-rose-50/50 p-4 text-sm text-rose-600 flex items-center gap-3 shadow-sm"
      >
        <div class="h-2 w-2 rounded-full bg-rose-500 animate-pulse"></div>
        <span class="font-bold">{{ error }}</span>
      </div>

      <Tabs v-model:value="activeTab" class="w-full">
        <TabsList class="bg-white border border-slate-100 p-1.5 rounded-3xl shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] mb-10 h-14 w-fit">
          <TabsTrigger value="dashboard" class="rounded-2xl px-10 h-full data-[state=active]:bg-primary data-[state=active]:text-white data-[state=active]:shadow-lg data-[state=active]:shadow-primary/20 transition-all font-bold text-sm">
            Дашборд
          </TabsTrigger>
          <TabsTrigger value="services" class="rounded-2xl px-10 h-full data-[state=active]:bg-primary data-[state=active]:text-white data-[state=active]:shadow-lg data-[state=active]:shadow-primary/20 transition-all font-bold text-sm">
            Услуги
          </TabsTrigger>
          <TabsTrigger value="commodities" class="rounded-2xl px-10 h-full data-[state=active]:bg-primary data-[state=active]:text-white data-[state=active]:shadow-lg data-[state=active]:shadow-primary/20 transition-all font-bold text-sm">
            Товары
          </TabsTrigger>
        </TabsList>

        <TabsContent value="dashboard" class="outline-none">
          <AnalyticsDashboardSection
            :filters="filters"
            :agents="agentOptions"
            :channels="availableChannels"
            :tags="availableTags"
            :resources="analyticsResources"
            :loading="dashboardContentBusy || servicesPending"
            @update-filters="updateFilters"
            @refresh="refreshAll"
            @reset="resetAll"
          >
            <div class="space-y-12">
              <AnalyticsKpiGrid
                :overview="overview"
                :previous-overview="previousOverview"
                :timeseries="timeseries"
                :loading="dashboardContentBusy"
                :agent-id="filters.agentId"
                :date-from="filters.dateFrom"
                :date-to="filters.dateTo"
                :drill-timezone="filters.timezone"
                :drill-channel="filters.channel"
                :drill-client-tags="filters.clientTags"
                :drill-revenue-basis="filters.revenueBasis"
                :drill-payment-methods="filters.paymentMethods"
                :drill-revenue-categories="filters.revenueCategories"
                :drill-resource-external-id="filters.resourceExternalId"
              />
              <AnalyticsTimeseries :timeseries="timeseries" :loading="dashboardContentBusy" />
              <AnalyticsBreakdown
                :channel-breakdown="channelBreakdown"
                :tag-breakdown="tagBreakdown"
                :overview="overview"
                :loading="dashboardContentBusy"
              />
            </div>
          </AnalyticsDashboardSection>
        </TabsContent>

        <TabsContent value="services" class="space-y-10 outline-none">
          <AnalyticsDashboardSection
            :filters="filters"
            :agents="agentOptions"
            :channels="availableChannels"
            :tags="availableTags"
            :resources="analyticsResources"
            :loading="dashboardContentBusy || servicesPending"
            @update-filters="updateFilters"
            @refresh="refreshAll"
            @reset="resetAll"
          >
            <ServicesTableToolbar
              :resource-external-id="servicesQuery.resourceExternalId"
              :resources="servicesResources"
              :loading="servicesPending"
              @update-resource="updateServicesQuery"
              @export-current="exportServicesCurrent"
              @export-all="exportServicesAll"
            />

            <ServicesTotalsBar v-if="servicesTotals" :totals="servicesTotals" />

            <div class="grid grid-cols-1 gap-10">
              <CategoriesTopCards :items="servicesItems" :loading="servicesPending" />
              <ServicesTopCards :items="servicesItems" :loading="servicesPending" />
            </div>

            <ServicesMetricsTable
              :items="servicesItems"
              :loading="servicesPending"
              :error-message="servicesErrorMessage"
              :totals="servicesTotals"
              :total-items="servicesTotalItems"
              :current-page="servicesCurrentPage"
              :total-pages="servicesTotalPages"
              :sort-by="servicesQuery.sortBy"
              :sort-order="servicesQuery.sortOrder"
              @sort-change="setServicesSort"
              @page-change="setServicesPage"
              @retry="refreshServices"
            />
          </AnalyticsDashboardSection>
        </TabsContent>

        <TabsContent value="commodities" class="space-y-10 outline-none">
          <AnalyticsDashboardSection
            :filters="filters"
            :agents="agentOptions"
            :channels="availableChannels"
            :tags="availableTags"
            :resources="analyticsResources"
            :loading="dashboardContentBusy || commoditiesPending"
            @update-filters="updateFilters"
            @refresh="refreshAll"
            @reset="resetAll"
          >
            <ServicesTableToolbar
              :resource-external-id="commoditiesQuery.resourceExternalId"
              :resources="commoditiesResources"
              :loading="commoditiesPending"
              @update-resource="updateCommoditiesQuery"
              @export-current="exportCommoditiesCurrent"
              @export-all="exportCommoditiesAll"
            />

            <CommoditiesTotalsBar v-if="commoditiesTotals" :totals="commoditiesTotals" />

            <div class="grid grid-cols-1 gap-10">
              <CommodityCategoriesTopCards :items="commoditiesItems" :loading="commoditiesPending" />
              <CommoditiesTopCards :items="commoditiesItems" :loading="commoditiesPending" />
            </div>

            <CommoditiesMetricsTable
              :items="commoditiesItems"
              :loading="commoditiesPending"
              :error-message="commoditiesErrorMessage"
              :totals="commoditiesTotals"
              :total-items="commoditiesTotalItems"
              :current-page="commoditiesCurrentPage"
              :total-pages="commoditiesTotalPages"
              :sort-by="commoditiesQuery.sortBy"
              :sort-order="commoditiesQuery.sortOrder"
              @sort-change="setCommoditiesSort"
              @page-change="setCommoditiesPage"
              @retry="refreshCommodities"
            />
          </AnalyticsDashboardSection>
        </TabsContent>
      </Tabs>

      <div
        v-if="phase2Backlog.length"
        class="rounded-3xl border border-slate-100 bg-white/50 p-8 backdrop-blur-sm shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]"
      >
        <div class="flex flex-col gap-1 mb-6">
          <h3 class="text-sm font-black text-slate-900 uppercase tracking-widest">Следующий этап метрик</h3>
          <p class="text-xs font-medium text-slate-400">
            Эти показатели будут добавлены в ближайших обновлениях для более глубокого анализа.
          </p>
        </div>
        <div class="flex flex-wrap gap-2">
          <Badge
            v-for="item in phase2Backlog"
            :key="item"
            variant="secondary"
            class="bg-white text-slate-600 border border-slate-100 hover:bg-slate-50 transition-all px-4 py-2 rounded-xl text-xs font-bold shadow-sm"
          >
            {{ item }}
          </Badge>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
definePageMeta({
  middleware: 'auth',
})

import { computed, onMounted, ref } from 'vue'
import AnalyticsBreakdown from '~/components/analytics/AnalyticsBreakdown.vue'
import AnalyticsDashboardSection from '~/components/analytics/AnalyticsDashboardSection.vue'
import AnalyticsKpiGrid from '~/components/analytics/AnalyticsKpiGrid.vue'
import CommoditiesMetricsTable from '~/components/analytics/CommoditiesMetricsTable.vue'
import CommoditiesTotalsBar from '~/components/analytics/CommoditiesTotalsBar.vue'
import CommoditiesTopCards from '~/components/analytics/CommoditiesTopCards.vue'
import CommodityCategoriesTopCards from '~/components/analytics/CommodityCategoriesTopCards.vue'
import ServicesMetricsTable from '~/components/analytics/ServicesMetricsTable.vue'
import ServicesTableToolbar from '~/components/analytics/ServicesTableToolbar.vue'
import ServicesTopCards from '~/components/analytics/ServicesTopCards.vue'
import CategoriesTopCards from '~/components/analytics/CategoriesTopCards.vue'
import ServicesTotalsBar from '~/components/analytics/ServicesTotalsBar.vue'
import AnalyticsTimeseries from '~/components/analytics/AnalyticsTimeseries.vue'
import { Badge } from '~/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '~/components/ui/tabs'
import { useDashboardData } from '~/composables/useDashboardData'
import { useCommoditiesAnalyticsTable } from '~/composables/useCommoditiesAnalyticsTable'
import { useServicesAnalyticsTable } from '~/composables/useServicesAnalyticsTable'

const { pageTitle } = useLayoutState()
const activeTab = ref('dashboard')

const {
  pending,
  error,
  filters,
  agentOptions,
  availableChannels,
  availableTags,
  phase2Backlog,
  overview,
  previousOverview,
  timeseries,
  channelBreakdown,
  tagBreakdown,
  analyticsResources,
  isBootstrapping,
  initialize,
  refresh,
  updateFilters,
  resetFilters,
} = useDashboardData()

const dashboardContentBusy = computed(() => pending.value || isBootstrapping.value)

const {
  query: servicesQuery,
  pending: servicesPending,
  error: servicesError,
  items: servicesItems,
  totals: servicesTotals,
  totalItems: servicesTotalItems,
  currentPage: servicesCurrentPage,
  totalPages: servicesTotalPages,
  resources: servicesResources,
  refresh: refreshServices,
  setSort: setServicesSort,
  setPage: setServicesPage,
  updateQuery: updateServicesQuery,
  exportCurrentPageCsv: exportServicesCurrent,
  exportAllCsv: exportServicesAll,
} = useServicesAnalyticsTable(computed(() => filters.agentId), { syncFromDashboard: filters })

const {
  query: commoditiesQuery,
  pending: commoditiesPending,
  error: commoditiesError,
  items: commoditiesItems,
  totals: commoditiesTotals,
  totalItems: commoditiesTotalItems,
  currentPage: commoditiesCurrentPage,
  totalPages: commoditiesTotalPages,
  resources: commoditiesResources,
  refresh: refreshCommodities,
  setSort: setCommoditiesSort,
  setPage: setCommoditiesPage,
  updateQuery: updateCommoditiesQuery,
  exportCurrentPageCsv: exportCommoditiesCurrent,
  exportAllCsv: exportCommoditiesAll,
} = useCommoditiesAnalyticsTable(computed(() => filters.agentId), { syncFromDashboard: filters })

const refreshAll = async () => {
  await refresh()
  await refreshServices()
  await refreshCommodities()
}

const resetAll = async () => {
  updateServicesQuery({ resourceExternalId: null })
  updateCommoditiesQuery({ resourceExternalId: null })
  await resetFilters()
}

const servicesErrorMessage = computed(() => {
  const value = servicesError.value as any
  if (!value) return null
  return value?.data?.message || value?.message || 'Не удалось загрузить таблицу услуг'
})

const commoditiesErrorMessage = computed(() => {
  const value = commoditiesError.value as any
  if (!value) return null
  return value?.data?.message || value?.message || 'Не удалось загрузить таблицу товаров'
})

onMounted(() => {
  pageTitle.value = 'Аналитика'
  void initialize()
})
</script>
