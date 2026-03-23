<template>
  <div class="space-y-6">
    <KnowledgeSubTabs
      v-model="knowledgeSubTab"
      :tabs="knowledgeSubTabs"
    />

    <div v-if="knowledgeSubTab === 'direct_questions'">
      <DirectQuestionsList
        :questions="directQuestions"
        :loading="directQuestionsLoading"
        @create="handleOpenCreateDirectQuestion"
        @select="handleSelectDirectQuestion"
        @toggle="handleToggleDirectQuestion"
        @delete="handleDeleteDirectQuestion"
        @import-excel="handleImportDirectQuestions"
        @reorder="handleReorderDirectQuestions"
      />
    </div>

    <div v-else-if="knowledgeSubTab === 'file_uploads'">
      <FileUploadsWorkspace v-if="agent" :agent-id="agent.id" />
    </div>

    <div v-else-if="knowledgeSubTab === 'directories'">
      <div v-if="selectedDirectory">
        <DirectoryDetail
          :directory="selectedDirectory"
          :items="directoryItems"
          :loading="directoryItemsLoading"
          :on-update-item="handleUpdateItem"
          @back="handleBackToList"
          @settings="showDirectorySettingsSheet = true"
          @create="handleCreateItem"
          @delete="handleDeleteItem"
          @delete-selected="handleDeleteSelectedItems"
          @import="showImportCsvModal = true"
          @export="handleExportCsv"
          @add-column="handleAddColumn"
          @delete-column="handleDeleteColumn"
          @update-columns="handleUpdateColumns"
        />
      </div>
      <div v-else>
        <DirectoriesList
          :directories="directories"
          :loading="directoriesLoading"
          :error="directoriesError"
          @create="showCreateDirectoryModal = true"
          @select="handleSelectDirectory"
          @toggle="handleToggleDirectory"
          @settings="handleOpenDirectorySettings"
          @retry="loadDirectories"
        />
      </div>
    </div>

    <div v-else-if="knowledgeSubTab === 'sqns'">
      <div v-if="!isSqnsEnabled" class="bg-background rounded-md border border-border p-6 sm:p-8 text-center">
        <div class="max-w-md mx-auto">
          <div class="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <Database class="h-8 w-8 text-slate-400" />
          </div>
          <h3 class="text-lg font-bold text-slate-900">База знаний SQNS</h3>
          <p class="text-slate-500 mt-2 mb-6">
            Подключите SQNS интеграцию для управления услугами и категориями.
          </p>
          <button
            @click="navigateTo(`/agents/${agent?.id}/connections`)"
            class="px-6 py-3 bg-indigo-600 text-white rounded-md text-sm font-bold hover:bg-indigo-700 transition-colors"
          >
            Перейти к подключениям
          </button>
        </div>
      </div>

      <div v-else>
        <SQNSIntegrationManager
          v-if="agent"
          :agent-id="agent.id"
          :status="sqnsStatus?.sqnsStatus === 'error' ? 'error' : 'active'"
          :last-sync-at="sqnsStatus?.sqnsLastSyncAt"
          :warning="sqnsStatus?.sqnsWarning"
          @sync-complete="store.loadSqnsStatusForAgent"
        />
      </div>
    </div>

    <CreateDirectoryModal
      :is-open="showCreateDirectoryModal"
      :existing-tool-names="directoriesComposable?.existingToolNames ?? []"
      @close="showCreateDirectoryModal = false"
      @submit="handleCreateDirectory"
    />

    <ImportCsvModal
      v-if="selectedDirectory"
      :is-open="showImportCsvModal"
      :directory-name="selectedDirectory.name"
      :columns="selectedDirectory.columns"
      @close="showImportCsvModal = false"
      @import="handleImportCsv"
    />

    <DirectorySettingsSheet
      ref="directorySettingsSheetRef"
      :is-open="showDirectorySettingsSheet"
      :directory="selectedDirectory"
      :existing-tool-names="directoriesComposable?.existingToolNames ?? []"
      @close="showDirectorySettingsSheet = false"
      @save="handleSaveDirectorySettings"
      @delete="handleDeleteDirectoryFromSettings"
    />

    <DirectQuestionEditor
      :open="showDirectQuestionEditor"
      :question="selectedDirectQuestion"
      :saving="isSavingDirectQuestion"
      @close="showDirectQuestionEditor = false"
      @save="handleSaveDirectQuestion"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, shallowRef, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { Database } from 'lucide-vue-next'
