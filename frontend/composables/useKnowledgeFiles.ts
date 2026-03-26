import { computed, ref } from 'vue'
import { useApiFetch } from '~/composables/useApiFetch'
import {
  knowledgeIndexJobStatus,
  knowledgeItemType,
  knowledgeVectorStatus,
  type CreateKnowledgeFilePayload,
  type CreateKnowledgeTextPayload,
  type KnowledgeFileItem,
  type KnowledgeFileIndexStatusResponse,
  type KnowledgeIndexJobStateResponse,
  type KnowledgeIndexJobStatus,
  type KnowledgeIndexStartResponse
} from '~/types/knowledge'

const getHttpErrorStatus = (e: unknown): number => {
  const err = e as { status?: number; statusCode?: number; response?: { status?: number } }
  return err?.status ?? err?.statusCode ?? err?.response?.status ?? 0
}

type KnowledgeFilesStorage = {
  items: KnowledgeFileItem[]
}

export type KnowledgeUploadBatchItemResult = {
  fileName: string
  ok: boolean
  id?: string
  error?: string
}

const ensureClient = () => typeof window !== 'undefined'

const createId = () => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  return `kf_${Date.now()}_${Math.random().toString(16).slice(2)}`
}

const sortItems = (items: KnowledgeFileItem[]) => {
  return [...items].sort((left, right) => {
    if ((left.parent_id ?? '') !== (right.parent_id ?? '')) return (left.parent_id ?? '').localeCompare(right.parent_id ?? '')
    if (left.order_index !== right.order_index) return left.order_index - right.order_index
    if (left.type !== right.type) return left.type === knowledgeItemType.folder ? -1 : 1
    return left.title.localeCompare(right.title, 'ru')
  })
}

const DEFAULT_CHUNK_SIZE_CHARS = 6000
const DEFAULT_CHUNK_OVERLAP_CHARS = 1000

const normalizeIncomingItem = (
  source: Partial<KnowledgeFileItem>,
  fallback: KnowledgeFileItem
): KnowledgeFileItem => ({
  ...fallback,
  ...source,
  id: source.id || fallback.id,
  agent_id: source.agent_id || fallback.agent_id,
  parent_id: source.parent_id ?? fallback.parent_id ?? null,
  type: source.type === knowledgeItemType.folder ? knowledgeItemType.folder : (
    source.type === knowledgeItemType.file ? knowledgeItemType.file : fallback.type
  ),
  title: typeof source.title === 'string' ? source.title : fallback.title,
  meta_tags: Array.isArray(source.meta_tags) ? source.meta_tags : fallback.meta_tags,
  content: typeof source.content === 'string' ? source.content : fallback.content,
  is_enabled: typeof source.is_enabled === 'boolean' ? source.is_enabled : fallback.is_enabled,
  vector_status: source.vector_status ?? fallback.vector_status,
  chunk_size_chars:
    typeof source.chunk_size_chars === 'number'
      ? source.chunk_size_chars
      : fallback.chunk_size_chars ?? null,
  chunk_overlap_chars:
    typeof source.chunk_overlap_chars === 'number'
      ? source.chunk_overlap_chars
      : fallback.chunk_overlap_chars ?? null,
  order_index: typeof source.order_index === 'number' ? source.order_index : fallback.order_index,
  chunks_count:
    typeof source.chunks_count === 'number'
      ? source.chunks_count
      : (fallback.chunks_count ?? null),
  indexed_at:
    typeof source.indexed_at === 'string'
      ? source.indexed_at
      : source.indexed_at === null
        ? null
        : (fallback.indexed_at ?? null),
  created_at: source.created_at ?? fallback.created_at,
  updated_at: source.updated_at ?? fallback.updated_at
})

