import { ref } from 'vue'
import { useApiFetch } from './useApiFetch'
import { useAuth } from './useAuth'
import { getReadableErrorMessage } from '~/utils/api-errors'
import type {
  ExpertSkill,
  ReviewCorrectionPayload,
  ReviewDialog,
  SkillDoc,
  SkillGap,
  SkillObjection,
} from '~/types/scriptFlow'

/**
 * API-слой раздела «Навыки эксперта» (expert_skills) — самостоятельная сущность,
 * отделённая от потоков. Навык правится в чате/структуре и публикуется для рантайма.
 */
export const useExpertSkills = (agentId: string) => {
  const apiFetch = useApiFetch()
  const { token } = useAuth()
  // @ts-ignore - Nuxt auto-import
  const { public: { apiBase } } = useRuntimeConfig()

  const skills = ref<ExpertSkill[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  const authHeaders = () => ({ Authorization: `Bearer ${token.value}` })
  const base = `/agents/${agentId}/expert-skills`

  const fetchSkills = async () => {
    isLoading.value = true
    error.value = null
    try {
      const data = await apiFetch<ExpertSkill[]>(base, { headers: authHeaders() })
      skills.value = data || []
    } catch (err: unknown) {
      error.value = getReadableErrorMessage(err, 'Не удалось загрузить навыки')
    } finally {
      isLoading.value = false
    }
  }

  const fetchTrash = async (): Promise<ExpertSkill[]> => {
    return (await apiFetch<ExpertSkill[]>(`${base}/trash`, { headers: authHeaders() })) || []
  }

  const getSkill = async (skillId: string): Promise<ExpertSkill> => {
    return await apiFetch<ExpertSkill>(`${base}/${skillId}`, { headers: authHeaders() })
  }

  const createSkill = async (payload: {
    name: string
    service_external_ids?: string[]
    import_from_flow_id?: string | null
  }): Promise<ExpertSkill> => {
    return await apiFetch<ExpertSkill>(base, {
      method: 'POST',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: payload,
    })
  }

  const updateSkill = async (
    skillId: string,
    payload: { name?: string; service_external_ids?: string[]; status?: 'draft' | 'published' },
  ): Promise<ExpertSkill> => {
    return await apiFetch<ExpertSkill>(`${base}/${skillId}`, {
      method: 'PATCH',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: payload,
    })
  }

  const deleteSkill = async (skillId: string): Promise<void> => {
    await apiFetch(`${base}/${skillId}`, { method: 'DELETE', headers: authHeaders() })
  }

  const restoreSkill = async (skillId: string): Promise<ExpertSkill> => {
    return await apiFetch<ExpertSkill>(`${base}/${skillId}/restore`, {
      method: 'POST',
      headers: authHeaders(),
    })
  }

  const publishSkill = async (skillId: string): Promise<ExpertSkill> => {
    return await apiFetch<ExpertSkill>(`${base}/${skillId}/publish`, {
      method: 'POST',
      headers: authHeaders(),
    })
  }

  const unpublishSkill = async (skillId: string): Promise<ExpertSkill> => {
    return await apiFetch<ExpertSkill>(`${base}/${skillId}/unpublish`, {
      method: 'POST',
      headers: authHeaders(),
    })
  }

  const importFromFlow = async (
    skillId: string,
    flowId: string,
  ): Promise<{ id: string; skill_doc: SkillDoc; objections: number; gaps: number }> => {
    return await apiFetch(`${base}/${skillId}/import-from-flow`, {
      method: 'POST',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: { flow_id: flowId },
    })
  }

  const updateSkillDoc = async (
    skillId: string,
    skillDoc: SkillDoc,
  ): Promise<{ id: string; skill_doc: SkillDoc; objections: number; gaps: number }> => {
    return await apiFetch(`${base}/${skillId}/skill-doc`, {
      method: 'PATCH',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: { skill_doc: skillDoc },
    })
  }

  const getSkillChatModels = async (): Promise<{
    models: Array<{ id: string; label: string; hint: string }>
    default: string
  }> => {
    return await apiFetch(`${base}/skill-chat/models`, { headers: authHeaders() })
  }

  const skillChat = async (
    skillId: string,
    payload: {
      messages: Array<{ role: string; content: string }>
      attachments?: Array<{ name: string; text: string }>
      skill_doc?: SkillDoc | null
      model?: string
    },
    signal?: AbortSignal,
  ): Promise<{
    reply: string
    additions: { objections: SkillObjection[]; gaps: SkillGap[] }
    added_objections: number
    added_gaps: number
  }> => {
    return await apiFetch(`${base}/${skillId}/skill-chat`, {
      method: 'POST',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: payload,
      signal,
    })
  }

  const skillChatStream = async (
    skillId: string,
    payload: {
      messages: Array<{ role: string; content: string }>
      attachments?: Array<{ name: string; text: string }>
      skill_doc?: SkillDoc | null
      model?: string
    },
    opts: { onDelta: (text: string) => void; signal?: AbortSignal },
  ): Promise<{ reply: string; additions: { objections: SkillObjection[]; gaps: SkillGap[] } } | null> => {
    const res = await fetch(`${apiBase}${base}/${skillId}/skill-chat/stream`, {
      method: 'POST',
      headers: { ...authHeaders(), 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify(payload),
      signal: opts.signal,
    })
    if (!res.ok || !res.body) throw new Error(`Стрим недоступен (${res.status})`)
    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let done: { reply: string; additions: { objections: SkillObjection[]; gaps: SkillGap[] } } | null = null
    for (;;) {
      const { value, done: rdDone } = await reader.read()
      if (rdDone) break
      buffer += decoder.decode(value, { stream: true })
      let idx: number
      while ((idx = buffer.indexOf('\n\n')) >= 0) {
        const rawEvent = buffer.slice(0, idx)
        buffer = buffer.slice(idx + 2)
        let event = 'message'
        let data = ''
        for (const line of rawEvent.split('\n')) {
          if (line.startsWith('event:')) event = line.slice(6).trim()
          else if (line.startsWith('data:')) data += line.slice(5).trim()
        }
        if (!data) continue
        const parsed = JSON.parse(data)
        if (event === 'delta') opts.onDelta(parsed.text as string)
        else if (event === 'done') done = parsed
        else if (event === 'error') throw new Error(parsed.error || 'Ошибка стрима')
      }
    }
    return done
  }

  const getReviewDialogs = async (
    skillId: string,
    limit = 30,
  ): Promise<{ dialogs: ReviewDialog[]; has_service_link: boolean }> => {
    return await apiFetch(`${base}/${skillId}/review-dialogs?limit=${limit}`, {
      headers: authHeaders(),
    })
  }

  const addReviewCorrection = async (
    skillId: string,
    payload: ReviewCorrectionPayload,
  ): Promise<{ id: string; skill_doc: SkillDoc; objections: number; gaps: number }> => {
    return await apiFetch(`${base}/${skillId}/review-correction`, {
      method: 'POST',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: payload,
    })
  }

  return {
    skills,
    isLoading,
    error,
    fetchSkills,
    fetchTrash,
    getSkill,
    createSkill,
    updateSkill,
    deleteSkill,
    restoreSkill,
    publishSkill,
    unpublishSkill,
    importFromFlow,
    updateSkillDoc,
    getSkillChatModels,
    skillChat,
    skillChatStream,
    getReviewDialogs,
    addReviewCorrection,
  }
}
