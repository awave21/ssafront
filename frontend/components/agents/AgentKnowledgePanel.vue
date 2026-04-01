<template>
  <div class="flex min-h-0 min-w-0 w-full flex-1 flex-col gap-6">
    <div v-if="knowledgeSubTab === 'dashboard'">
      <KnowledgeDashboard
        :direct-questions="directQuestions"
        :directories="directories.filter(d => d.template !== 'custom')"
        :tables="tables"
        :files="knowledgeFilesApi?.allItems.value ?? []"
        :sqns-tools="sqnsToolsList"
        :is-sqns-enabled="isSqnsEnabled"
        @select="(tab) => knowledgeSubTab = tab as any"
      />
    </div>

    <div v-else-if="knowledgeSubTab === 'direct_questions'">
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
      <KnowledgeRagTestWidget v-if="agent" :agent-id="agent.id" />
    </div>

    <div v-else-if="knowledgeSubTab === 'directories'">
      <div v-if="selectedDirectory">
        <DirectoryDetail
          :directory="selectedDirectory"
          :items="directoryItems"
          :loading="directoryItemsLoading"
          :on-update-item="handleUpdateItem"
          :on-create-item="handleCreateItem"
          @settings="showDirectorySettingsSheet = true"
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
          :directories="visibleDirectories"
          :loading="directoriesLoading"
          :error="directoriesError"
          @create="showCreateDirectoryModal = true"
          @select="handleSelectDirectory"
          @toggle="handleToggleDirectory"
          @settings="handleOpenDirectorySettings"
          @delete="handleDeleteDirectoryFromList"
          @retry="loadDirectories"
        />
      </div>
    </div>

    <div v-else-if="knowledgeSubTab === 'tables'" class="flex min-h-0 w-full flex-1 flex-col min-w-0">
      <TableDetail
        v-if="selectedTableId && tablesApi"
        :table-id="selectedTableId"
        :tables-api="tablesApi"
      />
      <TablesList
        v-else
        :tables="tables"
        :loading="tablesLoading"
        :error="tablesError"
        @create="showCreateTableModal = true"
        @retry="loadTables"
        @select="handleSelectTable"
      />
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
      ref="createDirectoryModalRef"
      :is-open="showCreateDirectoryModal"
      :existing-tool-names="directoriesComposable?.existingToolNames ?? []"
      :mode="knowledgeSubTab === 'tables' ? 'table' : 'directory'"
      @close="showCreateDirectoryModal = false"
      @submit="handleCreateDirectory"
    />
    <CreateTableModal
      ref="createTableModalRef"
      :is-open="showCreateTableModal"
      @close="showCreateTableModal = false"
      @submit="handleCreateTable"
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
import { computed, nextTick, onMounted, onUnmounted, ref, shallowRef, watch } from 'vue'
import { storeToRefs } from 'pinia'
import KnowledgeDashboard from '~/components/knowledge/KnowledgeDashboard.vue'
import { Database } from 'lucide-vue-next'
import { navigateTo, useRoute, useRouter } from '#app'
import { useAgentEditorStore } from '~/composables/useAgentEditorStore'
import { useToast } from '~/composables/useToast'
import type { Directory } from '~/types/directories'
import {
  useLayoutState,
  type LayoutBreadcrumbSegment,
  type KnowledgeBreadcrumbTab,
} from '~/composables/useLayoutState'
import DirectoriesList from '~/components/knowledge/DirectoriesList.vue'
import DirectoryDetail from '~/components/knowledge/DirectoryDetail.vue'
import CreateDirectoryModal from '~/components/knowledge/CreateDirectoryModal.vue'
import CreateTableModal from '~/components/knowledge/CreateTableModal.vue'
import ImportCsvModal from '~/components/knowledge/ImportCsvModal.vue'
import DirectorySettingsSheet from '~/components/knowledge/DirectorySettingsSheet.vue'
import TablesList from '~/components/knowledge/TablesList.vue'
import TableDetail from '~/components/knowledge/TableDetail.vue'
import SQNSIntegrationManager from '~/components/SQNSIntegrationManager.vue'
import FileUploadsWorkspace from '~/components/knowledge/FileUploadsWorkspace.vue'
import KnowledgeRagTestWidget from '~/components/knowledge/KnowledgeRagTestWidget.vue'

