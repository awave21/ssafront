import { ref, computed } from 'vue'
import { useApiFetch } from './useApiFetch'
import { useAuth } from './useAuth'
import { getStoredAccessToken } from '~/composables/authSessionManager'
import { getReadableErrorMessage, getHttpStatusMessage } from '~/utils/api-errors'
import type {
  DirectoryColumn,
  Directory,
  DirectoryItem,
  CreateDirectoryPayload,
  UpdateDirectoryPayload,
  ImportResult
} from '~/types/directories'

export type { DirectoryColumn, Directory, DirectoryItem, CreateDirectoryPayload, UpdateDirectoryPayload, ImportResult }

// Поддерживаемые типы колонок: text, number, date, bool
// Предустановленные колонки по шаблонам
const TEMPLATE_COLUMNS: Record<string, DirectoryColumn[]> = {
  qa: [
    { name: 'question', label: 'Вопрос', type: 'text', required: true, searchable: true },
    { name: 'answer', label: 'Ответ', type: 'text', required: true, searchable: false },
  ],
  service_catalog: [
    { name: 'name', label: 'Название', type: 'text', required: true, searchable: true },
    { name: 'description', label: 'Описание', type: 'text', required: false, searchable: true },
    { name: 'price', label: 'Цена', type: 'number', required: false, searchable: false },
    { name: 'is_active', label: 'Активна', type: 'bool', required: false, searchable: false },
  ],
  product_catalog: [
    { name: 'name', label: 'Название', type: 'text', required: true, searchable: true },
    { name: 'description', label: 'Описание', type: 'text', required: false, searchable: true },
    { name: 'price', label: 'Цена', type: 'number', required: false, searchable: false },
    { name: 'in_stock', label: 'В наличии', type: 'bool', required: false, searchable: false },
  ],
  company_info: [
    { name: 'topic', label: 'Тема', type: 'text', required: true, searchable: true },
    { name: 'info', label: 'Информация', type: 'text', required: true, searchable: true },
  ],
  custom: [
    { name: 'field1', label: 'Поле 1', type: 'text', required: true, searchable: true },
    { name: 'field2', label: 'Поле 2', type: 'text', required: false, searchable: false },
  ],
}

