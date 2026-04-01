import { useApiFetch } from '~/composables/useApiFetch'
import type {
  PatientsQuery,
  PatientsVisitCohort,
  SqnsClientCachedVisitsResponse,
  SqnsClientsListResponse,
} from '~/types/patient-directory'

const VISIT_COHORTS = new Set<string>([
  'primary_bookings',
  'primary_arrived',
  'repeat_bookings',
  'repeat_arrived',
  'all_bookings',
  'all_arrived',
])

export const usePatientsApi = () => {
  const apiFetch = useApiFetch()

  const getClients = async (
    agentId: string,
    query: Partial<PatientsQuery>,
  ): Promise<SqnsClientsListResponse> => {
    const q: Record<string, string | number | string[]> = {
      limit: query.limit ?? 50,
      offset: query.offset ?? 0,
      sort_by: query.sort_by ?? 'visits_count',
      sort_order: query.sort_order ?? 'desc',
    }
    const s = query.search?.trim()
    if (s) q.search = s
    const ct = query.client_type?.trim()
    if (ct) q.client_type = ct
    const vf = query.visit_date_from?.trim()
    const vt = query.visit_date_to?.trim()
    const vc = query.visit_cohort?.trim() as PatientsVisitCohort | ''
    if (vf && vt && vc && VISIT_COHORTS.has(vc)) {
      q.vf = vf
      q.vt = vt
      q.vc = vc
      const tz = query.timezone?.trim()
      if (tz) q.tz = tz
      const ch = query.channel?.trim()
      if (ch) q.channel = ch
      const tags = query.tags?.trim()
      if (tags) q.tags = tags
      if (query.revenue_basis === 'all') q.revenue_basis = 'all'
      if (query.paymentMethods?.length) q.payment_methods = query.paymentMethods
      if (query.revenueCategories?.length) q.revenue_categories = query.revenueCategories
      if (
        query.resource_external_id != null &&
        Number.isFinite(query.resource_external_id)
      ) {
        q.resource = query.resource_external_id
      }
    }
    return apiFetch<SqnsClientsListResponse>(`/agents/${agentId}/sqns/clients`, { query: q })
  }

  /** externalClientId — id клиента в SQNS (поле external_id), не UUID строки в БД */
  const getClientCachedVisits = async (
    agentId: string,
    externalClientId: number,
    limit = 40,
  ): Promise<SqnsClientCachedVisitsResponse> =>
    apiFetch<SqnsClientCachedVisitsResponse>(
      `/agents/${agentId}/sqns/clients/by-external/${externalClientId}/visits`,
      { query: { limit } },
    )

  return { getClients, getClientCachedVisits }
}