import { useKnowledge } from '~/composables/useKnowledge'
import { useKnowledgeFiles } from '~/composables/useKnowledgeFiles'
import { useTables } from '~/composables/useTables'
import DirectQuestionsList from '~/components/knowledge/DirectQuestionsList.vue'
import DirectQuestionEditor from '~/components/knowledge/DirectQuestionEditor.vue'
import type { DirectQuestion, CreateDirectQuestionPayload } from '~/types/knowledge'
import type { TableItem } from '~/types/tables'
import { decodeCsvBuffer, estimateCyrillicDecodeScore } from '~/utils/csvTextDecode'

const store = useAgentEditorStore()
const route = useRoute()
const router = useRouter()
const { layoutBreadcrumbSegments, pendingBreadcrumbAction } = useLayoutState()
const { agent, directoriesComposable, isSqnsEnabled, sqnsToolsList, sqnsStatus } = storeToRefs(store)
const { success: toastSuccess, error: toastError } = useToast()

type KnowledgeSubTabId = 'sqns' | 'directories' | 'direct_questions' | 'file_uploads' | 'tables' | 'dashboard'

const isValidKnowledgeSubTab = (value: string): value is KnowledgeSubTabId =>
  value === 'sqns' ||
  value === 'directories' ||
  value === 'direct_questions' ||
  value === 'file_uploads' ||
  value === 'tables' ||
  value === 'dashboard'

const queryString = (value: unknown): string | undefined => {
  if (typeof value === 'string' && value.length > 0) return value
  if (Array.isArray(value) && typeof value[0] === 'string' && value[0].length > 0) return value[0]
  return undefined
}

const initialTableId = queryString(route.query.tableId)
const initialKnowledgeTabStr = queryString(route.query.knowledgeTab)

const knowledgeSubTab = ref<KnowledgeSubTabId>(
  initialTableId
    ? 'tables'
    : initialKnowledgeTabStr && isValidKnowledgeSubTab(initialKnowledgeTabStr)
      ? initialKnowledgeTabStr
      : 'dashboard'
)
const showCreateDirectoryModal = ref(false)
const showImportCsvModal = ref(false)
const showDirectorySettingsSheet = ref(false)
const directorySettingsSheetRef = ref<InstanceType<typeof DirectorySettingsSheet> | null>(null)
const createDirectoryModalRef = ref<InstanceType<typeof CreateDirectoryModal> | null>(null)
const createTableModalRef = ref<InstanceType<typeof CreateTableModal> | null>(null)
const showCreateTableModal = ref(false)
const selectedTableId = ref<string | null>(initialTableId ?? null)

const showDirectQuestionEditor = ref(false)
const selectedDirectQuestion = ref<DirectQuestion | null>(null)
const isSavingDirectQuestion = ref(false)

/** Один экземпляр на agentId — иначе `useKnowledge` в computed создавал бы новый state и список не обновлялся */
const knowledgeApi = shallowRef<ReturnType<typeof useKnowledge> | null>(null)
const knowledgeFilesApi = shallowRef<ReturnType<typeof useKnowledgeFiles> | null>(null)
const tablesApi = shallowRef<ReturnType<typeof useTables> | null>(null)

watch(
  () => agent.value?.id,
  (id) => {
    knowledgeApi.value = id ? useKnowledge(id) : null
    knowledgeFilesApi.value = id ? useKnowledgeFiles(id) : null
    tablesApi.value = id ? useTables() : null
    if (id) {
      knowledgeFilesApi.value?.fetchItems()
    }
  },
  { immediate: true }
)

const directQuestions = computed(() => knowledgeApi.value?.directQuestions.value ?? [])
const directQuestionsLoading = computed(() => knowledgeApi.value?.isLoading.value ?? false)

