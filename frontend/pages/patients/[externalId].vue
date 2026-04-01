<template>
  <div class="min-h-screen w-full min-w-0 bg-[#f8fafc]">
    <div class="w-full min-w-0 max-w-full px-3 py-6 sm:px-4 sm:py-8 lg:px-3 lg:py-10">
      <PatientInvalidLinkAlert v-if="!agentId || externalIdNum === null" />

      <template v-else>
        <PatientDetailLoadError v-if="loadError" :message="loadError" />

        <PatientDetailHeader
          :display-name="displayName"
          :external-id-label="externalIdLabel"
          :loading="pending && !client"
          @back="goBack"
        />

        <PatientDetailSkeleton v-if="pending && !client" />

        <template v-else-if="client">
          <div
            class="grid min-w-0 gap-6 xl:grid-cols-[minmax(0,340px)_minmax(0,1fr)] xl:items-start"
          >
            <div class="flex min-w-0 flex-col gap-5">
              <PatientProfileCard
                :display-name="displayName"
                :initials="initials"
                :external-id-label="externalIdLabel"
                :badges="profileBadges"
                :contacts="contactRows"
              />
            </div>

            <div class="flex min-w-0 flex-col gap-6">
              <PatientMetricsCards
                :revenue-rub="revenueRub"
                :visits-count-display="visitsCountDisplay"
                :next-visit="nextVisitSummary"
              />
              <PatientDetailTabsPanel
                v-model="activeTab"
                v-model:expand-visits="showAllVisits"
                :tabs="tabs"
                :visits-pending="visitsPending"
                :sorted-visits="sortedVisits"
                :preview-limit="visitPreviewLimit"
              />
            </div>
          </div>
        </template>

        <PatientNotFoundCard v-else-if="!pending" @back="goBack" />
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import PatientDetailHeader from '~/components/patients/PatientDetailHeader.vue'
import PatientDetailLoadError from '~/components/patients/PatientDetailLoadError.vue'
import PatientDetailSkeleton from '~/components/patients/PatientDetailSkeleton.vue'
import PatientDetailTabsPanel from '~/components/patients/PatientDetailTabsPanel.vue'
import PatientInvalidLinkAlert from '~/components/patients/PatientInvalidLinkAlert.vue'
import PatientMetricsCards from '~/components/patients/PatientMetricsCards.vue'
import PatientNotFoundCard from '~/components/patients/PatientNotFoundCard.vue'
import PatientProfileCard from '~/components/patients/PatientProfileCard.vue'
import { usePatientDetail } from '~/composables/usePatientDetail'
import { useLayoutState } from '~/composables/useLayoutState'
import { routerPushSafe } from '~/utils/routerSafe'
import type { PatientDetailTabId } from '~/utils/patientDetailFormat'

definePageMeta({
  middleware: 'auth',
})

const route = useRoute()
const router = useRouter()
const { pageTitle } = useLayoutState()

const visitPreviewLimit = 5
const showAllVisits = ref(false)
const activeTab = ref<PatientDetailTabId>('visits')

const agentId = computed(() => {
  const q = route.query.agent
  if (typeof q === 'string' && q.length > 0) return q
  if (Array.isArray(q) && typeof q[0] === 'string' && q[0].length > 0) return q[0]
  return null
})

const externalIdNum = computed(() => {
  const p = route.params.externalId
  const s = Array.isArray(p) ? p[0] : p
  const n = parseInt(String(s ?? ''), 10)
  return Number.isFinite(n) ? n : null
})

const {
  client,
  pending,
  visitsPending,
  loadError,
  displayName,
  initials,
  externalIdLabel,
  revenueRub,
  visitsCountDisplay,
  sortedVisits,
  nextVisitSummary,
  tabs,
  profileBadges,
  contactRows,
} = usePatientDetail(agentId, externalIdNum)

watch(externalIdNum, () => {
  showAllVisits.value = false
  activeTab.value = 'visits'
})

const goBack = () => {
  if (agentId.value) void routerPushSafe(router, { path: '/patients', query: { agent: agentId.value } })
  else void routerPushSafe(router, '/patients')
}

watch(
  client,
  (c) => {
    if (c) {
      const n = c.name?.trim()
      pageTitle.value = n ? n : 'Без имени'
    } else pageTitle.value = 'Пациент'
  },
  { immediate: true },
)
</script>
