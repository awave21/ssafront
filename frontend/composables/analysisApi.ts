import { useApiFetch } from '~/composables/useApiFetch'
import type {
  AnalysisJob,
  AnalysisRecommendationReviewPayload,
  AnalysisRecommendationsFilters,
  AnalysisRecommendationsResponse,
  AnalysisReport,
  AnalysisStartPayload,
} from '~/types/agent-analysis'

const toDefinedQuery = (query: Record<string, unknown>) =>
  Object.fromEntries(Object.entries(query).filter(([, value]) => value !== undefined && value !== null && value !== ''))

const getAgentAnalysisBase = (agentId: string) => `/agents/${agentId}/analysis`
const toApiReviewStatus = (status: AnalysisRecommendationsFilters['status']) =>
  status === 'pending' ? 'open' : status

export const useAnalysisApi = () => {
  const apiFetch = useApiFetch()

  const startAnalysisJob = async (agentId: string, payload: AnalysisStartPayload) => {
    return await apiFetch<AnalysisJob>(`${getAgentAnalysisBase(agentId)}/jobs`, {
      method: 'POST',
      body: payload
    })
  }

  const getAnalysisJobs = async (agentId: string) => {
    return await apiFetch<AnalysisJob[] | { items?: AnalysisJob[]; jobs?: AnalysisJob[] }>(`${getAgentAnalysisBase(agentId)}/jobs`)
  }

  const getAnalysisJob = async (agentId: string, jobId: string) => {
    return await apiFetch<AnalysisJob>(`${getAgentAnalysisBase(agentId)}/jobs/${jobId}`)
  }

  const getAnalysisReport = async (agentId: string, jobId: string) => {
    return await apiFetch<AnalysisReport>(`${getAgentAnalysisBase(agentId)}/jobs/${jobId}/report`)
  }

  const cancelAnalysisJob = async (agentId: string, jobId: string) => {
    return await apiFetch<void>(`${getAgentAnalysisBase(agentId)}/jobs/${jobId}/cancel`, {
      method: 'POST'
    })
  }

  const getAnalysisRecommendations = async (agentId: string, filters: AnalysisRecommendationsFilters = {}) => {
    return await apiFetch<AnalysisRecommendationsResponse | { items?: any[]; recommendations?: any[]; total?: number }>(
      `${getAgentAnalysisBase(agentId)}/recommendations`,
      {
        query: toDefinedQuery({
          category: filters.category,
          status: filters.status && filters.status !== 'all' ? toApiReviewStatus(filters.status) : undefined,
          limit: filters.limit,
          offset: filters.offset
        })
      }
    )
  }

  const reviewRecommendation = async (
    agentId: string,
    recommendationId: string,
    body: AnalysisRecommendationReviewPayload
  ) => {
    return await apiFetch<void>(`${getAgentAnalysisBase(agentId)}/recommendations/${recommendationId}/review`, {
      method: 'POST',
      body
    })
  }

  return {
    startAnalysisJob,
    getAnalysisJobs,
    getAnalysisJob,
    getAnalysisReport,
    cancelAnalysisJob,
    getAnalysisRecommendations,
    reviewRecommendation
  }
}