import { navigateTo, useRoute, useRouter } from '#app'
import { useAgentEditorStore } from '~/composables/useAgentEditorStore'
import { useToast } from '~/composables/useToast'
import type { Directory } from '~/types/directories'
import KnowledgeSubTabs from '~/components/knowledge/KnowledgeSubTabs.vue'
import DirectoriesList from '~/components/knowledge/DirectoriesList.vue'
import DirectoryDetail from '~/components/knowledge/DirectoryDetail.vue'
import CreateDirectoryModal from '~/components/knowledge/CreateDirectoryModal.vue'
import ImportCsvModal from '~/components/knowledge/ImportCsvModal.vue'
import DirectorySettingsSheet from '~/components/knowledge/DirectorySettingsSheet.vue'
import SQNSIntegrationManager from '~/components/SQNSIntegrationManager.vue'
import FileUploadsWorkspace from '~/components/knowledge/FileUploadsWorkspace.vue'

import { useKnowledge } from '~/composables/useKnowledge'
import DirectQuestionsList from '~/components/knowledge/DirectQuestionsList.vue'
import DirectQuestionEditor from '~/components/knowledge/DirectQuestionEditor.vue'
import type { DirectQuestion, CreateDirectQuestionPayload } from '~/types/knowledge'

const store = useAgentEditorStore()
const route = useRoute()
const router = useRouter()
const { agent, directoriesComposable, isSqnsEnabled, sqnsToolsList, sqnsStatus } = storeToRefs(store)
const { success: toastSuccess, error: toastError } = useToast()

const knowledgeSubTab = ref<'sqns' | 'directories' | 'direct_questions' | 'file_uploads'>('direct_questions')
const showCreateDirectoryModal = ref(false)
const showImportCsvModal = ref(false)
const showDirectorySettingsSheet = ref(false)
const directorySettingsSheetRef = ref<InstanceType<typeof DirectorySettingsSheet> | null>(null)

const showDirectQuestionEditor = ref(false)
const selectedDirectQuestion = ref<DirectQuestion | null>(null)
const isSavingDirectQuestion = ref(false)

/** Один экземпляр на agentId — иначе `useKnowledge` в computed создавал бы новый state и список не обновлялся */
const knowledgeApi = shallowRef<ReturnType<typeof useKnowledge> | null>(null)
watch(
  () => agent.value?.id,
  (id) => {
    knowledgeApi.value = id ? useKnowledge(id) : null
  },
  { immediate: true }
)

const directQuestions = computed(() => knowledgeApi.value?.directQuestions.value ?? [])
const directQuestionsLoading = computed(() => knowledgeApi.value?.isLoading.value ?? false)

const directories = computed(() => directoriesComposable.value?.directories ?? [])
const directoriesLoading = computed(() => directoriesComposable.value?.isLoading ?? false)
const directoriesError = computed(() => directoriesComposable.value?.error ?? null)
const directoryItems = computed(() => directoriesComposable.value?.items ?? [])
const directoryItemsLoading = computed(() => directoriesComposable.value?.isLoadingItems ?? false)
const selectedDirectory = computed(() => directoriesComposable.value?.currentDirectory ?? null)

const knowledgeSubTabs = computed(() => [
  { id: 'direct_questions', label: 'Прямые вопросы', count: directQuestions.value.length },
  { id: 'file_uploads', label: 'Загрузка файлов' },
  { id: 'directories', label: 'Справочники', count: directories.value.length },
  { id: 'sqns', label: 'SQNS', count: isSqnsEnabled.value ? sqnsToolsList.value.length : undefined }
])

