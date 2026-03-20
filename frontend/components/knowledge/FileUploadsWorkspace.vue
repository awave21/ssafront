<template>
  <div class="space-y-6">
    <div class="rounded-3xl border border-slate-200 bg-white p-4 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
      <div class="flex flex-col gap-1.5">
        <label class="text-[10px] font-bold uppercase tracking-widest text-slate-500">
          Описание инструмента База знаний
        </label>
        <textarea
          v-model="form.knowledge_tool_description"
          :disabled="!canEditAgents"
          @blur="handleKnowledgeDescriptionBlur"
          rows="3"
          class="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-800 resize-y focus:outline-none focus:ring-2 focus:ring-indigo-200 placeholder:text-slate-400"
          placeholder="Например: ищи в загруженных knowledge files, когда вопрос про факты, услуги, цены, регламенты."
        />
        <p class="text-[11px] text-slate-500">
          Это описание используется для runtime-инструмента <span class="font-mono">search_knowledge_files</span> и отображается в разделе "Системный промпт".
        </p>
      </div>
    </div>

    <div class="rounded-3xl border border-slate-100 bg-white p-6 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
      <div class="mb-5 flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 pb-4">
        <div class="flex min-w-0 flex-wrap items-center gap-2">
          <template v-for="(crumb, index) in breadcrumbs" :key="crumb.id ?? 'root'">
            <ChevronRight v-if="index > 0" class="h-3.5 w-3.5 text-slate-300" />
            <button
              type="button"
              class="truncate rounded-full px-2.5 py-1 text-xs font-bold transition-all"
              :class="index === breadcrumbs.length - 1 ? 'bg-indigo-50 text-indigo-700' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-700'"
              @click="openFolder(crumb.id)"
            >
              {{ crumb.title }}
            </button>
          </template>
        </div>

        <div class="flex items-center gap-2">
          <button
            v-if="currentFolderId"
            type="button"
            class="inline-flex h-9 items-center gap-1 rounded-xl border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 transition-colors hover:bg-slate-50"
            @click="handleGoBack"
          >
            <ArrowLeft class="h-3.5 w-3.5" />
            Назад
          </button>
          <button
            v-if="currentFolderId"
            type="button"
            class="inline-flex h-9 items-center gap-1 rounded-xl border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 transition-colors hover:bg-slate-50"
            @click="handleRenameCurrentFolder"
          >
            <Pencil class="h-3.5 w-3.5" />
            Переименовать папку
          </button>
          <button
            v-if="currentFolderId"
            type="button"
            class="inline-flex h-9 items-center gap-1 rounded-xl border border-rose-200 bg-rose-50 px-3 text-xs font-semibold text-rose-700 transition-colors hover:bg-rose-100"
            @click="handleDeleteCurrentFolder"
          >
            <Trash2 class="h-3.5 w-3.5" />
            Удалить папку
          </button>
        </div>
      </div>

      <KnowledgeItemsList
        :items="currentItems"
        :folder-children-count="folderChildrenCount"
        :index-progress-by-item="indexProgressByItem"
        :index-state-by-item="indexStateByItem"
        :loading="isLoading"
        @create-folder="handleCreateFolder"
        @create-file="openCreateFile"
        @open-folder="openFolder"
        @open-file="handleOpenFile"
        @delete="handleDeleteItem"
        @move-click="handleMoveClick"
        @move-drop="handleDropMove"
      />
    </div>

    <KnowledgeFileEditor
      :open="showFileEditor"
      :file="selectedFile"
      :saving="isSavingFile"
      @close="showFileEditor = false"
      @save="handleSaveFile"
      @reindex="handleReindexFile"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { ArrowLeft, ChevronRight, Pencil, Trash2 } from 'lucide-vue-next'
import { usePermissions } from '~/composables/usePermissions'
import { useAgentEditorStore } from '~/composables/useAgentEditorStore'
import { useToast } from '~/composables/useToast'
import { useKnowledgeFiles } from '~/composables/useKnowledgeFiles'
import { knowledgeItemType, type CreateKnowledgeTextPayload, type KnowledgeFileItem } from '~/types/knowledge'
import KnowledgeItemsList from './KnowledgeItemsList.vue'
import KnowledgeFileEditor from './KnowledgeFileEditor.vue'

const props = defineProps<{
  agentId: string
}>()

const store = useAgentEditorStore()
const { form, agent } = storeToRefs(store)
const { canEditAgents } = usePermissions()
const { success: toastSuccess, error: toastError } = useToast()

const {
  currentFolderId,
  currentItems,
  folderChildrenCount,
  indexProgressByItem,
  indexStateByItem,
  breadcrumbs,
  folders,
  isLoading,
  fetchItems,
  openFolder,
  createFolder,
  createFile,
  updateFile,
  renameFolder,
  moveItem,
  deleteItem,
  getMoveTargets,
  reindexFile
} = useKnowledgeFiles(props.agentId)

const showFileEditor = ref(false)
const selectedFile = ref<KnowledgeFileItem | null>(null)
const isSavingFile = ref(false)