export const useKnowledgeFiles = (agentId: string) => {
  const apiFetch = useApiFetch()
  const items = ref<KnowledgeFileItem[]>([])
  const isLoading = ref(false)
  const currentFolderId = ref<string | null>(null)
  const error = ref<string | null>(null)
  const storageKey = computed(() => `knowledge-files:${agentId}`)
  const baseEndpoint = computed(() => `/agents/${agentId}/knowledge/files`)
  const itemEndpoint = (id: string) => `${baseEndpoint.value}/${id}`
  const uploadEndpoint = computed(() => `${baseEndpoint.value}/upload`)
  const fileIndexEndpoint = (id: string) => `${baseEndpoint.value}/${id}/index`
  const fileIndexStatusEndpoint = (id: string) => `${baseEndpoint.value}/${id}/index-status`
  const indexJobEndpoint = (jobId: string) => `/agents/${agentId}/knowledge/index-jobs/${jobId}`
  const indexProgressByItem = ref<Record<string, number>>({})
  const indexStateByItem = ref<Record<string, KnowledgeIndexJobStatus>>({})
  const pollTimers = new Map<string, ReturnType<typeof setTimeout>>()

  const readStorage = (): KnowledgeFilesStorage => {
    if (!ensureClient()) return { items: [] }
    try {
      const raw = window.localStorage.getItem(storageKey.value)
      if (!raw) return { items: [] }
      const parsed = JSON.parse(raw) as Partial<KnowledgeFilesStorage>
      return { items: Array.isArray(parsed.items) ? parsed.items : [] }
    } catch {
      return { items: [] }
    }
  }

  const writeStorage = () => {
    if (!ensureClient()) return
    window.localStorage.setItem(storageKey.value, JSON.stringify({ items: items.value }))
  }

  const siblings = (parentId: string | null) => items.value.filter((item) => item.parent_id === parentId)
  const nextOrderIndex = (parentId: string | null) => {
    const list = siblings(parentId)
    return list.length ? Math.max(...list.map((item) => item.order_index)) + 1 : 1
  }

  const normalizeParentOrder = (parentId: string | null) => {
    const list = sortItems(siblings(parentId))
    list.forEach((item, index) => { item.order_index = index + 1 })
  }

  const findItem = (id: string) => items.value.find((item) => item.id === id)
  const isFolder = (item: KnowledgeFileItem | undefined | null) => item?.type === knowledgeItemType.folder
  const isTerminalStatus = (status: KnowledgeIndexJobStatus | undefined) =>
    status === knowledgeIndexJobStatus.indexed || status === knowledgeIndexJobStatus.failed
  const toProgress = (value: unknown, fallback = 0) => {
    if (typeof value !== 'number' || !Number.isFinite(value)) return fallback
    return Math.max(0, Math.min(100, Math.round(value)))
  }
  const syncItemVectorStatus = (itemId: string, status: KnowledgeIndexJobStatus) => {
    const item = findItem(itemId)
    if (!item || item.type !== knowledgeItemType.file) return
    if (status === knowledgeIndexJobStatus.indexed) item.vector_status = knowledgeVectorStatus.indexed
    else if (status === knowledgeIndexJobStatus.failed) item.vector_status = knowledgeVectorStatus.failed
    else item.vector_status = knowledgeVectorStatus.indexing
  }
  const clearPollTimer = (fileId: string) => {
    const timer = pollTimers.get(fileId)
    if (timer) clearTimeout(timer)
    pollTimers.delete(fileId)
  }
  const setIndexState = (fileId: string, status: KnowledgeIndexJobStatus, progress?: number) => {
    const prevProg = indexProgressByItem.value[fileId] ?? 0
    let nextProgress: number
    if (typeof progress === 'number' && Number.isFinite(progress)) {
      nextProgress = toProgress(progress, status === knowledgeIndexJobStatus.indexed ? 100 : 0)
    } else if (status === knowledgeIndexJobStatus.indexed) {
      nextProgress = 100
    } else if (status === knowledgeIndexJobStatus.failed) {
      nextProgress = prevProg
    } else {
      // queued / indexing без числа от API — не показываем фиктивные 5% / 10%
      nextProgress = 0
    }
    // Новые объекты — чтобы дочерние компоненты гарантированно увидели обновление прогресса
    indexStateByItem.value = { ...indexStateByItem.value, [fileId]: status }
    indexProgressByItem.value = { ...indexProgressByItem.value, [fileId]: nextProgress }
  }

  const pollJobStatus = (fileId: string, jobId: string, attempt = 0) => {
    clearPollTimer(fileId)
    const MAX_ATTEMPTS = 150
    const POLL_MS = 2000

    const run = async () => {
      try {
        const result = await apiFetch<KnowledgeIndexJobStateResponse>(indexJobEndpoint(jobId), {
          method: 'GET'
        })
        const status = result?.status ?? knowledgeIndexJobStatus.indexing
        setIndexState(fileId, status, result?.progress)
        syncItemVectorStatus(fileId, status)
        if (isTerminalStatus(status)) {
          const row = findItem(fileId)
          if (
            row
            && row.type === knowledgeItemType.file
            && status === knowledgeIndexJobStatus.indexed
            && typeof result?.chunks_total === 'number'
            && result.chunks_total >= 0
          ) {
            row.chunks_count = result.chunks_total
          }
          if (
            row
            && row.type === knowledgeItemType.file
            && status === knowledgeIndexJobStatus.indexed
            && typeof result?.indexed_at === 'string'
          ) {
            row.indexed_at = result.indexed_at
          }
          writeStorage()
          return
        }
        writeStorage()

        const timer = setTimeout(() => {
          void pollJobStatus(fileId, jobId, attempt + 1)
        }, POLL_MS)
        pollTimers.set(fileId, timer)
      } catch (apiError: any) {
        const httpStatus = getHttpErrorStatus(apiError)
        if (httpStatus === 404 && attempt < 8) {
          const timer = setTimeout(() => {
            void pollJobStatus(fileId, jobId, attempt + 1)
          }, POLL_MS)
          pollTimers.set(fileId, timer)
          return
        }
        if (httpStatus === 404) {
          pollFileIndexStatus(fileId, 0)
          return
        }
        if ([405, 501].includes(httpStatus)) {
          return
        }
        if (attempt >= MAX_ATTEMPTS) {
          setIndexState(fileId, knowledgeIndexJobStatus.failed)
          syncItemVectorStatus(fileId, knowledgeIndexJobStatus.failed)
          writeStorage()
          return
        }
        const timer = setTimeout(() => {
          void pollJobStatus(fileId, jobId, attempt + 1)
        }, POLL_MS)
        pollTimers.set(fileId, timer)
      }
    }

    if (attempt >= MAX_ATTEMPTS) {
      setIndexState(fileId, knowledgeIndexJobStatus.failed)
      syncItemVectorStatus(fileId, knowledgeIndexJobStatus.failed)
      writeStorage()
      return
    }

    void run()
  }

  const pollFileIndexStatus = (fileId: string, attempt = 0) => {
    clearPollTimer(fileId)
    const MAX_ATTEMPTS = 120
    const POLL_MS = 2000

    const run = async () => {
      try {
        const result = await apiFetch<KnowledgeFileIndexStatusResponse>(fileIndexStatusEndpoint(fileId), {
          method: 'GET'
        })
        const row = findItem(fileId)
        if (row && row.type === knowledgeItemType.file) {
          if (typeof result?.chunks_count === 'number') {
            row.chunks_count = result.chunks_count
          }
          if (typeof result?.indexed_at === 'string') {
            row.indexed_at = result.indexed_at
          }
          if (result?.indexed_at === null) {
            row.indexed_at = null
          }
        }
        const rawVs = result?.vector_status
        const vs =
          rawVs === knowledgeVectorStatus.notIndexed
            ? knowledgeVectorStatus.indexing
            : (rawVs ?? knowledgeVectorStatus.indexing)
        const progress = toProgress(
          result?.progress,
          vs === knowledgeVectorStatus.indexed ? 100 : 0
        )

        if (vs === knowledgeVectorStatus.indexed) {
          setIndexState(fileId, knowledgeIndexJobStatus.indexed, progress)
          syncItemVectorStatus(fileId, knowledgeIndexJobStatus.indexed)
          writeStorage()
          return
        }
        if (vs === knowledgeVectorStatus.failed) {
          setIndexState(fileId, knowledgeIndexJobStatus.failed, progress)
          syncItemVectorStatus(fileId, knowledgeIndexJobStatus.failed)
          writeStorage()
          return
        }

        setIndexState(fileId, knowledgeIndexJobStatus.indexing, progress)
        syncItemVectorStatus(fileId, knowledgeIndexJobStatus.indexing)
        writeStorage()

        const timer = setTimeout(() => {
          void pollFileIndexStatus(fileId, attempt + 1)
        }, POLL_MS)
        pollTimers.set(fileId, timer)
      } catch (apiError: any) {
        if ([404, 405, 501].includes(getHttpErrorStatus(apiError))) return
        if (attempt >= MAX_ATTEMPTS) {
          setIndexState(fileId, knowledgeIndexJobStatus.failed)
          syncItemVectorStatus(fileId, knowledgeIndexJobStatus.failed)
          writeStorage()
          return
        }
        const timer = setTimeout(() => {
          void pollFileIndexStatus(fileId, attempt + 1)
        }, POLL_MS)
        pollTimers.set(fileId, timer)
      }
    }

    void run()
  }

  const fetchItems = async () => {
    isLoading.value = true
    error.value = null
    try {
      try {
        const data = await apiFetch<KnowledgeFileItem[]>(baseEndpoint.value, {
          method: 'GET'
        })
        if (Array.isArray(data)) {
          items.value = sortItems(
            data
              .filter((item) => item.agent_id === agentId)
              .map((item) => ({
                ...item,
                type: item.type === knowledgeItemType.folder ? knowledgeItemType.folder : knowledgeItemType.file,
                meta_tags: Array.isArray(item.meta_tags) ? item.meta_tags : [],
                content: item.content ?? '',
                vector_status: item.vector_status ?? knowledgeVectorStatus.notIndexed,
                chunk_size_chars: typeof item.chunk_size_chars === 'number' ? item.chunk_size_chars : null,
                chunk_overlap_chars: typeof item.chunk_overlap_chars === 'number' ? item.chunk_overlap_chars : null,
                chunks_count: typeof item.chunks_count === 'number' ? item.chunks_count : null,
                indexed_at:
                  typeof item.indexed_at === 'string'
                    ? item.indexed_at
                    : item.indexed_at === null
                      ? null
                      : undefined
              }))
          )
          writeStorage()
          return
        }
      } catch (apiError: any) {
        // Backend may not yet support this endpoint in all envs.
        // Fallback keeps UI fully functional.
        if (![404, 405, 501].includes(getHttpErrorStatus(apiError))) {
          throw apiError
        }
      }

      const state = readStorage()
      items.value = sortItems(state.items.filter((item) => item.agent_id === agentId))
    } finally {
      isLoading.value = false
    }
  }

  const openFolder = (folderId: string | null) => {
    currentFolderId.value = folderId
  }

  const createFolder = async (payload: CreateKnowledgeFilePayload) => {
    const parentId = payload.parent_id ?? currentFolderId.value ?? null
    const now = new Date().toISOString()
    const folder: KnowledgeFileItem = {
      id: createId(),
      agent_id: agentId,
      parent_id: parentId,
      type: knowledgeItemType.folder,
      title: payload.title.trim(),
      meta_tags: [],
      content: '',
      is_enabled: true,
      vector_status: knowledgeVectorStatus.notIndexed,
      chunk_size_chars: DEFAULT_CHUNK_SIZE_CHARS,
      chunk_overlap_chars: DEFAULT_CHUNK_OVERLAP_CHARS,
      order_index: nextOrderIndex(parentId),
      created_at: now,
      updated_at: now
    }
    try {
      const created = await apiFetch<KnowledgeFileItem>(baseEndpoint.value, {
        method: 'POST',
        body: {
          parent_id: parentId,
          type: knowledgeItemType.folder,
          title: folder.title
        }
      })
      if (created?.id) {
        items.value.push(normalizeIncomingItem(created, folder))
      } else {
        items.value.push(folder)
      }
    } catch (apiError: any) {
      if (![404, 405, 501].includes(getHttpErrorStatus(apiError))) throw apiError
      items.value.push(folder)
    }
    normalizeParentOrder(parentId)
    items.value = sortItems(items.value)
    writeStorage()
    return folder
  }

  const createFile = async (payload: CreateKnowledgeTextPayload) => {
    const parentId = payload.parent_id ?? currentFolderId.value ?? null
    const now = new Date().toISOString()
    const file: KnowledgeFileItem = {
      id: createId(),
      agent_id: agentId,
      parent_id: parentId,
      type: knowledgeItemType.file,
      title: payload.title.trim(),
      meta_tags: payload.meta_tags ?? [],
      content: payload.content ?? '',
      is_enabled: payload.is_enabled ?? true,
      vector_status: payload.vector_status ?? knowledgeVectorStatus.notIndexed,
      chunk_size_chars: null,
      chunk_overlap_chars: null,
      chunks_count: 0,
      indexed_at: null,
      order_index: nextOrderIndex(parentId),
      created_at: now,
      updated_at: now
    }
    let persistedFile: KnowledgeFileItem = file
    try {
      const created = await apiFetch<KnowledgeFileItem>(baseEndpoint.value, {
        method: 'POST',
        body: {
          parent_id: parentId,
          type: knowledgeItemType.file,
          title: file.title,
          meta_tags: file.meta_tags,
          content: file.content,
          is_enabled: file.is_enabled
        }
      })
      if (created?.id) {
        persistedFile = normalizeIncomingItem(created, file)
        items.value.push(persistedFile)
      } else {
        items.value.push(file)
      }
    } catch (apiError: any) {
      if (![404, 405, 501].includes(getHttpErrorStatus(apiError))) throw apiError
      items.value.push(file)
    }
    normalizeParentOrder(parentId)
    items.value = sortItems(items.value)
    writeStorage()
    return persistedFile
  }

  const uploadDocument = async (file: File) => {
    const parentId = currentFolderId.value ?? null
    const formData = new FormData()
    formData.append('file', file)
    if (parentId) formData.append('parent_id', parentId)

    const created = await apiFetch<KnowledgeFileItem>(uploadEndpoint.value, {
      method: 'POST',
      body: formData
    })

    if (created?.id) {
      items.value.push(normalizeIncomingItem(created, created))
      items.value = sortItems(items.value)
      writeStorage()
    }

    return created
  }

  /**
   * Несколько файлов через тот же POST /upload, с ограничением параллелизма (по умолчанию 3).
   */
  const uploadDocumentsBatch = async (
    files: File[],
    concurrency = 3
  ): Promise<KnowledgeUploadBatchItemResult[]> => {
    const allowed = files.filter(Boolean)
    if (!allowed.length) return []

    const results: KnowledgeUploadBatchItemResult[] = new Array(allowed.length)
    let nextIndex = 0
    const limit = Math.max(1, Math.min(concurrency, 8))

    const worker = async () => {
      while (true) {
        const i = nextIndex
        nextIndex += 1
        if (i >= allowed.length) return
        const file = allowed[i]
        try {
          const created = await uploadDocument(file)
          if (created?.id) {
            results[i] = { fileName: file.name, ok: true, id: created.id }
          } else {
            results[i] = { fileName: file.name, ok: false, error: 'Пустой ответ сервера' }
          }
        } catch (e: any) {
          const detail = e?.data?.detail
          const msg =
            typeof detail === 'string'
              ? detail
              : Array.isArray(detail)
                ? detail.map((x: { msg?: string }) => x?.msg).filter(Boolean).join('; ')
                : e?.message || 'Ошибка загрузки'
          results[i] = { fileName: file.name, ok: false, error: msg }
        }
      }
    }

    await Promise.all(Array.from({ length: Math.min(limit, allowed.length) }, () => worker()))
    return results
  }

  const updateFile = async (id: string, payload: Partial<CreateKnowledgeTextPayload>) => {
    const item = findItem(id)
    if (!item || item.type !== knowledgeItemType.file) return null
    const snapshot = { ...item, meta_tags: [...item.meta_tags] }
    if (typeof payload.title === 'string') item.title = payload.title.trim()
    if (Array.isArray(payload.meta_tags)) item.meta_tags = payload.meta_tags
    if (typeof payload.content === 'string') item.content = payload.content
    if (typeof payload.is_enabled === 'boolean') item.is_enabled = payload.is_enabled
    if (payload.vector_status) item.vector_status = payload.vector_status
    item.updated_at = new Date().toISOString()
    try {
      // vector_status на файлах меняет только бэкенд (индексация); в PATCH его нельзя — будет 400.
      const updated = await apiFetch<KnowledgeFileItem>(itemEndpoint(id), {
        method: 'PATCH',
        body: {
          title: item.title,
          meta_tags: item.meta_tags,
          content: item.content,
          is_enabled: item.is_enabled
        }
      })
      if (updated && typeof updated.chunks_count === 'number') {
        item.chunks_count = updated.chunks_count
      }
      if (updated && typeof updated.indexed_at === 'string') {
        item.indexed_at = updated.indexed_at
      }
      if (updated && updated.indexed_at === null) {
        item.indexed_at = null
      }
    } catch (apiError: any) {
      if (![404, 405, 501].includes(getHttpErrorStatus(apiError))) {
        Object.assign(item, snapshot)
        throw apiError
      }
    }
    items.value = sortItems(items.value)
    writeStorage()
    return item
  }

  const updateFolderChunkingSettings = async (
    folderId: string,
    settings: { chunk_size_chars: number | null; chunk_overlap_chars: number | null }
  ) => {
    const item = findItem(folderId)
    if (!item || item.type !== knowledgeItemType.folder) return null
    const snapshot = { ...item }

    item.chunk_size_chars = settings.chunk_size_chars
    item.chunk_overlap_chars = settings.chunk_overlap_chars
    item.updated_at = new Date().toISOString()

    try {
      await apiFetch<KnowledgeFileItem>(itemEndpoint(folderId), {
        method: 'PATCH',
        body: {
          chunk_size_chars: item.chunk_size_chars,
          chunk_overlap_chars: item.chunk_overlap_chars
        }
      })
    } catch (apiError: any) {
      Object.assign(item, snapshot)
      throw apiError
    }

    items.value = sortItems(items.value)
    writeStorage()
    return item
  }

  const renameFolder = async (id: string, title: string) => {
    const item = findItem(id)
    if (!isFolder(item)) return null
    const previousTitle = item.title
    item.title = title.trim()
    item.updated_at = new Date().toISOString()
    try {
      await apiFetch<KnowledgeFileItem>(itemEndpoint(id), {
        method: 'PATCH',
        body: { title: item.title }
      })
    } catch (apiError: any) {
      if (![404, 405, 501].includes(getHttpErrorStatus(apiError))) {
        item.title = previousTitle
        throw apiError
      }
    }
    items.value = sortItems(items.value)
    writeStorage()
    return item
  }

  const collectDescendants = (folderId: string) => {
    const result = new Set<string>()
    const stack = [folderId]
    while (stack.length) {
      const current = stack.pop()
      if (!current || result.has(current)) continue
      result.add(current)
      items.value
        .filter((item) => item.parent_id === current && item.type === knowledgeItemType.folder)
        .forEach((item) => stack.push(item.id))
    }
    return result
  }

  const moveItem = async (id: string, targetFolderId: string | null) => {
    const item = findItem(id)
    if (!item) return
    if (targetFolderId) {
      const target = findItem(targetFolderId)
      if (!isFolder(target)) return
    }
    if (item.parent_id === targetFolderId) return
    if (item.type === knowledgeItemType.folder && targetFolderId) {
      const descendants = collectDescendants(item.id)
      if (descendants.has(targetFolderId)) return
    }
    const snapshotParent = item.parent_id
    const snapshotOrder = item.order_index
    const previousParent = item.parent_id
    item.parent_id = targetFolderId
    item.order_index = nextOrderIndex(targetFolderId)
    item.updated_at = new Date().toISOString()
    normalizeParentOrder(previousParent)
    normalizeParentOrder(targetFolderId)
    try {
      await apiFetch(itemEndpoint(id), {
        method: 'PATCH',
        body: {
          parent_id: targetFolderId,
          order_index: item.order_index
        }
      })
    } catch (apiError: any) {
      if (![404, 405, 501].includes(getHttpErrorStatus(apiError))) {
        item.parent_id = snapshotParent
        item.order_index = snapshotOrder
        normalizeParentOrder(previousParent)
        normalizeParentOrder(targetFolderId)
        throw apiError
      }
    }
    items.value = sortItems(items.value)
    writeStorage()
  }

  const deleteItem = async (id: string) => {
    const item = findItem(id)
    if (!item) return
    if (item.type === knowledgeItemType.file) {
      const snapshot = [...items.value]
      items.value = items.value.filter((entry) => entry.id !== id)
      normalizeParentOrder(item.parent_id)
      try {
        await apiFetch(itemEndpoint(id), { method: 'DELETE' })
      } catch (apiError: any) {
        if (![404, 405, 501].includes(getHttpErrorStatus(apiError))) {
          items.value = snapshot
          throw apiError
        }
      }
      writeStorage()
      return
    }
    const toDelete = collectDescendants(id)
    const snapshot = [...items.value]
    items.value = items.value.filter((entry) => !toDelete.has(entry.id))
    normalizeParentOrder(item.parent_id)
    if (toDelete.has(currentFolderId.value || '')) currentFolderId.value = item.parent_id
    try {
      await apiFetch(itemEndpoint(id), { method: 'DELETE' })
    } catch (apiError: any) {
      if (![404, 405, 501].includes(getHttpErrorStatus(apiError))) {
        items.value = snapshot
        throw apiError
      }
    }
    writeStorage()
  }

  const reindexFile = async (id: string) => {
    const item = findItem(id)
    if (!item || item.type !== knowledgeItemType.file) return
    item.vector_status = knowledgeVectorStatus.indexing
    setIndexState(id, knowledgeIndexJobStatus.queued, 0)
    writeStorage()
    try {
      const result = await apiFetch<KnowledgeIndexStartResponse>(fileIndexEndpoint(id), {
        method: 'POST'
      })

      if (result?.job_id) {
        const startStatus = result.status ?? knowledgeIndexJobStatus.queued
        const startProgress = typeof result.progress === 'number' ? result.progress : 0
        setIndexState(id, startStatus, startProgress)
        syncItemVectorStatus(id, startStatus)
        writeStorage()
        pollJobStatus(id, result.job_id)
        return
      }

      const responseStatus = result?.status
      if (responseStatus) {
        setIndexState(id, responseStatus, result.progress)
        syncItemVectorStatus(id, responseStatus)
        writeStorage()
        if (!isTerminalStatus(responseStatus)) {
          pollFileIndexStatus(id)
        }
        return
      }

      if (result?.vector_status === knowledgeVectorStatus.indexed) {
        setIndexState(id, knowledgeIndexJobStatus.indexed, 100)
        item.vector_status = knowledgeVectorStatus.indexed
        writeStorage()
        return
      }

      pollFileIndexStatus(id)
    } catch (apiError: any) {
      if ([404, 405, 501].includes(getHttpErrorStatus(apiError))) {
        // If indexing endpoint is unavailable, keep UI in "indexing" as draft status.
        setIndexState(id, knowledgeIndexJobStatus.indexing, indexProgressByItem.value[id] ?? 0)
        item.vector_status = knowledgeVectorStatus.indexing
      } else {
        setIndexState(id, knowledgeIndexJobStatus.failed, indexProgressByItem.value[id] ?? 0)
        item.vector_status = knowledgeVectorStatus.failed
        writeStorage()
        throw apiError
      }
    }
    writeStorage()
  }

  const currentItems = computed(() =>
    sortItems(items.value.filter((item) => item.parent_id === currentFolderId.value))
  )

  const folderChildrenCount = computed(() => {
    const map = new Map<string, number>()
    items.value.forEach((item) => {
      if (item.parent_id && findItem(item.parent_id)?.type === knowledgeItemType.folder) {
        map.set(item.parent_id, (map.get(item.parent_id) ?? 0) + 1)
      }
    })
    return map
  })

  const breadcrumbs = computed(() => {
    const root: { id: string | null; title: string } = { id: null, title: 'Загрузка файлов' }
    const upward: Array<{ id: string; title: string }> = []
    let cursor = currentFolderId.value
    const guard = new Set<string>()
    while (cursor) {
      if (guard.has(cursor)) break
      guard.add(cursor)
      const current = findItem(cursor)
      if (!current || current.type !== knowledgeItemType.folder) break
      upward.push({ id: current.id, title: current.title })
      cursor = current.parent_id
    }
    return [root, ...upward.reverse()]
  })

  const folders = computed(() =>
    sortItems(items.value.filter((item) => item.type === knowledgeItemType.folder))
  )

  const getMoveTargets = (itemId: string) => {
    const current = findItem(itemId)
    const descendants = current?.type === knowledgeItemType.folder ? collectDescendants(itemId) : new Set<string>()
    return folders.value.filter((folder) => folder.id !== itemId && !descendants.has(folder.id))
  }

  return {
    error,
    isLoading,
    currentFolderId,
    allItems: computed(() => sortItems(items.value)),
    currentItems,
    folders,
    folderChildrenCount,
    indexProgressByItem: computed(() => ({ ...indexProgressByItem.value })),
    indexStateByItem: computed(() => ({ ...indexStateByItem.value })),
    breadcrumbs,
    fetchItems,
    openFolder,
    createFolder,
    createFile,
    updateFile,
    renameFolder,
    moveItem,
    deleteItem,
    getMoveTargets,
    reindexFile,
    updateFolderChunkingSettings,
    uploadDocument,
    uploadDocumentsBatch
  }
}
