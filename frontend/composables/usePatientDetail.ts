import type { Ref } from 'vue'
import { computed, ref, watch } from 'vue'
import { usePatientsApi } from '~/composables/usePatientsApi'
import type { SqnsClientCachedVisitItem, SqnsClientListItem } from '~/types/patient-directory'
import { getReadableErrorMessage } from '~/utils/api-errors'
import {
  buildContactRows,
  buildPatientDetailTabs,
  buildProfileBadges,
  computeNextVisitSummary,
  initialsFromName,
  sortVisitsForDisplay,
  toRevenueNumber,
} from '~/utils/patientDetailFormat'

export const usePatientDetail = (agentId: Ref<string | null>, externalIdNum: Ref<number | null>) => {
  const { getClients, getClientCachedVisits } = usePatientsApi()

  const client = ref<SqnsClientListItem | null>(null)
  const visits = ref<SqnsClientCachedVisitItem[]>([])
  const pending = ref(false)
  const visitsPending = ref(false)
  const loadError = ref('')

  const displayName = computed(() => {
    const n = client.value?.name?.trim()
    return n ? n : 'Без имени'
  })

  const initials = computed(() => initialsFromName(client.value?.name))

  const externalIdLabel = computed(() =>
    externalIdNum.value != null ? `PT-${externalIdNum.value}` : '—',
  )

  const revenueRub = computed(() => toRevenueNumber(client.value?.total_arrival))

  const visitsCountDisplay = computed(() =>
    client.value?.visits_count != null ? String(client.value.visits_count) : '0',
  )

  const sortedVisits = computed(() => sortVisitsForDisplay(visits.value))

  const nextVisitSummary = computed(() =>
    computeNextVisitSummary(sortedVisits.value, visitsPending.value),
  )

  const tabs = computed(() => buildPatientDetailTabs(sortedVisits.value.length))

  const profileBadges = computed(() => (client.value ? buildProfileBadges(client.value) : []))

  const contactRows = computed(() => (client.value ? buildContactRows(client.value) : []))

  async function loadPatient() {
    loadError.value = ''
    client.value = null
    visits.value = []
    if (!agentId.value || externalIdNum.value === null) {
      pending.value = false
      visitsPending.value = false
      return
    }

    pending.value = true
    visitsPending.value = true
    try {
      const search = `PT-${externalIdNum.value}`
      const res = await getClients(agentId.value, {
        search,
        limit: 20,
        offset: 0,
        sort_by: 'external_id',
        sort_order: 'asc',
      })
      const found = res.clients.find((c) => c.external_id === externalIdNum.value) ?? null
      client.value = found
      if (!found) {
        visits.value = []
        return
      }
      const vr = await getClientCachedVisits(agentId.value, externalIdNum.value, 100)
      visits.value = vr.visits
    } catch (e) {
      loadError.value = getReadableErrorMessage(e, 'Не удалось загрузить данные пациента')
      client.value = null
      visits.value = []
    } finally {
      pending.value = false
      visitsPending.value = false
    }
  }

  watch(
    () => [agentId.value, externalIdNum.value] as const,
    () => {
      void loadPatient()
    },
    { immediate: true },
  )

  return {
    client,
    visits,
    pending,
    visitsPending,
    loadError,
    loadPatient,
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
  }
}
