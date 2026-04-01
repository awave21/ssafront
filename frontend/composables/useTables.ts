import { computed, ref } from 'vue'
import { useApiFetch } from './useApiFetch'
import { useAuth } from './useAuth'
import { getReadableErrorMessage } from '~/utils/api-errors'
import type {
  TableAttribute,
  TableCreatePayload,
  TableItem,
  TableRead,
  TableRecordRead,
  TableRecordsBulkCreateResponse,
  TableRecordsListResponse,
} from '~/types/tables'

export const useTables = () => {
  const apiFetch = useApiFetch()
  const { token } = useAuth()

  const tables = ref<TableItem[]>([])
  const isLoading = ref(false)
  const error = ref<string | null>(null)

  const fetchTables = async () => {
    isLoading.value = true
    error.value = null
    try {
      const data = await apiFetch<TableItem[]>('/tables', {
        headers: { Authorization: `Bearer ${token.value}` },
      })
      tables.value = data || []
    } catch (err: any) {
      error.value = getReadableErrorMessage(err, 'Не удалось загрузить таблицы')
      tables.value = []
    } finally {
      isLoading.value = false
    }
  }

  const createTable = async (payload: TableCreatePayload): Promise<TableRead> => {
    try {
      const created = await apiFetch<TableRead>('/tables', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token.value}`,
          'Content-Type': 'application/json',
        },
        body: payload,
      })
      await fetchTables()
      return created
    } catch (err: any) {
      throw new Error(getReadableErrorMessage(err, 'Не удалось создать таблицу'))
    }
  }

  const totalRecords = computed(() => tables.value.reduce((acc, table) => acc + (table.records_count ?? 0), 0))

  const fetchTable = async (tableId: string): Promise<TableRead> => {
    return await apiFetch<TableRead>(`/tables/${tableId}`, {
      headers: { Authorization: `Bearer ${token.value}` },
    })
  }

  const fetchRecords = async (
    tableId: string,
    opts?: { limit?: number; offset?: number }
  ): Promise<TableRecordsListResponse> => {
    const limit = opts?.limit ?? 50
    const offset = opts?.offset ?? 0
    return await apiFetch<TableRecordsListResponse>(
      `/tables/${tableId}/records?limit=${limit}&offset=${offset}`,
      { headers: { Authorization: `Bearer ${token.value}` } }
    )
  }

  const createRecord = async (tableId: string, data: Record<string, unknown>): Promise<TableRecordRead> => {
    const created = await apiFetch<TableRecordRead>(`/tables/${tableId}/records`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token.value}`,
        'Content-Type': 'application/json',
      },
      body: { data, source: 'admin' },
    })
    await fetchTables()
    return created
  }

  const updateRecord = async (
    tableId: string,
    recordId: string,
    data: Record<string, unknown>
  ): Promise<TableRecordRead> => {
    const updated = await apiFetch<TableRecordRead>(`/tables/${tableId}/records/${recordId}`, {
      method: 'PATCH',
      headers: {
        Authorization: `Bearer ${token.value}`,
        'Content-Type': 'application/json',
      },
      body: { data },
    })
    await fetchTables()
    return updated
  }

  const deleteRecord = async (tableId: string, recordId: string): Promise<void> => {
    await apiFetch(`/tables/${tableId}/records/${recordId}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token.value}` },
    })
    await fetchTables()
  }

  const bulkCreateRecords = async (
    tableId: string,
    records: Record<string, unknown>[]
  ): Promise<TableRecordsBulkCreateResponse> => {
    const res = await apiFetch<TableRecordsBulkCreateResponse>(`/tables/${tableId}/records/bulk`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token.value}`,
        'Content-Type': 'application/json',
      },
      body: { records, source: 'import' },
    })
    await fetchTables()
    return res
  }

  const updateTable = async (tableId: string, payload: { name?: string; description?: string | null }) => {
    return await apiFetch<TableRead>(`/tables/${tableId}`, {
      method: 'PATCH',
      headers: {
        Authorization: `Bearer ${token.value}`,
        'Content-Type': 'application/json',
      },
      body: payload,
    })
  }

  const createAttribute = async (
    tableId: string,
    body: {
      name: string
      label: string
      attribute_type: string
      type_config?: Record<string, unknown>
      is_required?: boolean
      is_searchable?: boolean
      is_unique?: boolean
      order_index?: number
      default_value?: unknown
    }
  ): Promise<TableAttribute> => {
    return await apiFetch<TableAttribute>(`/tables/${tableId}/attributes`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token.value}`,
        'Content-Type': 'application/json',
      },
      body,
    })
  }

  const updateAttribute = async (
    tableId: string,
    attributeId: string,
    body: {
      label?: string
      name?: string
      attribute_type?: string
      type_config?: Record<string, unknown>
      is_required?: boolean
      is_searchable?: boolean
      is_unique?: boolean
      order_index?: number
      default_value?: unknown
    }
  ) => {
    return await apiFetch(`/tables/${tableId}/attributes/${attributeId}`, {
      method: 'PATCH',
      headers: {
        Authorization: `Bearer ${token.value}`,
        'Content-Type': 'application/json',
      },
      body,
    })
  }

  const deleteAttribute = async (tableId: string, attributeId: string): Promise<void> => {
    await apiFetch(`/tables/${tableId}/attributes/${attributeId}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token.value}` },
    })
  }

  const reorderAttributes = async (tableId: string, attributeIds: string[]): Promise<void> => {
    await apiFetch(`/tables/${tableId}/attributes/reorder`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token.value}`,
        'Content-Type': 'application/json',
      },
      body: { attribute_ids: attributeIds },
    })
  }

  return {
    tables,
    isLoading,
    error,
    totalRecords,
    fetchTables,
    createTable,
    fetchTable,
    fetchRecords,
    createRecord,
    updateRecord,
    deleteRecord,
    bulkCreateRecords,
    updateTable,
    createAttribute,
    updateAttribute,
    deleteAttribute,
    reorderAttributes,
  }
}