const isValidKnowledgeSubTab = (value: string): value is 'sqns' | 'directories' | 'direct_questions' | 'file_uploads' =>
  value === 'sqns' || value === 'directories' || value === 'direct_questions' || value === 'file_uploads'

const getKnowledgeTabStorageKey = () => `agent-knowledge-subtab:${agent.value?.id ?? 'unknown'}`

const syncKnowledgeTabToQuery = (tab: 'sqns' | 'directories' | 'direct_questions' | 'file_uploads') => {
  if ((route.query.knowledgeTab as string | undefined) === tab) return
  router.replace({
    query: {
      ...route.query,
      knowledgeTab: tab
    }
  })
}

const restoreKnowledgeTabState = () => {
  const tabFromQuery = route.query.knowledgeTab as string | undefined
  if (tabFromQuery && isValidKnowledgeSubTab(tabFromQuery)) {
    knowledgeSubTab.value = tabFromQuery
    return
  }

  if (typeof window !== 'undefined') {
    const tabFromStorage = window.localStorage.getItem(getKnowledgeTabStorageKey())
    if (tabFromStorage && isValidKnowledgeSubTab(tabFromStorage)) {
      knowledgeSubTab.value = tabFromStorage
      syncKnowledgeTabToQuery(tabFromStorage)
      return
    }
  }
  
  // Default tab
  knowledgeSubTab.value = 'direct_questions'
}

const loadDirectories = async () => {
  await store.ensureDirectoriesLoaded()
}

const loadDirectQuestions = async () => {
  if (knowledgeApi.value) {
    await knowledgeApi.value.fetchDirectQuestions()
  }
}

// Восстановление выбранного справочника из URL query при загрузке
const restoreDirectoryFromQuery = () => {
  const directoryId = route.query.directoryId as string | undefined
  if (!directoryId || !directoriesComposable.value) return
  // Если справочник уже выбран — не трогаем
  if (selectedDirectory.value?.id === directoryId) return
  const dir = directories.value.find(d => d.id === directoryId)
  if (dir) {
    directoriesComposable.value.setCurrentDirectory(dir)
  }
}

// Следим за загрузкой directories, чтобы восстановить выбранный справочник из query
watch(directories, (newDirs) => {
  if (newDirs.length > 0) {
    restoreDirectoryFromQuery()
  }
})

watch(selectedDirectory, (dir) => {
  if (dir) return

  const { directoryId, ...rest } = route.query
  if (!directoryId) return

  router.replace({
    query: rest
  })
})

onMounted(() => {
  restoreKnowledgeTabState()
  if (knowledgeSubTab.value === 'directories') {
    store.ensureDirectoriesLoaded()
  } else if (knowledgeSubTab.value === 'direct_questions') {
    loadDirectQuestions()
  } else if (knowledgeSubTab.value === 'file_uploads') {
    // loaded inside FileUploadsWorkspace
  } else {
    store.ensureSqnsStatusLoaded()
    store.ensureSqnsHints()
  }
})

watch(agent, async (value) => {
  if (!value) return
  if (knowledgeSubTab.value === 'directories') {
    await store.ensureDirectoriesLoaded()
  } else if (knowledgeSubTab.value === 'direct_questions') {
    await loadDirectQuestions()
  } else if (knowledgeSubTab.value === 'file_uploads') {
    return
  } else {
    await store.ensureSqnsStatusLoaded()
    await store.ensureSqnsHints()
  }
}, { immediate: true })

watch(knowledgeSubTab, async (value) => {
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(getKnowledgeTabStorageKey(), value)
  }
  syncKnowledgeTabToQuery(value)

  if (value === 'directories') {
    await store.ensureDirectoriesLoaded()
  } else if (value === 'direct_questions') {
    await loadDirectQuestions()
  } else if (value === 'file_uploads') {
    return
  } else {
    await store.ensureSqnsStatusLoaded()
    await store.ensureSqnsHints()
  }
})