const directories = computed(() => directoriesComposable.value?.directories ?? [])
const visibleDirectories = computed(() => directories.value.filter((directory) => directory.template !== 'custom'))
const tables = computed<TableItem[]>(() => tablesApi.value?.tables.value ?? [])
const tablesLoading = computed(() => tablesApi.value?.isLoading.value ?? false)
const tablesError = computed(() => tablesApi.value?.error.value ?? null)
const directoriesLoading = computed(() => directoriesComposable.value?.isLoading ?? false)
const directoriesError = computed(() => directoriesComposable.value?.error ?? null)
const directoryItems = computed(() => directoriesComposable.value?.items ?? [])
const directoryItemsLoading = computed(() => directoriesComposable.value?.isLoadingItems ?? false)
const selectedDirectory = computed(() => directoriesComposable.value?.currentDirectory ?? null)

const knowledgeSubTabs = computed(() => [
  { id: 'direct_questions', label: 'Прямые вопросы', count: directQuestions.value.length },
  { id: 'directories', label: 'Справочники', count: directories.value.filter((directory) => directory.template !== 'custom').length },
  { id: 'tables', label: 'Таблицы', count: tables.value.length },
  { id: 'file_uploads', label: 'Загрузка файлов' },
  { id: 'sqns', label: 'SQNS', count: isSqnsEnabled.value ? sqnsToolsList.value.length : undefined }
])

const loadDirectories = async () => {
  await store.ensureDirectoriesLoaded()
}

const loadDirectQuestions = async () => {
  if (knowledgeApi.value) {
    await knowledgeApi.value.fetchDirectQuestions()
  }
}

const loadTables = async () => {
  if (tablesApi.value) await tablesApi.value.fetchTables()
}

const handleSelectTable = (tableId: string) => {
  selectedTableId.value = tableId
  router.replace({ query: { ...route.query, knowledgeTab: 'tables', tableId } })
}

const handleBackFromTable = () => {
  selectedTableId.value = null
  const { tableId: _tid, ...rest } = route.query
  router.replace({ query: { ...rest, knowledgeTab: 'tables' } })
}

/** Загрузка данных под вкладку. Активная вкладка и открытая таблица дублируются в query (`knowledgeTab`, `tableId`) для перезагрузки страницы. */
const loadDataForKnowledgeSubTab = async (tab: KnowledgeSubTabId) => {
  if (tab === 'directories' || tab === 'tables') {
    if (tab === 'directories') await store.ensureDirectoriesLoaded()
    else await loadTables()
  } else if (tab === 'direct_questions') {
    await loadDirectQuestions()
  } else if (tab === 'file_uploads') {
    return
  } else if (tab === 'dashboard') {
    await Promise.all([
      loadDirectQuestions(),
      store.ensureDirectoriesLoaded(),
      loadTables(),
      store.ensureSqnsStatusLoaded(),
      store.ensureSqnsHints()
    ])
  } else {
    await store.ensureSqnsStatusLoaded()
    await store.ensureSqnsHints()
  }
}

