import { useApiFetch } from '~/composables/useApiFetch'
import { usePermissions } from '~/composables/usePermissions'
import type {
  AnalyticsAgentOption,
  AnalyticsBreakdown,
  AnalyticsBreakdownDimension,
  AnalyticsFilters,
  AnalyticsFiltersMeta,
  AnalyticsOverview,
  AnalyticsResourceOption,
  AnalyticsCommoditiesTableResponse,
  AnalyticsServicesTableResponse,
  AnalyticsTimeGroup,
  AnalyticsTimeseries,
  CommoditiesTableQuery,
  ServicesTableQuery,
  ToolCallHistoryQuery,
  ToolCallHistoryResponse,
} from '~/types/analytics'

type AnalyticsQueryInput = Pick<
  AnalyticsFilters,
  | 'dateFrom'
  | 'dateTo'
  | 'timezone'
  | 'channel'
  | 'clientTags'
  | 'revenueBasis'
  | 'paymentMethods'
  | 'revenueCategories'
  | 'resourceExternalId'
>

type AgentListItem = {
  id: string
  name: string
}

type SqnsResourceRaw = {
  id?: number | string
  external_id?: number | string
  name?: string
  full_name?: string
  status?: string
}

type SqnsSpecialistsResponse = {
  specialists?: Array<{
    id?: string | number
    external_id?: string | number
    name?: string
  }>
}

const toAnalyticsQuery = (
  filters: AnalyticsQueryInput,
  extra: Record<string, string | number | undefined> = {},
) => {
  const query: Record<string, string | number | string[]> = {}

  if (filters.dateFrom) query.date_from = filters.dateFrom
  if (filters.dateTo) query.date_to = filters.dateTo
  if (filters.timezone) query.timezone = filters.timezone
  if (filters.channel) query.channel = filters.channel
  if (filters.clientTags.length) query.tags = filters.clientTags.join(',')
  query.revenue_basis = filters.revenueBasis
  if (filters.paymentMethods?.length) query.payment_methods = filters.paymentMethods
  if (filters.revenueCategories?.length) query.revenue_categories = filters.revenueCategories
  if (filters.resourceExternalId != null && Number.isFinite(filters.resourceExternalId)) {
    query.resource_external_id = filters.resourceExternalId
  }

  Object.entries(extra).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return
    query[key] = value
  })

  return query
}

const normalizeSqnsResourceItems = (rawItems: SqnsResourceRaw[]): AnalyticsResourceOption[] =>
  rawItems
    .filter((item) => {
      const st = String(item.status || '').toLowerCase()
      if (st && st !== 'active') return false
      return true
    })
    .map((item) => {
      const idValue = item.external_id ?? item.id
      const name = item.name || item.full_name || ''
      if (idValue === undefined || idValue === null || !name) return null
      return { id: idValue, name }
    })
    .filter((item): item is AnalyticsResourceOption => item !== null)