watch(() => route.query.knowledgeTab, (tabValue) => {
  const parsed = typeof tabValue === 'string' ? tabValue : undefined
  if (!parsed || !isValidKnowledgeSubTab(parsed)) return
  if (knowledgeSubTab.value === parsed) return
  knowledgeSubTab.value = parsed
})

const handleOpenCreateDirectQuestion = () => {
  selectedDirectQuestion.value = null
  showDirectQuestionEditor.value = true
}

const handleSelectDirectQuestion = (q: DirectQuestion) => {
  selectedDirectQuestion.value = q
  showDirectQuestionEditor.value = true
}

const handleSaveDirectQuestion = async (data: CreateDirectQuestionPayload) => {
  if (!knowledgeApi.value) return
  isSavingDirectQuestion.value = true
  try {
    if (selectedDirectQuestion.value) {
      await knowledgeApi.value.updateDirectQuestion(selectedDirectQuestion.value.id, data)
      toastSuccess('Вопрос обновлен')
    } else {
      await knowledgeApi.value.createDirectQuestion(data)
      toastSuccess('Вопрос создан')
    }
    await loadDirectQuestions()
    showDirectQuestionEditor.value = false
    selectedDirectQuestion.value = null
  } catch (err: any) {
    toastError(err.message || 'Не удалось сохранить вопрос')
  } finally {
    isSavingDirectQuestion.value = false
  }
}

const handleToggleDirectQuestion = async (id: string, enabled: boolean) => {
  if (!knowledgeApi.value) return
  try {
    await knowledgeApi.value.toggleDirectQuestion(id, enabled)
    toastSuccess(enabled ? 'Вопрос включен' : 'Вопрос выключен')
  } catch (err: any) {
    toastError(err.message || 'Не удалось изменить статус')
  }
}

const handleDeleteDirectQuestion = async (id: string) => {
  if (!knowledgeApi.value) return
  if (!confirm('Вы уверены, что хотите удалить этот вопрос?')) return
  try {
    await knowledgeApi.value.deleteDirectQuestion(id)
    toastSuccess('Вопрос удален')
  } catch (err: any) {
    toastError(err.message || 'Не удалось удалить вопрос')
  }
}

const handleReorderDirectQuestions = async (ids: string[]) => {
  if (!knowledgeApi.value) return
  try {
    await knowledgeApi.value.reorderDirectQuestions(ids)
    await loadDirectQuestions()
  } catch (err: any) {
    toastError(err.message || 'Не удалось сохранить порядок прямых вопросов')
  }
}

const CP1251_REVERSE_MAP: Record<string, number> = (() => {
  const decoder = new TextDecoder('windows-1251')
  const map: Record<string, number> = {}

  for (let byte = 0; byte <= 255; byte += 1) {
    const char = decoder.decode(new Uint8Array([byte]))
    if (!(char in map)) map[char] = byte
  }

  return map
})()

const looksLikeCp1251Mojibake = (value: string): boolean => {
  const pairMatches = countMatches(value, /[РС][^\s]/g)
  const weirdMatches = countMatches(value, /[ЃЌЋЏ]/g)
  const markerMatches = countMatches(value, /[РСÐÑ]/g)
  return pairMatches >= 2 || weirdMatches >= 1 || markerMatches >= 4
}

const repairUtf8FromCp1251Mojibake = (value: string): string => {
  if (!value || !looksLikeCp1251Mojibake(value)) return value

  const bytes: number[] = []
  for (const char of value) {
    const mapped = CP1251_REVERSE_MAP[char]
    if (mapped === undefined) return value
    bytes.push(mapped)
  }

  let repaired = value
  try {
    repaired = new TextDecoder('utf-8', { fatal: false }).decode(new Uint8Array(bytes))
  } catch {
    return value
  }

  const originalScore = estimateCyrillicDecodeScore(value)
  const repairedScore = estimateCyrillicDecodeScore(repaired)
  return repairedScore > originalScore ? repaired : value
}

const normalizeCell = (value: unknown): string => {
  const source = String(value ?? '').trim()
  return repairUtf8FromCp1251Mojibake(source).trim()
}

