<template>
  <div class="space-y-6">
    <div
      v-if="!currentFolderId"
      class="rounded-3xl border border-slate-200 bg-white p-4 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]"
    >
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
      <div
        class="relative z-10 mb-5 flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 bg-white pb-4"
      >
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
            class="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-700 transition-colors hover:bg-slate-50"
            aria-label="Переименовать папку"
            title="Переименовать папку"
            @click="handleRenameCurrentFolder"
          >
            <Pencil class="h-3.5 w-3.5" />
          </button>
          <button
            v-if="currentFolderId"
            type="button"
            class="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-rose-200 bg-rose-50 text-rose-700 transition-colors hover:bg-rose-100"
            aria-label="Удалить папку"
            title="Удалить папку"
            @click="handleDeleteCurrentFolder"
          >
            <Trash2 class="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <KnowledgeItemsList
        :items="currentItems"
        :list-scope-key="currentFolderId ?? 'root'"
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
      >
        <template #below-toolbar>
          <div
            v-if="currentFolderId"
            class="relative z-10 rounded-2xl border border-slate-100 bg-white p-4"
          >
            <div class="mb-3 min-w-0">
              <p class="text-[10px] font-bold uppercase tracking-widest text-slate-500">Настройки чанкинга</p>
              <p class="mt-1 text-xs text-slate-500">
                Размер чанка и перекрытие (в символах) для индексации файлов в этой папке и подпапках.
                После сохранения запускается переиндексирование (до 200 файлов за раз).
              </p>
            </div>

            <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div>
                <label class="text-xs font-semibold text-slate-700">Размер чанка, символов</label>
                <input
                  v-model.number="chunkSizeChars"
                  type="number"
                  min="500"
                  max="50000"
                  step="100"
                  class="mt-2 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm outline-none transition-all duration-300 focus:border-indigo-400 focus:bg-white focus:ring-4 focus:ring-indigo-500/10"
                />
              </div>
              <div>
                <label class="text-xs font-semibold text-slate-700">Перекрытие, символов</label>
                <input
                  v-model.number="chunkOverlapChars"
                  type="number"
                  min="0"
                  step="50"
                  class="mt-2 w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm outline-none transition-all duration-300 focus:border-indigo-400 focus:bg-white focus:ring-4 focus:ring-indigo-500/10"
                />
              </div>
            </div>

            <div class="mt-4 flex items-center justify-end gap-2">
              <button
                type="button"
                class="inline-flex h-9 items-center rounded-xl border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 transition-colors hover:bg-slate-50"
                @click="handleResetChunking"
              >
                Сбросить
              </button>
              <button
                type="button"
                class="inline-flex h-9 items-center rounded-xl bg-indigo-600 px-3 text-xs font-semibold text-white transition-colors hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="isSavingChunking"
                @click="handleSaveChunking"
              >
                {{ isSavingChunking ? 'Сохранение...' : 'Сохранить' }}
              </button>
            </div>
          </div>
        </template>
      </KnowledgeItemsList>
    </div>

    <KnowledgeFileEditor
      :open="showFileEditor"
      :file="selectedFile"
      :saving="isSavingFile"
      :document-upload-enabled="!!currentFolderId"
      @close="showFileEditor = false"
      @save="handleSaveFile"
      @reindex="handleReindexFile"
      @upload-documents="handleUploadDocumentsFromEditor"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { ChevronRight, Pencil, Trash2 } from 'lucide-vue-next'
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
  reindexFile,
  updateFolderChunkingSettings,
  uploadDocumentsBatch
} = useKnowledgeFiles(props.agentId)

const showFileEditor = ref(false)
const selectedFile = ref<KnowledgeFileItem | null>(null)
const isSavingFile = ref(false)

const DEFAULT_CHUNK_SIZE_CHARS = 6000
const DEFAULT_CHUNK_OVERLAP_CHARS = 1000
const MAX_CHUNK_SIZE_CHARS = 50_000
const isSavingChunking = ref(false)
const chunkSizeChars = ref(DEFAULT_CHUNK_SIZE_CHARS)
const chunkOverlapChars = ref(DEFAULT_CHUNK_OVERLAP_CHARS)

