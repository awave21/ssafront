<template>
  <div class="space-y-6">
    <KnowledgeSubTabs
      v-model="knowledgeSubTab"
      :tabs="knowledgeSubTabs"
    />

    <div v-if="knowledgeSubTab === 'directories'">
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
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
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

const store = useAgentEditorStore()
const route = useRoute()
const router = useRouter()
const { agent, directoriesComposable, isSqnsEnabled, sqnsToolsList, sqnsStatus } = storeToRefs(store)
const { success: toastSuccess, error: toastError } = useToast()

const knowledgeSubTab = ref<'sqns' | 'directories'>('directories')
const showCreateDirectoryModal = ref(false)
const showImportCsvModal = ref(false)
const showDirectorySettingsSheet = ref(false)
const directorySettingsSheetRef = ref<InstanceType<typeof DirectorySettingsSheet> | null>(null)

const directories = computed(() => directoriesComposable.value?.directories ?? [])
const directoriesLoading = computed(() => directoriesComposable.value?.isLoading ?? false)
const directoriesError = computed(() => directoriesComposable.value?.error ?? null)
const directoryItems = computed(() => directoriesComposable.value?.items ?? [])
const directoryItemsLoading = computed(() => directoriesComposable.value?.isLoadingItems ?? false)
const selectedDirectory = computed(() => directoriesComposable.value?.currentDirectory ?? null)

const knowledgeSubTabs = computed(() => [
  { id: 'directories', label: 'Справочники', count: directories.value.length },
  { id: 'sqns', label: 'SQNS', count: isSqnsEnabled.value ? sqnsToolsList.value.length : undefined }
])

const isValidKnowledgeSubTab = (value: string): value is 'sqns' | 'directories' =>
  value === 'sqns' || value === 'directories'

const getKnowledgeTabStorageKey = () => `agent-knowledge-subtab:${agent.value?.id ?? 'unknown'}`

const syncKnowledgeTabToQuery = (tab: 'sqns' | 'directories') => {
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
    }
  }
}

const loadDirectories = async () => {
  await store.ensureDirectoriesLoaded()
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
  } else {
    store.ensureSqnsStatusLoaded()
    store.ensureSqnsHints()
  }
})

watch(agent, async (value) => {
  if (!value) return
  if (knowledgeSubTab.value === 'directories') {
    await store.ensureDirectoriesLoaded()
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