const buildDefaultFolderTitle = () => {
  const existingTitles = new Set(
    currentItems.value
      .filter((item) => item.type === knowledgeItemType.folder)
      .map((item) => item.title.trim().toLowerCase())
  )
  if (!existingTitles.has('новая папка')) return 'Новая папка'

  let index = 2
  while (existingTitles.has(`новая папка ${index}`)) {
    index += 1
  }
  return `Новая папка ${index}`
}

const handleCreateFolder = async () => {
  const title = buildDefaultFolderTitle()
  try {
    await createFolder({ title, parent_id: currentFolderId.value })
    toastSuccess('Папка создана')
  } catch (error: any) {
    toastError(error?.message || 'Не удалось создать папку')
  }
}

const handleRenameCurrentFolder = async () => {
  if (!currentFolderId.value) return
  const current = folders.value.find((item) => item.id === currentFolderId.value)
  if (!current) return
  const title = window.prompt('Новое название папки', current.title)
  if (!title?.trim()) return
  await renameFolder(currentFolderId.value, title)
  toastSuccess('Папка переименована')
}

const handleDeleteCurrentFolder = async () => {
  if (!currentFolderId.value) return
  const ok = window.confirm('Удалить текущую папку вместе с вложенным содержимым?')
  if (!ok) return
  const folderId = currentFolderId.value
  const parentId = folders.value.find((item) => item.id === folderId)?.parent_id ?? null
  await deleteItem(folderId)
  openFolder(parentId)
  toastSuccess('Папка удалена')
}

const handleGoBack = () => {
  if (!currentFolderId.value) return
  const current = folders.value.find((item) => item.id === currentFolderId.value)
  openFolder(current?.parent_id ?? null)
}

const openCreateFile = () => {
  selectedFile.value = null
  showFileEditor.value = true
}

const handleOpenFile = (id: string) => {
  const item = currentItems.value.find((entry) => entry.id === id)
  if (!item || item.type !== knowledgeItemType.file) return
  selectedFile.value = item
  showFileEditor.value = true
}

const handleDeleteItem = async (id: string) => {
  const item = currentItems.value.find((entry) => entry.id === id) ?? folders.value.find((entry) => entry.id === id)
  if (!item) return
  const ok = window.confirm(item.type === knowledgeItemType.folder ? 'Удалить папку вместе с содержимым?' : 'Удалить файл?')
  if (!ok) return
  await deleteItem(id)
  toastSuccess(item.type === knowledgeItemType.folder ? 'Папка удалена' : 'Файл удален')
}

const handleSaveFile = async (payload: CreateKnowledgeTextPayload) => {
  isSavingFile.value = true
  try {
    const nextPayload: CreateKnowledgeTextPayload = {
      ...payload,
      parent_id: currentFolderId.value
    }
    let savedFile: KnowledgeFileItem | null = null
    if (selectedFile.value) {
      savedFile = await updateFile(selectedFile.value.id, nextPayload)
    } else {
      savedFile = await createFile(nextPayload)
    }

    if (!savedFile) {
      throw new Error('Не удалось определить сохраненный файл')
    }

    showFileEditor.value = false
    toastSuccess('Файл сохранен. Запущена индексация')

    void (async () => {
      try {
        await reindexFile(savedFile.id)
      } catch (error: any) {
        toastError(error?.message || 'Ошибка индексации файла')
      }
    })()
  } catch (error: any) {
    toastError(error?.message || 'Не удалось сохранить файл и отправить в векторное хранилище')
  } finally {
    isSavingFile.value = false
  }
}

const handleKnowledgeDescriptionBlur = () => {
  if (!canEditAgents.value || !agent.value) return
  const current = String(form.value.knowledge_tool_description ?? '').trim()
  const saved = String(agent.value.knowledge_tool_description ?? '').trim()
  if (current === saved) return
  store.autoSaveField({ knowledge_tool_description: form.value.knowledge_tool_description })
}

onMounted(async () => {
  await fetchItems()
})

const handleDropMove = async (itemId: string, targetFolderId: string) => {
  await moveItem(itemId, targetFolderId)
  toastSuccess('Элемент перемещен')
}

const handleMoveClick = async (itemId: string) => {
  const targets = getMoveTargets(itemId)
  if (!targets.length) {
    toastError('Нет доступных папок для перемещения')
    return
  }
  const options = targets.map((target, index) => `${index + 1}. ${target.title}`).join('\n')
  const value = window.prompt(`Куда переместить?\n${options}\n\nВведите номер:`)
  const index = Number(value) - 1
  if (!Number.isInteger(index) || index < 0 || index >= targets.length) return
  await moveItem(itemId, targets[index].id)
  toastSuccess('Элемент перемещен')
}

const handleReindexFile = async () => {
  if (!selectedFile.value) return
  try {
    await reindexFile(selectedFile.value.id)
    const updated = currentItems.value.find((item) => item.id === selectedFile.value?.id) ?? null
    if (updated) selectedFile.value = updated
    toastSuccess('Индексация запущена')
  } catch (error: any) {
    toastError(error?.message || 'Не удалось запустить индексацию')
  }
}
</script>
