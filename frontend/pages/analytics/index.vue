<template>
  <div class="w-full px-4 py-10 flex flex-col gap-8 bg-[#f8fafc] min-h-screen">
    <div class="max-w-7xl mx-auto w-full space-y-8">

      <!-- Filter bar (shared across all tabs) -->
      <AnalyticsDashboardSection
        :filters="filters"
        :agents="agentOptions"
        :channels="availableChannels"
        :tags="availableTags"
        :resources="analyticsResources"
        :loading="dashboardContentBusy"
        @update-filters="updateFilters"
        @refresh="refreshAll"
        @reset="resetAll"
      >
        <!-- Tab nav -->
        <Tabs v-model:value="activeTab" class="w-full">
          <TabsList class="bg-white border border-slate-100 p-1.5 rounded-3xl shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] mb-8 h-14 flex w-fit gap-1">
            <TabsTrigger
              v-for="tab in tabs"
              :key="tab.key"
              :value="tab.key"
              class="rounded-2xl px-6 h-full data-[state=active]:bg-primary data-[state=active]:text-white data-[state=active]:shadow-lg data-[state=active]:shadow-primary/20 transition-all font-bold text-sm flex items-center gap-2"
            >
              <component :is="tab.icon" class="h-4 w-4" />
              {{ tab.label }}
            </TabsTrigger>
          </TabsList>

          <!-- Обзор -->
          <TabsContent value="overview" class="outline-none">
            <OverviewTab
              :ai-reco="v2.aiReco.value"
              :ai-reco-loading="v2.aiRecoLoading.value"
              :insights="v2.insights.value"
              :funnel="v2.funnel.value"
              :staff="v2.staff.value"
              :overview="overview"
              :agent-id="filters.agentId"
              :filters="filters"
              @refresh-ai="handleRefreshAi"
              @go-to-tab="activeTab = $event"
              @navigate="navigateUrl"
            >
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
            </OverviewTab>
          </TabsContent>

          <!-- Сотрудники -->
          <TabsContent value="staff" class="outline-none">
            <StaffTab
              :data="v2.staff.value"
              :loading="v2.pending.value"
              @open-detail="openStaffDetail"
            />
          </TabsContent>

          <!-- Менеджеры -->
          <TabsContent value="managers" class="outline-none">
            <ManagersTab
              :overview="v2.managers.value"
              :timeline="v2.managersTimeline.value"
              :loading="v2.pending.value"
            />
          </TabsContent>

          <!-- Бот -->
          <TabsContent value="bot" class="outline-none">
            <BotTab
              :data="v2.botHealth.value"
              :loading="v2.pending.value"
            />
          </TabsContent>

          <!-- Мотивация -->
          <TabsContent value="motivation" class="outline-none">
            <MotivationTab
              :overview="motivation.overview.value"
              :pending="motivation.pending.value"
              :save-rule="motivation.saveRule"
            />
          </TabsContent>

          <!-- Каталог -->
          <TabsContent value="catalog" class="outline-none">
            <CatalogTab>
              <template #services>
                <div class="space-y-8">
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
                </div>
              </template>
              <template #commodities>
                <div class="space-y-8">
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
                </div>
              </template>
            </CatalogTab>
          </TabsContent>
        </Tabs>
      </AnalyticsDashboardSection>

      <!-- Staff detail drawer -->
      <StaffDetailDrawer
        :resource-id="selectedStaffId"
        :agent-id="filters.agentId"
        :date-from="filters.dateFrom"
        :date-to="filters.dateTo"
        :timezone="filters.timezone"
        @close="selectedStaffId = null"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
definePageMeta({
  middleware: 'auth',
})

import { computed, onMounted, ref } from 'vue'
import { LayoutDashboard, Users, MessageSquare, Bot, BookOpen, Award } from 'lucide-vue-next'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '~/components/ui/tabs'

import AnalyticsBreakdown from '~/components/analytics/AnalyticsBreakdown.vue'
import AnalyticsDashboardSection from '~/components/analytics/AnalyticsDashboardSection.vue'
import AnalyticsKpiGrid from '~/components/analytics/AnalyticsKpiGrid.vue'
import AnalyticsTimeseries from '~/components/analytics/AnalyticsTimeseries.vue'
import CategoriesTopCards from '~/components/analytics/CategoriesTopCards.vue'
import CommoditiesMetricsTable from '~/components/analytics/CommoditiesMetricsTable.vue'
import CommoditiesTotalsBar from '~/components/analytics/CommoditiesTotalsBar.vue'
import CommoditiesTopCards from '~/components/analytics/CommoditiesTopCards.vue'
import CommodityCategoriesTopCards from '~/components/analytics/CommodityCategoriesTopCards.vue'
import ServicesMetricsTable from '~/components/analytics/ServicesMetricsTable.vue'
import ServicesTableToolbar from '~/components/analytics/ServicesTableToolbar.vue'
import ServicesTopCards from '~/components/analytics/ServicesTopCards.vue'
import ServicesTotalsBar from '~/components/analytics/ServicesTotalsBar.vue'

import OverviewTab from '~/components/analytics/v2/OverviewTab.vue'
import StaffTab from '~/components/analytics/v2/StaffTab.vue'
import ManagersTab from '~/components/analytics/v2/ManagersTab.vue'
import BotTab from '~/components/analytics/v2/BotTab.vue'
import CatalogTab from '~/components/analytics/v2/CatalogTab.vue'
import StaffDetailDrawer from '~/components/analytics/v2/StaffDetailDrawer.vue'
import MotivationTab from '~/components/analytics/v2/MotivationTab.vue'

import { useDashboardData } from '~/composables/useDashboardData'
import { useCommoditiesAnalyticsTable } from '~/composables/useCommoditiesAnalyticsTable'
import { useServicesAnalyticsTable } from '~/composables/useServicesAnalyticsTable'
import { useAnalyticsV2Data } from '~/composables/useAnalyticsV2Data'
import { useMotivationData } from '~/composables/useMotivationData'

const { pageTitle } = useLayoutState()
const activeTab = ref('overview')

const tabs = [
  { key: 'overview', label: 'Обзор', icon: LayoutDashboard },
  { key: 'staff', label: 'Сотрудники', icon: Users },
  { key: 'managers', label: 'Менеджеры', icon: MessageSquare },
  { key: 'bot', label: 'Бот', icon: Bot },
  { key: 'catalog', label: 'Каталог', icon: BookOpen },
  { key: 'motivation', label: 'Мотивация', icon: Award },
]

const {
  pending,
  filters,
  agentOptions,
  availableChannels,
  availableTags,
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

const v2 = useAnalyticsV2Data(filters)
const motivation = useMotivationData(filters)

const selectedStaffId = ref<number | null>(null)
const openStaffDetail = (id: number) => { selectedStaffId.value = id }

const handleRefreshAi = () => v2.fetchAiReco(true)
const navigateUrl = (url: string) => { window.location.href = url }

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
  await Promise.allSettled([refresh(), v2.fetchAll(), motivation.fetchAll(), refreshServices(), refreshCommodities()])
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