const countMatches = (value: string, pattern: RegExp): number => value.match(pattern)?.length ?? 0

const estimateCyrillicDecodeScore = (value: string): number => {
  const cyrillicCount = countMatches(value, /[А-Яа-яЁё]/g)
  const latinCount = countMatches(value, /[A-Za-z]/g)
  const replacementCount = countMatches(value, /\uFFFD/g)
  // Typical mojibake: UTF-8 Cyrillic decoded as cp1251 => "РїРѕС‡Рµ..."
  const mojibakeRuPairs = countMatches(value, /[РС][а-яё]/g)
  const mojibakeWeird = countMatches(value, /[ЃЌЋЏ]/g)
  const mojibakeCount = countMatches(value, /[ÐÑ]/g)
  return (
    cyrillicCount
    + latinCount
    - replacementCount * 10
    - mojibakeCount * 4
    - mojibakeRuPairs * 3
    - mojibakeWeird * 2
  )
}

const decodeCsvBuffer = (buffer: ArrayBuffer): string => {
  const bytes = new Uint8Array(buffer)
  const utf8Decoded = new TextDecoder('utf-8').decode(bytes).replace(/^\uFEFF/, '')

  let bestDecoded = utf8Decoded
  let bestScore = estimateCyrillicDecodeScore(utf8Decoded)

  try {
    const cp1251Decoded = new TextDecoder('windows-1251').decode(bytes).replace(/^\uFEFF/, '')
    const cp1251Score = estimateCyrillicDecodeScore(cp1251Decoded)
    if (cp1251Score > bestScore) {
      bestDecoded = cp1251Decoded
      bestScore = cp1251Score
    }
  } catch {
    // Some environments may not support windows-1251 decoder.
  }

  return bestDecoded
}

const readWorkbookFromFile = async (file: File) => {
  const XLSX = await import('xlsx')
  const buffer = await file.arrayBuffer()
  const isCsv = file.name.toLowerCase().endsWith('.csv')

  if (!isCsv) {
    return XLSX.read(buffer, { type: 'array' })
  }

  const decodedCsv = decodeCsvBuffer(buffer)
  return XLSX.read(decodedCsv, { type: 'string' })
}

const parseDirectQuestionRows = (rows: unknown[][]) => {
  if (!rows.length) return [] as Array<{ title: string; content: string }>

  const firstRow = rows[0] ?? []
  const firstCell = normalizeCell(firstRow[0]).toLowerCase()
  const secondCell = normalizeCell(firstRow[1]).toLowerCase()
  const hasHeader = (
    ['title', 'название'].includes(firstCell)
    && ['description', 'описание', 'content', 'содержание'].includes(secondCell)
  )

  const dataRows = hasHeader ? rows.slice(1) : rows
  return dataRows
    .map((row) => {
      const title = normalizeCell(row?.[0])
      const content = normalizeCell(row?.[1])
      return { title, content }
    })
    .filter((item) => item.title && item.content)
}

const createSearchTitleTranslator = () => {
  const cache = new Map<string, string>()

  return async (title: string): Promise<string> => {
    const normalizedTitle = title.trim()
    if (!normalizedTitle) return ''

    const cached = cache.get(normalizedTitle)
    if (cached) return cached

    try {
      const translated = (await knowledgeApi.value?.translateSearchTitle(normalizedTitle))?.trim()
      const searchTitle = translated || normalizedTitle
      cache.set(normalizedTitle, searchTitle)
      return searchTitle
    } catch {
      cache.set(normalizedTitle, normalizedTitle)
      return normalizedTitle
    }
  }
}