export const useAnalyticsApi = () => {
  const apiFetch = useApiFetch()
  const { canEditAgents } = usePermissions()

  const getAgentsForFilter = async (limit = 200): Promise<AnalyticsAgentOption[]> => {
    const response = await apiFetch<AgentListItem[]>('/agents', {
      query: { limit, offset: 0 },
    })
    return response.map((item) => ({ id: item.id, name: item.name }))
  }

  const getFiltersMeta = async (agentId: string, timezone?: string): Promise<AnalyticsFiltersMeta> => {
    return await apiFetch<AnalyticsFiltersMeta>(`/agents/${agentId}/analytics/filters-meta`, {
      query: timezone ? { timezone } : {},
    })
  }

  const getOverview = async (agentId: string, filters: AnalyticsQueryInput): Promise<AnalyticsOverview> => {
    return await apiFetch<AnalyticsOverview>(`/agents/${agentId}/analytics/overview`, {
      query: toAnalyticsQuery(filters),
    })
  }

  const getTimeseries = async (
    agentId: string,
    filters: AnalyticsQueryInput,
    groupBy: AnalyticsTimeGroup = 'day',
  ): Promise<AnalyticsTimeseries> => {
    return await apiFetch<AnalyticsTimeseries>(`/agents/${agentId}/analytics/timeseries`, {
      query: toAnalyticsQuery(filters, { group_by: groupBy }),
    })
  }

  const getBreakdown = async (
    agentId: string,
    filters: AnalyticsQueryInput,
    dimension: AnalyticsBreakdownDimension,
    limit = 10,
  ): Promise<AnalyticsBreakdown> => {
    return await apiFetch<AnalyticsBreakdown>(`/agents/${agentId}/analytics/breakdown`, {
      query: toAnalyticsQuery(filters, { dimension, limit }),
    })
  }

  const getServicesTable = async (agentId: string, query: ServicesTableQuery): Promise<AnalyticsServicesTableResponse> => {
    const requestQuery: Record<string, string | number | string[]> = {
      date_from: query.dateFrom,
      date_to: query.dateTo,
      timezone: query.timezone,
      sort_by: query.sortBy,
      sort_order: query.sortOrder,
      limit: query.limit,
      offset: query.offset,
    }

    if (query.channel) requestQuery.channel = query.channel
    if (query.resourceExternalId !== null) requestQuery.resource_external_id = query.resourceExternalId
    if (query.clientTags.length) {
      requestQuery.tags = query.clientTags.join(',')
      requestQuery.client_tags = query.clientTags
    }
    requestQuery.revenue_basis = query.revenueBasis
    if (query.paymentMethods?.length) requestQuery.payment_methods = query.paymentMethods
    if (query.revenueCategories?.length) requestQuery.revenue_categories = query.revenueCategories

    return await apiFetch<AnalyticsServicesTableResponse>(`/agents/${agentId}/analytics/services-table`, {
      query: requestQuery,
    })
  }

  const getCommoditiesTable = async (
    agentId: string,
    query: CommoditiesTableQuery,
  ): Promise<AnalyticsCommoditiesTableResponse> => {
    const requestQuery: Record<string, string | number | string[]> = {
      date_from: query.dateFrom,
      date_to: query.dateTo,
      timezone: query.timezone,
      sort_by: query.sortBy,
      sort_order: query.sortOrder,
      limit: query.limit,
      offset: query.offset,
    }

    if (query.channel) requestQuery.channel = query.channel
    if (query.resourceExternalId !== null) requestQuery.resource_external_id = query.resourceExternalId
    if (query.clientTags.length) {
      requestQuery.tags = query.clientTags.join(',')
      requestQuery.client_tags = query.clientTags
    }
    requestQuery.revenue_basis = query.revenueBasis
    if (query.paymentMethods?.length) requestQuery.payment_methods = query.paymentMethods
    if (query.revenueCategories?.length) requestQuery.revenue_categories = query.revenueCategories

    return await apiFetch<AnalyticsCommoditiesTableResponse>(`/agents/${agentId}/analytics/commodities-table`, {
      query: requestQuery,
    })
  }

  const getSqnsResourcesForFilter = async (agentId: string): Promise<AnalyticsResourceOption[]> => {
    // Live SQNS /resources требует agents:write — у менеджера только analytics:view, иначе 403 и тосты.
    if (canEditAgents.value) {
      try {
        const response = await apiFetch<any>(`/agents/${agentId}/sqns/resources`)
        const rawItems: SqnsResourceRaw[] = Array.isArray(response)
          ? response
          : Array.isArray(response?.resources)
            ? response.resources
            : Array.isArray(response?.items)
              ? response.items
              : []
        const normalizedResources = normalizeSqnsResourceItems(rawItems)
        if (normalizedResources.length > 0) return normalizedResources
      } catch {
        // падаем на кэш specialists ниже
      }
    }

    // Кэш специалистов в БД: доступен с analytics:view (см. бэкенд sqns_list_cached_specialists).
    const specialistsResponse = await apiFetch<SqnsSpecialistsResponse>(`/agents/${agentId}/sqns/specialists`, {
      query: { limit: 500, offset: 0, active: true },
    })

    const specialistItems = specialistsResponse.specialists || []
    return specialistItems
      .map((item) => {
        const idValue = item.external_id ?? item.id
        const name = item.name || ''
        if (idValue === undefined || idValue === null || !name) return null
        return {
          id: idValue,
          name,
        }
      })
      .filter((item): item is AnalyticsResourceOption => item !== null)
  }

  const getToolCallsHistory = async (query: ToolCallHistoryQuery): Promise<ToolCallHistoryResponse> => {
    const requestQuery: Record<string, string | number> = {
      date_from: query.dateFrom,
      date_to: query.dateTo,
      timezone: query.timezone,
      limit: query.limit,
      offset: query.offset,
    }

    if (query.agentId) requestQuery.agent_id = query.agentId
    if (query.toolName) requestQuery.tool_name = query.toolName
    if (query.status) requestQuery.status = query.status
    if (query.search) requestQuery.search = query.search

    // Different backend deployments may expose this endpoint under different paths.
    const candidatePaths = [
      '/analytics/tool-calls-history',
      '/tool-calls/history',
      '/admin/tool-calls/history',
    ]

    let lastError: unknown = null
    for (const path of candidatePaths) {
      try {
        return await apiFetch<ToolCallHistoryResponse>(path, { query: requestQuery })
      } catch (error: any) {
        const statusCode = Number(error?.status || error?.response?.status || 0)
        if (statusCode === 404) {
          lastError = error
          continue
        }
        throw error
      }
    }

    throw lastError || new Error('Tool calls history endpoint not found')
  }

  return {
    getAgentsForFilter,
    getFiltersMeta,
    getOverview,
    getTimeseries,
    getBreakdown,
    getServicesTable,
    getCommoditiesTable,
    getSqnsResourcesForFilter,
    getToolCallsHistory,
  }
}