const currentFolder = computed(() => {
  if (!currentFolderId.value) return null
  return folders.value.find((f) => f.id === currentFolderId.value) ?? null
})

watch(
  () => currentFolderId.value,
  () => {
    if (!currentFolder.value) {
      chunkSizeChars.value = DEFAULT_CHUNK_SIZE_CHARS
      chunkOverlapChars.value = DEFAULT_CHUNK_OVERLAP_CHARS
      return
    }

    chunkSizeChars.value = currentFolder.value.chunk_size_chars ?? DEFAULT_CHUNK_SIZE_CHARS
    chunkOverlapChars.value = currentFolder.value.chunk_overlap_chars ?? DEFAULT_CHUNK_OVERLAP_CHARS
  },
  { immediate: true }
)

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

const handleUploadDocumentsFromEditor = async (files: File[]) => {
  const list = Array.from(files ?? []).filter(Boolean)
  if (!list.length) return
  if (!currentFolderId.value) {
    toastError('Откройте папку в дереве базы знаний, затем загрузите документы')
    return
  }
  isSavingFile.value = true
  try {
    const results = await uploadDocumentsBatch(list, 3)
    const okRows = results.filter((r) => r.ok && r.id)
    const failed = results.filter((r) => !r.ok)

    if (okRows.length) await Promise.all(okRows.map((r) => reindexFile(r.id!)))

    if (failed.length === 0) {
      const n = okRows.length
      const m10 = n % 10
      const m100 = n % 100
      const label =
        m100 >= 11 && m100 <= 14 ? 'файлов' : m10 === 1 ? 'файл' : m10 >= 2 && m10 <= 4 ? 'файла' : 'файлов'
      toastSuccess(`Загружено ${n} ${label}. Запущена индексация`)
      showFileEditor.value = false
      return
    }

    const ok = okRows.length
    const names = failed.map((f) => f.fileName).slice(0, 5).join(', ')
    const more = failed.length > 5 ? ` и ещё ${failed.length - 5}` : ''
    toastError(
      `Загружено ${ok} из ${list.length}. Ошибки: ${names}${more}`,
      failed[0]?.error
    )
    if (ok > 0) {
      showFileEditor.value = false
    }
  } catch (error: any) {
    toastError(error?.message || 'Не удалось выполнить загрузку')
  } finally {
    isSavingFile.value = false
  }
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

const handleResetChunking = () => {
  if (!currentFolder.value) return
  chunkSizeChars.value = currentFolder.value.chunk_size_chars ?? DEFAULT_CHUNK_SIZE_CHARS
  chunkOverlapChars.value = currentFolder.value.chunk_overlap_chars ?? DEFAULT_CHUNK_OVERLAP_CHARS
}

const handleSaveChunking = async () => {
  if (!currentFolderId.value) return
  const size = Number(chunkSizeChars.value)
  const overlap = Number(chunkOverlapChars.value)
  if (!Number.isFinite(size) || size < 500 || size > MAX_CHUNK_SIZE_CHARS) {
    toastError(`Размер чанка: от 500 до ${MAX_CHUNK_SIZE_CHARS} символов`)
    return
  }
  if (!Number.isFinite(overlap) || overlap < 0) {
    toastError('Перекрытие не может быть отрицательным')
    return
  }
  if (overlap >= size) {
    toastError('Перекрытие должно быть меньше размера чанка')
    return
  }
  isSavingChunking.value = true
  try {
    await updateFolderChunkingSettings(currentFolderId.value, {
      chunk_size_chars: size,
      chunk_overlap_chars: overlap
    })
    toastSuccess('Настройки сохранены. Запущено переиндексирование файлов в папке.')
  } catch (e: any) {
    toastError(e?.message || 'Не удалось сохранить настройки чанкинга')
  } finally {
    isSavingChunking.value = false
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