const handleImportDirectQuestions = async (file: File) => {
  if (!knowledgeApi.value) return

  try {
    const XLSX = await import('xlsx')
    const workbook = await readWorkbookFromFile(file)
    const firstSheetName = workbook.SheetNames[0]
    if (!firstSheetName) {
      toastError('Файл пустой')
      return
    }

    const worksheet = workbook.Sheets[firstSheetName]
    const rawRows = XLSX.utils.sheet_to_json(worksheet, {
      header: 1,
      blankrows: false,
      defval: '',
      raw: false
    }) as unknown[][]

    const parsed = parseDirectQuestionRows(rawRows)
    if (!parsed.length) {
      toastError('Не найдено валидных строк. Нужны 2 колонки: title и описание')
      return
    }

    let created = 0
    let failed = 0
    const resolveSearchTitle = createSearchTitleTranslator()

    for (const row of parsed) {
      try {
        const searchTitle = await resolveSearchTitle(row.title)
        await knowledgeApi.value.createDirectQuestion({
          title: row.title,
          search_title: searchTitle,
          content: row.content,
          tags: [],
          is_enabled: true,
          interrupt_dialog: false,
          notify_telegram: false,
          files: [],
          followup: {
            enabled: false,
            content: '',
            delay_minutes: 60
          }
        })
        created += 1
      } catch {
        failed += 1
      }
    }

    await loadDirectQuestions()
    if (failed > 0) {
      toastSuccess(`Импортировано ${created}, пропущено ${failed}`)
      return
    }
    toastSuccess(`Импортировано ${created} вопросов`)
  } catch (err: any) {
    toastError(err.message || 'Не удалось импортировать прямые вопросы')
  }
}

const handleCreateDirectory = async (data: any) => {
  if (!directoriesComposable.value) return
  try {
    await directoriesComposable.value.createDirectory(data)
    showCreateDirectoryModal.value = false
    toastSuccess('Справочник создан')
  } catch (err: any) {
    toastError(err.message || 'Не удалось создать справочник')
  }
}

const handleSelectDirectory = (dir: Directory) => {
  if (directoriesComposable.value) {
    directoriesComposable.value.setCurrentDirectory(dir)
    // Сохраняем ID справочника в query, чтобы при перезагрузке он восстановился
    router.replace({ query: { ...route.query, directoryId: dir.id } })
  }
}

const handleOpenDirectorySettings = (dir: Directory) => {
  if (!directoriesComposable.value) return
  directoriesComposable.value.setCurrentDirectory(dir)
  showDirectorySettingsSheet.value = true
}

const handleToggleDirectory = async (id: string, enabled: boolean) => {
  if (!directoriesComposable.value) return

  try {
    await directoriesComposable.value.updateDirectory(id, { is_enabled: enabled })
    toastSuccess(enabled ? 'Справочник включён' : 'Справочник выключен')
  } catch (err: any) {
    toastError(err.message || 'Не удалось изменить статус справочника')
  }
}

const handleBackToList = () => {
  if (directoriesComposable.value) {
    directoriesComposable.value.setCurrentDirectory(null)
    // Убираем directoryId из query
    const { directoryId, ...rest } = route.query
    router.replace({ query: rest })
  }
}

const handleCreateItem = async (data: Record<string, any>) => {
  if (!directoriesComposable.value || !selectedDirectory.value) return
  try {
    await directoriesComposable.value.createItem(selectedDirectory.value.id, data)
    toastSuccess('Запись добавлена')
  } catch (err: any) {
    toastError(err.message || 'Не удалось создать запись')
  }
}

const handleUpdateItem = async (itemId: string, data: Record<string, any>) => {
  if (!directoriesComposable.value || !selectedDirectory.value) return
  try {
    await directoriesComposable.value.updateItem(selectedDirectory.value.id, itemId, data)
  } catch (err: any) {
    toastError(err.message || 'Не удалось обновить запись')
  }
}

const handleDeleteItem = async (itemId: string) => {
  if (!directoriesComposable.value || !selectedDirectory.value) return
  try {
    await directoriesComposable.value.deleteItem(selectedDirectory.value.id, itemId)
    toastSuccess('Запись удалена')
  } catch (err: any) {
    toastError(err.message || 'Не удалось удалить запись')
  }
}