export const useDirectories = (agentId: string) => {
  const apiFetch = useApiFetch()
  const { token } = useAuth()

  const directories = ref<Directory[]>([])
  const currentDirectory = ref<Directory | null>(null)
  const items = ref<DirectoryItem[]>([])
  
  const isLoading = ref(false)
  const isLoadingItems = ref(false)
  const error = ref<string | null>(null)

  const existingToolNames = computed(() => directories.value.map(d => d.tool_name))

  // Получение колонок по шаблону
  const getTemplateColumns = (template: string): DirectoryColumn[] => {
    return TEMPLATE_COLUMNS[template] || TEMPLATE_COLUMNS.custom
  }

  // Загрузка списка справочников
  const fetchDirectories = async () => {
    isLoading.value = true
    error.value = null
    
    try {
      console.log(`📂 Fetching directories for agent ${agentId}...`)
      const data = await apiFetch<Directory[]>(`/agents/${agentId}/directories`, {
        headers: { Authorization: `Bearer ${token.value}` }
      })
      directories.value = data || []
      console.log(`✅ Loaded ${directories.value.length} directories`)
    } catch (err: any) {
      const status = err?.status || err?.statusCode || err?.response?.status
      
      if (status === 404) {
        console.warn('⚠️  Directories API not implemented on backend (404)')
        error.value = 'Функция справочников пока недоступна'
        directories.value = []
      } else {
        error.value = getReadableErrorMessage(err, 'Не удалось загрузить справочники')
        console.error('Failed to fetch directories:', err)
        if (status >= 500) directories.value = []
      }
    } finally {
      isLoading.value = false
    }
  }

  // Создание справочника
  const createDirectory = async (payload: CreateDirectoryPayload): Promise<Directory | null> => {
    try {
      // Добавляем колонки из шаблона если не указаны
      const data = {
        ...payload,
        columns: payload.columns || getTemplateColumns(payload.template),
        response_mode: payload.response_mode || 'function_result',
        search_type: payload.search_type || 'fuzzy'
      }
      
      console.log('📝 Creating directory:', data.name)
      console.log('📤 Request payload:', JSON.stringify(data, null, 2))
      
      const created = await apiFetch<Directory>(`/agents/${agentId}/directories`, {
        method: 'POST',
        headers: { 
          Authorization: `Bearer ${token.value}`,
          'Content-Type': 'application/json'
        },
        body: data
      })
      
      if (!created || !created.id) {
        console.error('❌ Server returned empty or invalid response')
        throw new Error('Сервер вернул пустой ответ')
      }
      
      console.log('✅ Directory created:', created.id)
      directories.value.push(created)
      return created
    } catch (err: any) {
      const status = err?.status || err?.statusCode || err?.response?.status
      console.error('❌ Failed to create directory:', err)
      
      if (status === 409) {
        throw new Error('Справочник с таким именем уже существует')
      }
      
      throw new Error(getReadableErrorMessage(err, 'Не удалось создать справочник'))
    }
  }

  // Обновление справочника
  const updateDirectory = async (id: string, payload: UpdateDirectoryPayload): Promise<Directory | null> => {
    try {
      const updated = await apiFetch<Directory>(`/agents/${agentId}/directories/${id}`, {
        method: 'PUT',
        headers: { 
          Authorization: `Bearer ${token.value}`,
          'Content-Type': 'application/json'
        },
        body: payload
      })
      
      const index = directories.value.findIndex(d => d.id === id)
      if (index !== -1) {
        directories.value[index] = updated
      }
      
      if (currentDirectory.value?.id === id) {
        currentDirectory.value = updated
      }
      
      return updated
    } catch (err: any) {
      throw new Error(getReadableErrorMessage(err, 'Не удалось обновить справочник'))
    }
  }

  // Удаление справочника
  const deleteDirectory = async (id: string): Promise<void> => {
    try {
      await apiFetch(`/agents/${agentId}/directories/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token.value}` }
      })
      
      directories.value = directories.value.filter(d => d.id !== id)
      
      if (currentDirectory.value?.id === id) {
        currentDirectory.value = null
      }
    } catch (err: any) {
      throw new Error(getReadableErrorMessage(err, 'Не удалось удалить справочник'))
    }
  }

  // Переключение статуса справочника
  const toggleDirectory = async (id: string, enabled: boolean): Promise<void> => {
    try {
      await apiFetch(`/agents/${agentId}/directories/${id}/toggle`, {
        method: 'PATCH',
        headers: { 
          Authorization: `Bearer ${token.value}`,
          'Content-Type': 'application/json'
        },
        body: { is_enabled: enabled }
      })
      
      const index = directories.value.findIndex(d => d.id === id)
      if (index !== -1) {
        directories.value[index].is_enabled = enabled
      }
    } catch (err: any) {
      throw new Error(getReadableErrorMessage(err, 'Не удалось изменить статус справочника'))
    }
  }

  // Загрузка записей справочника
  const fetchItems = async (directoryId: string, search?: string): Promise<void> => {
    isLoadingItems.value = true
    
    try {
      const params = new URLSearchParams()
      params.append('limit', '100')
      if (search) {
        params.append('search', search)
      }
      
      const data = await apiFetch<{ items: DirectoryItem[]; total: number }>(
        `/agents/${agentId}/directories/${directoryId}/items?${params}`,
        { headers: { Authorization: `Bearer ${token.value}` } }
      )
      
      items.value = data.items
    } catch (err: any) {
      console.error('Failed to fetch items:', err)
      items.value = []
    } finally {
      isLoadingItems.value = false
    }
  }

  // Добавление записи
  const createItem = async (directoryId: string, data: Record<string, any>): Promise<DirectoryItem | null> => {
    try {
      const created = await apiFetch<DirectoryItem>(
        `/agents/${agentId}/directories/${directoryId}/items`,
        {
          method: 'POST',
          headers: { 
            Authorization: `Bearer ${token.value}`,
            'Content-Type': 'application/json'
          },
          body: { data }
        }
      )
      
      items.value.push(created)
      
      // Обновляем счётчик
      const dirIndex = directories.value.findIndex(d => d.id === directoryId)
      if (dirIndex !== -1) {
        directories.value[dirIndex].items_count++
      }
      if (currentDirectory.value?.id === directoryId) {
        currentDirectory.value.items_count++
      }
      
      return created
    } catch (err: any) {
      throw new Error(getReadableErrorMessage(err, 'Не удалось добавить запись'))
    }
  }

  // Обновление записи
  const updateItem = async (directoryId: string, itemId: string, data: Record<string, any>): Promise<DirectoryItem | null> => {
    try {
      const updated = await apiFetch<DirectoryItem>(
        `/agents/${agentId}/directories/${directoryId}/items/${itemId}`,
        {
          method: 'PUT',
          headers: { 
            Authorization: `Bearer ${token.value}`,
            'Content-Type': 'application/json'
          },
          body: { data }
        }
      )
      
      // Создаём новый массив, чтобы TanStack Table гарантированно увидел изменение
      items.value = items.value.map(i => i.id === itemId ? updated : i)
      
      return updated
    } catch (err: any) {
      throw new Error(getReadableErrorMessage(err, 'Не удалось обновить запись'))
    }
  }

  // Удаление записи
  const deleteItem = async (directoryId: string, itemId: string): Promise<void> => {
    try {
      await apiFetch(
        `/agents/${agentId}/directories/${directoryId}/items/${itemId}`,
        {
          method: 'DELETE',
          headers: { Authorization: `Bearer ${token.value}` }
        }
      )
      
      items.value = items.value.filter(i => i.id !== itemId)
      
      // Обновляем счётчик
      const dirIndex = directories.value.findIndex(d => d.id === directoryId)
      if (dirIndex !== -1) {
        directories.value[dirIndex].items_count--
      }
      if (currentDirectory.value?.id === directoryId) {
        currentDirectory.value.items_count--
      }
    } catch (err: any) {
      throw new Error(getReadableErrorMessage(err, 'Не удалось удалить запись'))
    }
  }

  // Массовое удаление записей
  const deleteItems = async (directoryId: string, ids: string[]): Promise<void> => {
    try {
      await apiFetch(
        `/agents/${agentId}/directories/${directoryId}/items`,
        {
          method: 'DELETE',
          headers: { 
            Authorization: `Bearer ${token.value}`,
            'Content-Type': 'application/json'
          },
          body: { ids }
        }
      )
      
      items.value = items.value.filter(i => !ids.includes(i.id))
      
      // Обновляем счётчик
      const dirIndex = directories.value.findIndex(d => d.id === directoryId)
      if (dirIndex !== -1) {
        directories.value[dirIndex].items_count -= ids.length
      }
      if (currentDirectory.value?.id === directoryId) {
        currentDirectory.value.items_count -= ids.length
      }
    } catch (err: any) {
      throw new Error(getReadableErrorMessage(err, 'Не удалось удалить записи'))
    }
  }

  // Импорт CSV
  const importCsv = async (
    directoryId: string,
    file: File,
    mapping: Record<string, string | null>,
    options: { hasHeader: boolean; replaceAll: boolean }
  ): Promise<ImportResult> => {
    try {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('mapping', JSON.stringify(mapping))
      formData.append('has_header', String(options.hasHeader))
      formData.append('replace_all', String(options.replaceAll))
      
      const result = await apiFetch<ImportResult>(
        `/agents/${agentId}/directories/${directoryId}/import`,
        {
          method: 'POST',
          headers: { Authorization: `Bearer ${token.value}` },
          body: formData
        }
      )
      
      // Перезагружаем записи
      await fetchItems(directoryId)
      await fetchDirectories() // Для обновления items_count
      
      return result
    } catch (err: any) {
      throw new Error(getReadableErrorMessage(err, 'Не удалось импортировать файл'))
    }
  }

  // Экспорт CSV
  const exportCsv = async (directoryId: string): Promise<void> => {
    try {
      // @ts-ignore - Nuxt 3 auto-imports
      const { public: { apiBase } } = useRuntimeConfig()
      
      // Получаем актуальный токен
      const authToken = getStoredAccessToken()
      
      if (!authToken) {
        throw new Error('Не авторизован')
      }
      
      // Используем нативный fetch для blob (apiFetch не поддерживает responseType: blob)
      const response = await fetch(
        `${apiBase}/agents/${agentId}/directories/${directoryId}/export?format=csv`,
        {
          method: 'GET',
          credentials: 'include',
          headers: { 
            'Authorization': `Bearer ${authToken}`,
            'Accept': 'text/csv'
          }
        }
      )
      
      if (!response.ok) {
        throw new Error(getHttpStatusMessage(response.status, 'Не удалось экспортировать справочник'))
      }
      
      const blob = await response.blob()
      const url = URL.createObjectURL(blob)
      
      const dir = directories.value.find(d => d.id === directoryId)
      const filename = `${dir?.slug || dir?.name || 'export'}.csv`
      
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      
      URL.revokeObjectURL(url)
    } catch (err: any) {
      console.error('❌ Export CSV error:', err)
      throw new Error(getReadableErrorMessage(err, 'Не удалось экспортировать справочник'))
    }
  }

  // Установка текущего справочника
  const setCurrentDirectory = (directory: Directory | null) => {
    currentDirectory.value = directory
    if (directory) {
      fetchItems(directory.id)
    } else {
      items.value = []
    }
  }

  return {
    // State
    directories,
    currentDirectory,
    items,
    isLoading,
    isLoadingItems,
    error,
    existingToolNames,
    
    // Methods
    fetchDirectories,
    createDirectory,
    updateDirectory,
    deleteDirectory,
    toggleDirectory,
    fetchItems,
    createItem,
    updateItem,
    deleteItem,
    deleteItems,
    importCsv,
    exportCsv,
    setCurrentDirectory,
    getTemplateColumns
  }
}