const handleCreateTable = async (data: {
  name: string
  description?: string
  attributes: Array<{
    name: string
    label: string
    attribute_type: string
    type_config: Record<string, unknown>
    is_required: boolean
    is_searchable: boolean
    is_unique: boolean
  }>
}) => {
  if (!tablesApi.value) {
    createTableModalRef.value?.setSubmitting(false)
    return
  }
  try {
    await tablesApi.value.createTable({
      name: data.name,
      description: data.description,
      attributes: data.attributes.map((attribute, index) => ({
        name: attribute.name,
        label: attribute.label,
        attribute_type: attribute.attribute_type as any,
        type_config: attribute.type_config ?? {},
        is_required: !!attribute.is_required,
        is_searchable: !!attribute.is_searchable,
        is_unique: !!attribute.is_unique,
        order_index: index,
      })),
    })
    showCreateTableModal.value = false
    toastSuccess('Таблица создана')
  } catch (err: any) {
    const message = err.message || 'Не удалось создать таблицу'
    createTableModalRef.value?.setError(message)
    toastError(message)
  } finally {
    createTableModalRef.value?.setSubmitting(false)
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

watch(agent, async (value) => {
  if (!value) return
  await loadDataForKnowledgeSubTab(knowledgeSubTab.value)
}, { immediate: true })

watch(knowledgeSubTab, async (value) => {
  if (!agent.value) return
  if (value !== 'tables') {
    selectedTableId.value = null
    const q: Record<string, unknown> = { ...route.query }
    delete q.tableId
    if (value === 'dashboard') {
      delete q.knowledgeTab
    } else {
      q.knowledgeTab = value
    }
    router.replace({ query: q as Record<string, string | string[] | undefined> })
  } else {
    const q: Record<string, unknown> = { ...route.query }
    q.knowledgeTab = 'tables'
    if (selectedTableId.value) {
      q.tableId = selectedTableId.value
    } else {
      delete q.tableId
    }
    router.replace({ query: q as Record<string, string | string[] | undefined> })
  }
  await loadDataForKnowledgeSubTab(value)
})

onMounted(() => {
  nextTick(() => {
    if (selectedTableId.value && queryString(route.query.knowledgeTab) !== 'tables') {
      router.replace({ query: { ...route.query, knowledgeTab: 'tables' } })
    }
  })
})

watch([tables, tablesLoading, tablesError], () => {
  const tid = selectedTableId.value
  if (!tid || tablesLoading.value || tablesError.value) return
  if (!tables.value.some((t) => t.id === tid)) {
    selectedTableId.value = null
    const { tableId: _t, ...rest } = route.query
    router.replace({ query: { ...rest, knowledgeTab: 'tables' } })
  }
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

    for (const row of parsed) {
      try {
        await knowledgeApi.value.createDirectQuestion({
          title: row.title,
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
  if (!directoriesComposable.value) {
    createDirectoryModalRef.value?.setSubmitting(false)
    return
  }
  try {
    await directoriesComposable.value.createDirectory({
      ...data,
      create_tool: knowledgeSubTab.value === 'directories'
    })
    // Список уже обновлён в createDirectory (push); повторный GET не обязателен и при 500
    // на списке раньше оставлял модалку в странном состоянии вместе с ошибкой.
    showCreateDirectoryModal.value = false
    toastSuccess(knowledgeSubTab.value === 'tables' ? 'Таблица создана' : 'Справочник создан')
  } catch (err: any) {
    const message = err.message || (knowledgeSubTab.value === 'tables' ? 'Не удалось создать таблицу' : 'Не удалось создать справочник')
    createDirectoryModalRef.value?.setError(message)
    toastError(message)
  } finally {
    createDirectoryModalRef.value?.setSubmitting(false)
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

const handleDeleteDirectoryFromList = async (dir: Directory) => {
  if (!directoriesComposable.value) return
  const countLabel = dir.items_count === 1 ? '1 запись' : `${dir.items_count} записей`
  if (
    !confirm(
      `Удалить справочник «${dir.name}» и все ${countLabel}? Действие нельзя отменить.`
    )
  ) {
    return
  }
  const wasSelected = selectedDirectory.value?.id === dir.id
  const hadSettingsForDir =
    showDirectorySettingsSheet.value && selectedDirectory.value?.id === dir.id
  const queryDirId = route.query.directoryId
  const hadDirectoryInQuery =
    queryDirId === dir.id || (Array.isArray(queryDirId) && queryDirId[0] === dir.id)

  try {
    await directoriesComposable.value.deleteDirectory(dir.id)
    if (wasSelected) {
      handleBackToList()
    } else if (hadDirectoryInQuery) {
      const { directoryId: _d, ...rest } = route.query
      router.replace({ query: rest })
    }
    if (hadSettingsForDir) {
      showDirectorySettingsSheet.value = false
    }
    toastSuccess('Справочник удалён')
  } catch (err: any) {
    toastError(err.message || 'Не удалось удалить справочник')
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

const applyKnowledgeDashboard = () => {
  knowledgeSubTab.value = 'dashboard'
  selectedTableId.value = null
  if (directoriesComposable.value?.currentDirectory) {
    directoriesComposable.value.setCurrentDirectory(null)
  }
  const { directoryId: _d, tableId: _t, knowledgeTab: _k, ...rest } = route.query
  router.replace({ query: rest })
}

const applyKnowledgeTab = (tab: KnowledgeBreadcrumbTab) => {
  if (tab === 'dashboard') {
    applyKnowledgeDashboard()
    return
  }
  knowledgeSubTab.value = tab
  if (tab === 'tables') {
    if (selectedTableId.value) handleBackFromTable()
    return
  }
  if (tab === 'directories') {
    if (selectedTableId.value) {
      selectedTableId.value = null
      const { tableId: _tid, ...rest } = route.query
      router.replace({ query: rest })
    }
    if (selectedDirectory.value) handleBackToList()
    return
  }
  if (selectedTableId.value) handleBackFromTable()
  if (selectedDirectory.value && directoriesComposable.value) {
    directoriesComposable.value.setCurrentDirectory(null)
    const { directoryId: _did, ...rest } = route.query
    router.replace({ query: rest })
  }
}

const buildKnowledgeBreadcrumbs = (): LayoutBreadcrumbSegment[] | null => {
  const id = agent.value?.id
  const agentLabel = agent.value?.name?.trim() || 'Агент'
  if (!id) return null

  const agentSegment: LayoutBreadcrumbSegment = {
    label: agentLabel,
    action: { type: 'route', path: `/agents/${id}/prompt` },
  }

  if (knowledgeSubTab.value === 'dashboard') {
    return [agentSegment, { label: 'База знаний', action: null }]
  }

  const tabLabel =
    knowledgeSubTabs.value.find((t) => t.id === knowledgeSubTab.value)?.label ?? 'Раздел'

  const prefix: LayoutBreadcrumbSegment[] = [
    agentSegment,
    { label: 'База знаний', action: { type: 'knowledge-dashboard' } },
  ]

  if (knowledgeSubTab.value === 'tables' && selectedTableId.value) {
    const t = tables.value.find((x) => x.id === selectedTableId.value)
    return [
      ...prefix,
      { label: 'Таблицы', action: { type: 'knowledge-tab', tab: 'tables' } },
      { label: t?.name ?? 'Таблица', action: null },
    ]
  }

  if (knowledgeSubTab.value === 'directories' && selectedDirectory.value) {
    return [
      ...prefix,
      { label: 'Справочники', action: { type: 'knowledge-tab', tab: 'directories' } },
      { label: selectedDirectory.value.name, action: null },
    ]
  }

  return [...prefix, { label: tabLabel, action: null }]
}

watch(
  [
    () => agent.value?.id,
    () => agent.value?.name,
    () => knowledgeSubTab.value,
    () => selectedTableId.value,
    () => selectedDirectory.value?.id,
    () => selectedDirectory.value?.name,
    () => tables.value,
    () => knowledgeSubTabs.value,
  ],
  () => {
    layoutBreadcrumbSegments.value = buildKnowledgeBreadcrumbs()
  },
  { immediate: true }
)

watch(pendingBreadcrumbAction, (action) => {
  if (!action) return
  if (action.type === 'knowledge-dashboard') applyKnowledgeDashboard()
  else if (action.type === 'knowledge-tab') applyKnowledgeTab(action.tab)
  pendingBreadcrumbAction.value = null
})

onUnmounted(() => {
  layoutBreadcrumbSegments.value = null
  pendingBreadcrumbAction.value = null
})

const handleCreateItem = async (data: Record<string, any>) => {
  if (!directoriesComposable.value || !selectedDirectory.value) {
    throw new Error('Нет выбранного справочника')
  }
  try {
    await directoriesComposable.value.createItem(selectedDirectory.value.id, data)
    toastSuccess('Запись добавлена')
  } catch (err: any) {
    toastError(err.message || 'Не удалось создать запись')
    throw err
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
  if (selectedDirectory.value.template === 'qa') {
    toastError('Для шаблона Вопрос/Ответ нельзя изменять колонки')
    return
  }
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
  if (selectedDirectory.value.template === 'qa') {
    toastError('Для шаблона Вопрос/Ответ нельзя изменять колонки')
    return
  }
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
  if (selectedDirectory.value.template === 'qa') {
    toastError('Для шаблона Вопрос/Ответ нельзя изменять колонки')
    return
  }
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
  if (!directoriesComposable.value) {
    directorySettingsSheetRef.value?.setDeleting(false)
    return
  }
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