const handleDeleteSelectedItems = async (ids: string[]) => {
  if (!directoriesComposable.value || !selectedDirectory.value) return
  try {
    await directoriesComposable.value.deleteItems(selectedDirectory.value.id, ids)
    toastSuccess('Записи удалены')
  } catch (err: any) {
    toastError(err.message || 'Не удалось удалить записи')
  }
}

const handleImportCsv = async (file: File, mapping: Record<string, string | null>, options: { hasHeader: boolean; replaceAll: boolean }) => {
  if (!directoriesComposable.value || !selectedDirectory.value) return
  try {
    const result = await directoriesComposable.value.importCsv(selectedDirectory.value.id, file, mapping, options)
    showImportCsvModal.value = false
    toastSuccess(`Импортировано ${result.created} записей`)
  } catch (err: any) {
    toastError(err.message || 'Не удалось импортировать файл')
  }
}

const handleExportCsv = async () => {
  if (!directoriesComposable.value || !selectedDirectory.value) return
  try {
    await directoriesComposable.value.exportCsv(selectedDirectory.value.id)
  } catch (err: any) {
    toastError(err.message || 'Не удалось экспортировать справочник')
  }
}

const handleAddColumn = async (column: any) => {
  if (!directoriesComposable.value || !selectedDirectory.value) return
  try {
    const updatedColumns = [...selectedDirectory.value.columns, column]
    await directoriesComposable.value.updateDirectory(selectedDirectory.value.id, {
      columns: updatedColumns
    })
    toastSuccess('Столбец добавлен')
  } catch (err: any) {
    toastError(err.message || 'Не удалось добавить столбец')
  }
}

const handleDeleteColumn = async (columnName: string) => {
  if (!directoriesComposable.value || !selectedDirectory.value) return
  try {
    const updatedColumns = selectedDirectory.value.columns.filter(c => c.name !== columnName)
    if (updatedColumns.length === 0) {
      toastError('Нельзя удалить последний столбец')
      return
    }
    await directoriesComposable.value.updateDirectory(selectedDirectory.value.id, {
      columns: updatedColumns
    })
    toastSuccess('Столбец удалён')
  } catch (err: any) {
    toastError(err.message || 'Не удалось удалить столбец')
  }
}

const handleUpdateColumns = async (columns: any[]) => {
  if (!directoriesComposable.value || !selectedDirectory.value) return
  try {
    await directoriesComposable.value.updateDirectory(selectedDirectory.value.id, {
      columns
    })
  } catch (err: any) {
    toastError(err.message || 'Не удалось обновить столбцы')
  }
}

const handleSaveDirectorySettings = async (data: any) => {
  if (!directoriesComposable.value || !data.id) return
  try {
    await directoriesComposable.value.updateDirectory(data.id, data)
    showDirectorySettingsSheet.value = false
    toastSuccess('Настройки сохранены')
  } catch (err: any) {
    directorySettingsSheetRef.value?.setError(err.message || 'Не удалось сохранить настройки')
    toastError(err.message || 'Не удалось сохранить настройки')
  } finally {
    directorySettingsSheetRef.value?.setSaving(false)
  }
}

const handleDeleteDirectoryFromSettings = async (id: string) => {
  if (!directoriesComposable.value) return
  try {
    await directoriesComposable.value.deleteDirectory(id)
    showDirectorySettingsSheet.value = false
    // Убираем directoryId из query после удаления
    const { directoryId, ...rest } = route.query
    router.replace({ query: rest })
    toastSuccess('Справочник удалён')
  } catch (err: any) {
    directorySettingsSheetRef.value?.setError(err.message || 'Не удалось удалить справочник')
    toastError(err.message || 'Не удалось удалить справочник')
  } finally {
    directorySettingsSheetRef.value?.setDeleting(false)
    // Safety net for known Dialog/Sheet body lock edge-cases:
    // ensure stale body styles don't keep the page unclickable.
    if (typeof document !== 'undefined') {
      window.requestAnimationFrame(() => {
        document.body.style.pointerEvents = ''
        document.body.style.overflow = ''
      })
    }
  }
}
</script>
