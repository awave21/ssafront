<template>
  <div class="space-y-4">
    <!-- Header -->
    <div class="flex items-center justify-between gap-4">
      <div class="flex items-center gap-3 min-w-0">
        <button
          @click="$emit('back')"
          class="flex items-center gap-2 px-3 py-2 text-slate-600 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors text-sm font-medium"
        >
          <ArrowLeft class="w-4 h-4" />
          <span>Все справочники</span>
        </button>
        <div class="w-px h-6 bg-slate-200"></div>
        <div class="min-w-0">
          <h3 class="text-lg font-bold text-slate-900 truncate">{{ directory.name }}</h3>
          <p class="text-xs text-slate-500">
            <span class="font-mono text-slate-400">{{ directory.tool_name }}</span>
            <span class="mx-1.5">•</span>
            <span>{{ directory.items_count }} {{ itemsLabel }}</span>
          </p>
        </div>
      </div>
      <button
        @click="$emit('settings')"
        class="flex items-center gap-2 px-3 py-2 text-slate-600 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors text-sm font-medium"
      >
        <Pencil class="w-4 h-4" />
        <span>Редактировать</span>
      </button>
    </div>

    <!-- Actions Bar -->
    <DirectoryDetailToolbar
      :add-disabled="false"
      :has-items="items.length > 0"
      :selected-count="Object.keys(rowSelection).length"
      :search-query="globalFilter"
      @add-row="openAddRowSheet"
      @import="$emit('import')"
      @export="$emit('export')"
      @delete-selected="$emit('deleteSelected', selectedRowIds)"
      @update:search-query="globalFilter = $event"
    />

    <!-- Hint bar: shortcuts + undo/redo + hidden columns -->
    <div v-if="items.length > 0" class="flex items-center justify-between gap-4 flex-wrap">
      <p class="text-xs text-slate-400 flex items-center gap-1.5">
        <span class="inline-flex items-center gap-1 px-1.5 py-0.5 bg-slate-100 rounded text-slate-500">
          <MousePointer class="w-3 h-3" />
          Клик
        </span>
        редактирование
        <span class="mx-0.5">•</span>
        <span class="px-1.5 py-0.5 bg-slate-100 rounded text-slate-500 font-mono text-[10px]">Tab</span>
        далее
        <span class="mx-0.5">•</span>
        <span class="px-1.5 py-0.5 bg-slate-100 rounded text-slate-500 font-mono text-[10px]">Enter</span>
        сохранить
        <span class="mx-0.5">•</span>
        <span class="px-1.5 py-0.5 bg-slate-100 rounded text-slate-500 font-mono text-[10px]">Esc</span>
        отмена
        <span class="mx-0.5">•</span>
        <span class="px-1.5 py-0.5 bg-slate-100 rounded text-slate-500 font-mono text-[10px]">ПКМ</span>
        меню
      </p>
      <div class="flex items-center gap-2">
        <!-- Hidden columns badge -->
        <button
          v-if="hiddenColumnNames.size > 0"
          @click="showAllColumns"
          class="flex items-center gap-1 px-2 py-1 text-xs font-medium text-amber-700 bg-amber-50 hover:bg-amber-100 border border-amber-200 rounded-lg transition-colors"
        >
          <EyeOff class="w-3 h-3" />
          {{ hiddenColumnNames.size }} скрыто
          <X class="w-3 h-3 ml-0.5" />
        </button>
        <!-- Undo / Redo -->
        <TooltipProvider :delay-duration="300">
          <Tooltip>
            <TooltipTrigger as-child>
              <button
                @click="undo"
                :disabled="!canUndo"
                class="p-1.5 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <Undo2 class="w-3.5 h-3.5" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="bottom">
              <p class="text-xs">Отменить <kbd class="ml-1 px-1 py-0.5 bg-slate-700 rounded text-[10px]">Ctrl+Z</kbd></p>
            </TooltipContent>
          </Tooltip>
          <Tooltip>
            <TooltipTrigger as-child>
              <button
                @click="redo"
                :disabled="!canRedo"
                class="p-1.5 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
              >
                <Redo2 class="w-3.5 h-3.5" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="bottom">
              <p class="text-xs">Повторить <kbd class="ml-1 px-1 py-0.5 bg-slate-700 rounded text-[10px]">Ctrl+Shift+Z</kbd></p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex justify-center py-12">
      <Loader2 class="w-8 h-8 animate-spin text-indigo-600" />
    </div>

    <!-- Empty State: show table headers + empty body -->
    <div v-else-if="items.length === 0 && !globalFilter" class="shadow-sm">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead class="w-12"></TableHead>
            <TableHead
              v-for="col in orderedColumns"
              :key="col.name"
              :style="{ minWidth: getColumnWidth(col) }"
            >
              <span class="text-xs font-semibold text-slate-500 uppercase tracking-wide">{{ col.label }}</span>
            </TableHead>
            <TableHead class-name="w-16"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell :class-name="`text-center py-12`" :colspan="orderedColumns.length + 2">
              <div class="flex flex-col items-center">
                <div class="w-12 h-12 bg-slate-100 rounded-full flex items-center justify-center mb-3">
                  <FileText class="h-6 w-6 text-slate-400" />
                </div>
                <p class="text-sm font-medium text-slate-900">Записей пока нет</p>
                <p class="text-xs text-slate-500 mt-1 mb-4">Добавьте первую запись</p>
                <button
                  @click="openAddRowSheet"
                  class="px-4 py-2 bg-indigo-600 text-white rounded-md text-sm font-bold hover:bg-indigo-700 transition-colors"
                >
                  Добавить запись
                </button>
              </div>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>

    <!-- No Results -->
    <div 
      v-else-if="table.getRowModel().rows.length === 0 && globalFilter" 
      class="bg-background rounded-md border border-border p-8 text-center"
    >
      <p class="text-slate-500">Ничего не найдено по запросу "{{ globalFilter }}"</p>
    </div>

    <!-- Table with TanStack -->
    <div v-else-if="table.getRowModel().rows.length > 0" class="shadow-sm">
        <Table :style="{ width: `${table.getTotalSize() + 56}px`, minWidth: '100%' }">
          <TableHeader>
            <TableRow>
              <TableHead class-name="w-14 !px-0">
                <div class="flex items-center justify-center gap-1 h-full">
                  <!-- Невидимый spacer под размер кнопки "развернуть" в строках -->
                  <span class="w-[26px] shrink-0"></span>
                  <input
                    type="checkbox"
                    :checked="table.getIsAllPageRowsSelected()"
                    :indeterminate="table.getIsSomePageRowsSelected()"
                    @change="table.toggleAllPageRowsSelected()"
                    class="w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                  />
                </div>
              </TableHead>
              <TableHead
                v-for="header in table.getHeaderGroups()[0].headers.filter(h => h.id !== 'select' && h.id !== 'actions')" 
                :key="header.id"
                @dragover.prevent="handleDragOver($event, header.index - 1)"
                @dragenter.prevent="dragOverIndex = header.index - 1"
                @dragleave="handleDragLeave"
                @drop="handleDrop($event, header.index - 1)"
                @dragend="handleDragEnd"
                :class-name="`relative select-none ${dragOverIndex === header.index - 1 && dragIndex !== header.index - 1 ? 'bg-indigo-100' : ''} ${dragIndex === header.index - 1 ? 'opacity-50' : ''}`"
                :style="{ width: `${header.getSize()}px` }"
              >
                <ColumnHeaderDropdown
                  :column="header.column.columnDef.meta as any"
                  :is-only-column="columns.length <= 1"
                  @dragstart="handleDragStart($event, header.index - 1)"
                  @edit="openColumnSettings(header.column.columnDef.meta as any)"
                  @hide="hideColumn(header.column.columnDef.meta as any)"
                  @delete="deleteColumn(header.column.columnDef.meta as any)"
                />
                <!-- Resize Handle -->
                <div
                  @mousedown="header.getResizeHandler()?.($event)"
                  @touchstart="header.getResizeHandler()?.($event)"
                  @dblclick="resetColumnSize(header)"
                  class="absolute right-0 top-0 h-full w-1 cursor-col-resize select-none touch-none group/resize"
                  :class="header.column.getIsResizing() ? 'bg-indigo-400' : 'hover:bg-indigo-300'"
                />
              </TableHead>
              <!-- Add Column Button → opens settings sheet -->
              <TableHead class-name="w-40">
                <div class="flex justify-center">
                  <button
                    @click="$emit('settings')"
                    class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
                    title="Добавить столбец"
                  >
                    <Plus class="w-3.5 h-3.5" />
                    Столбец
                  </button>
                </div>
              </TableHead>
              <TableHead class-name="w-16"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <!-- Data Rows -->
            <RowContextMenu
              v-for="row in table.getRowModel().rows"
              :key="row.id"
              @edit="openEditRowSheet(row.original)"
              @duplicate="duplicateRow(row.original)"
              @delete="$emit('delete', row.original.id)"
            >
              <TableRow 
                class="group cursor-pointer"
                :class="{ 'bg-indigo-50/30': editingCell?.itemId === row.original.id }"
                @click="openEditRowSheet(row.original)"
              >
                <TableCell class-name="w-14 !px-0">
                  <div class="flex items-center justify-center gap-1 h-full">
                    <button
                      @click.stop="openEditRowSheet(row.original)"
                      class="p-1 text-slate-300 hover:text-indigo-600 hover:bg-indigo-50 rounded transition-colors opacity-0 group-hover:opacity-100"
                      title="Развернуть"
                    >
                      <Maximize2 class="w-3.5 h-3.5" />
                    </button>
                    <input
                      type="checkbox"
                      :checked="row.getIsSelected()"
                      @change="row.toggleSelected()"
                      @click.stop
                      class="w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                    />
                  </div>
                </TableCell>
                <TableCell 
                  v-for="col in orderedColumns" 
                  :key="col.name"
                  class-name="px-1 py-1"
                  :style="{ width: `${getColSize(col.name)}px` }"
                >
                  <EditableCell
                    :column="col"
                    :display-value="row.original.data[col.name]"
                    :model-value="editingCell?.itemId === row.original.id && editingCell?.colName === col.name ? editValue : row.original.data[col.name]"
                    :editing="isEditing(row.original.id, col.name)"
                    :saving="isSaving && isEditing(row.original.id, col.name)"
                    @update:model-value="editValue = $event"
                    @start-edit="startEdit(row.original, col)"
                    @blur="handleBlur"
                    @keydown="(e) => handleKeydown(e, row.original, col, row.index, orderedColumns.indexOf(col))"
                    @save="saveEdit(true)"
                  />
                </TableCell>
                <!-- Empty cell for add column -->
                <TableCell class-name="px-2 py-2 w-40"></TableCell>
                <TableCell class-name="px-4 py-2 w-16">
                  <div class="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      @click.stop="$emit('delete', row.original.id)"
                      class="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                      title="Удалить"
                    >
                      <Trash2 class="w-4 h-4" />
                    </button>
                  </div>
                </TableCell>
              </TableRow>
            </RowContextMenu>
          </TableBody>
        </Table>

      <!-- Pagination -->
      <div v-if="table.getPageCount() > 1" class="flex items-center justify-between px-4 py-3 border-t border-slate-100 bg-slate-50">
        <p class="text-sm text-slate-500">
          Показано {{ table.getState().pagination.pageIndex * table.getState().pagination.pageSize + 1 }}-{{ Math.min((table.getState().pagination.pageIndex + 1) * table.getState().pagination.pageSize, table.getFilteredRowModel().rows.length) }} из {{ table.getFilteredRowModel().rows.length }}
        </p>
        <div class="flex items-center gap-1">
          <button
            :disabled="!table.getCanPreviousPage()"
            @click="table.previousPage()"
            class="p-2 text-slate-400 hover:text-slate-600 hover:bg-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <ChevronLeft class="w-4 h-4" />
          </button>
          <button
            v-for="page in visiblePages"
            :key="page"
            @click="table.setPageIndex(page - 1)"
            class="min-w-[32px] h-8 px-2 text-sm font-medium rounded-lg transition-colors"
            :class="[
              table.getState().pagination.pageIndex === page - 1
                ? 'bg-indigo-600 text-white' 
                : 'text-slate-600 hover:bg-white'
            ]"
          >
            {{ page }}
          </button>
          <button
            :disabled="!table.getCanNextPage()"
            @click="table.nextPage()"
            class="p-2 text-slate-400 hover:text-slate-600 hover:bg-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <ChevronRight class="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>

    <!-- Add Row Side Panel -->
    <AddRowSheet
      :open="isAddRowSheetOpen"
      :columns="orderedColumns"
      :saving="isSavingNewRow"
      @update:open="isAddRowSheetOpen = $event"
      @save="handleSheetSave"
    />

    <!-- Edit Row Side Panel -->
    <EditRowSheet
      :open="isEditRowSheetOpen"
      :columns="orderedColumns"
      :item="editRowSheetItem"
      :saving="isSavingEditRow"
      @update:open="isEditRowSheetOpen = $event"
      @save="handleEditRowSave"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import {
  useVueTable,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  type ColumnDef,
} from '@tanstack/vue-table'
import {
  ArrowLeft,
  Pencil,
  Loader2,
  FileText,
  ChevronLeft,
  ChevronRight,
  MousePointer,
  Trash2,
  Undo2,
  Redo2,
  EyeOff,
  X,
  Maximize2,
  Plus,
} from 'lucide-vue-next'
import type { Directory, DirectoryItem, DirectoryColumn } from '~/types/directories'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '~/components/ui/table'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '~/components/ui/tooltip'
import { pluralize } from '~/utils/pluralize'
import { getColumnWidth as getColWidth, isLongTextField } from '~/utils/directory-helpers'

import DirectoryDetailToolbar from './DirectoryDetailToolbar.vue'
import EditableCell from './EditableCell.vue'
import ColumnHeaderDropdown from './ColumnHeaderDropdown.vue'
import RowContextMenu from './RowContextMenu.vue'
import AddRowSheet from './AddRowSheet.vue'
import EditRowSheet from './EditRowSheet.vue'

const props = defineProps<{
  directory: Directory
  items: DirectoryItem[]
  loading?: boolean
  onUpdateItem?: (itemId: string, data: Record<string, any>) => Promise<void>
}>()

const emit = defineEmits<{
  (e: 'back'): void
  (e: 'settings'): void
  (e: 'import'): void
  (e: 'export'): void
  (e: 'update', itemId: string, data: Record<string, any>): void
  (e: 'create', data: Record<string, any>): void
  (e: 'delete', id: string): void
  (e: 'deleteSelected', ids: string[]): void
  (e: 'addColumn', column: DirectoryColumn & { searchable: boolean }): void
  (e: 'deleteColumn', columnName: string): void
  (e: 'updateColumns', columns: DirectoryColumn[]): void
}>()

// --- Inline editing state ---
const editingCell = ref<{ itemId: string; colName: string } | null>(null)
const editValue = ref<any>('')
const originalValue = ref<any>('')
const isSaving = ref(false)
const blurTimeoutId = ref<ReturnType<typeof setTimeout> | null>(null)


// --- Undo/Redo history ---
type EditHistoryEntry = {
  itemId: string
  colName: string
  oldValue: any
  newValue: any
  timestamp: number
}
const editHistory = ref<EditHistoryEntry[]>([])
const redoStack = ref<EditHistoryEntry[]>([])
const MAX_HISTORY = 50

// --- Hidden columns ---
const hiddenColumnNames = ref<Set<string>>(new Set())

// --- Add row sheet state ---
const isAddRowSheetOpen = ref(false)
const isSavingNewRow = ref(false)

// --- Edit row sheet state ---
const isEditRowSheetOpen = ref(false)
const editRowSheetItem = ref<DirectoryItem | null>(null)
const isSavingEditRow = ref(false)

// --- TanStack Table ---
const globalFilter = ref('')
const rowSelection = ref<Record<string, boolean>>({})

const columns = computed(() => props.directory.columns || [])

const visibleColumns = computed(() =>
  columns.value.filter(c => !hiddenColumnNames.value.has(c.name))
)

// Column ordering (drag & drop)
const columnOrder = ref<string[]>([])
const dragIndex = ref<number | null>(null)
const dragOverIndex = ref<number | null>(null)

watch(() => props.directory.columns, (newCols) => {
  if (newCols && newCols.length > 0) {
    const existingOrder = columnOrder.value.filter(name => newCols.some(c => c.name === name))
    const newColNames = newCols.map(c => c.name).filter(name => !existingOrder.includes(name))
    columnOrder.value = [...existingOrder, ...newColNames]
  }
}, { immediate: true })

const orderedColumns = computed(() => {
  const base = visibleColumns.value
  if (columnOrder.value.length === 0) return base
  return columnOrder.value
    .map(name => base.find(c => c.name === name))
    .filter((c): c is DirectoryColumn => c !== undefined)
})

// Column size defaults by type
const getDefaultSize = (col: DirectoryColumn): number => {
  if (col.type === 'bool') return 80
  if (col.type === 'number') return 100
  if (col.type === 'date') return 120
  if (isLongTextField(col.name)) return 200
  return 140
}

// Build TanStack column defs from ordered columns
const tanstackColumns = computed<ColumnDef<DirectoryItem, any>[]>(() => {
  return orderedColumns.value.map(col => ({
    id: col.name,
    accessorFn: (row: DirectoryItem) => row.data[col.name],
    header: col.label,
    meta: col,
    filterFn: 'includesString',
    size: getDefaultSize(col),
    minSize: 40,
    maxSize: 500,
  }))
})

const table = useVueTable({
  get data() { return props.items },
  get columns() { return tanstackColumns.value },
  state: {
    get globalFilter() { return globalFilter.value },
    get rowSelection() { return rowSelection.value },
  },
  onGlobalFilterChange: (updater) => {
    globalFilter.value = typeof updater === 'function' ? updater(globalFilter.value) : updater
  },
  onRowSelectionChange: (updater) => {
    rowSelection.value = typeof updater === 'function' ? updater(rowSelection.value) : updater
  },
  columnResizeMode: 'onChange' as const,
  getCoreRowModel: getCoreRowModel(),
  getFilteredRowModel: getFilteredRowModel(),
  getPaginationRowModel: getPaginationRowModel(),
  getRowId: (row) => row.id,
  globalFilterFn: (row, _columnId, filterValue) => {
    const query = String(filterValue).toLowerCase()
    return columns.value.some(col => {
      const value = row.original.data[col.name]
      return value && String(value).toLowerCase().includes(query)
    })
  },
  initialState: {
    pagination: {
      pageSize: 10,
    },
  },
})

const selectedRowIds = computed(() => Object.keys(rowSelection.value).filter(k => rowSelection.value[k]))

const itemsLabel = computed(() =>
  pluralize(props.directory.items_count, ['запись', 'записи', 'записей'])
)

const getColumnWidth = (col: DirectoryColumn) => getColWidth(col.type, col.name)

// Get current column size from table state (for body cells)
const getColSize = (colName: string): number => {
  return table.getColumn(colName)?.getSize() ?? 140
}

// Reset column size on double-click
const resetColumnSize = (header: any) => {
  header.column.resetSize()
}

// --- Visible pages for pagination ---
const visiblePages = computed(() => {
  const pages: number[] = []
  const total = table.getPageCount()
  const current = table.getState().pagination.pageIndex + 1
  
  if (total <= 5) {
    for (let i = 1; i <= total; i++) pages.push(i)
  } else {
    if (current <= 3) {
      pages.push(1, 2, 3, 4, 5)
    } else if (current >= total - 2) {
      pages.push(total - 4, total - 3, total - 2, total - 1, total)
    } else {
      pages.push(current - 2, current - 1, current, current + 1, current + 2)
    }
  }
  return pages
})

// --- Drag & Drop ---
const handleDragStart = (event: DragEvent, index: number) => {
  dragIndex.value = index
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', String(index))
  }
}

const handleDragOver = (event: DragEvent, _index: number) => {
  event.preventDefault()
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'move'
  }
}

const handleDragLeave = () => {}

const handleDrop = (event: DragEvent, targetIndex: number) => {
  event.preventDefault()
  if (dragIndex.value === null || dragIndex.value === targetIndex) {
    handleDragEnd()
    return
  }
  const newOrder = [...columnOrder.value]
  const [movedItem] = newOrder.splice(dragIndex.value, 1)
  newOrder.splice(targetIndex, 0, movedItem)
  columnOrder.value = newOrder
  handleDragEnd()
}

const handleDragEnd = () => {
  dragIndex.value = null
  dragOverIndex.value = null
}

// --- Add Row Sheet ---
const openAddRowSheet = () => {
  if (editingCell.value) cancelEdit()
  isAddRowSheetOpen.value = true
}

const handleSheetSave = async (data: Record<string, any>) => {
  if (isSavingNewRow.value) return
  isSavingNewRow.value = true
  try {
    emit('create', data)
    await new Promise(resolve => setTimeout(resolve, 200))
  } finally {
    isSavingNewRow.value = false
  }
}

// --- Edit Row Sheet ---
const openEditRowSheet = (item: DirectoryItem) => {
  if (editingCell.value) cancelEdit()
  editRowSheetItem.value = item
  isEditRowSheetOpen.value = true
}

const handleEditRowSave = async (itemId: string, data: Record<string, any>) => {
  isSavingEditRow.value = true
  try {
    if (props.onUpdateItem) {
      await props.onUpdateItem(itemId, data)
    } else {
      emit('update', itemId, data)
    }
    isEditRowSheetOpen.value = false
  } finally {
    isSavingEditRow.value = false
  }
}

// --- Inline Editing ---
const isEditing = (itemId: string, colName: string) =>
  editingCell.value?.itemId === itemId && editingCell.value?.colName === colName

const startEdit = (item: DirectoryItem, col: DirectoryColumn) => {
  // Cancel pending blur timeout to prevent it from cancelling the new edit
  if (blurTimeoutId.value) {
    clearTimeout(blurTimeoutId.value)
    blurTimeoutId.value = null
  }
  // Save and close previous cell if it has changes
  if (editingCell.value) {
    saveEdit(true)
  }
  editingCell.value = { itemId: item.id, colName: col.name }
  const rawValue = item.data[col.name]
  editValue.value = rawValue ?? ''
  originalValue.value = rawValue ?? ''
}

const cancelEdit = () => {
  editingCell.value = null
  editValue.value = ''
  originalValue.value = ''
}

const saveEdit = async (shouldClose = false) => {
  if (!editingCell.value || isSaving.value) return
  const { itemId, colName } = editingCell.value
  const newValue = editValue.value
  
  if (newValue === originalValue.value) { 
    if (shouldClose) cancelEdit()
    return 
  }
  
  const item = props.items.find(i => i.id === itemId)
  if (!item) { 
    if (shouldClose) cancelEdit()
    return 
  }
  
  const cleanValue = newValue === '' ? null : newValue
  const updatedData = { ...item.data, [colName]: cleanValue }
  const prevOriginal = originalValue.value

  // 1. Показать индикатор сохранения
  isSaving.value = true

  try {
    // 2. Отправить на сервер и дождаться ответа
    if (props.onUpdateItem) {
      await props.onUpdateItem(itemId, updatedData)
    } else {
      emit('update', itemId, updatedData)
    }

    // 3. Записать в undo-историю
    pushHistory({
      itemId,
      colName,
      oldValue: prevOriginal,
      newValue: cleanValue,
      timestamp: Date.now(),
    })
  } finally {
    isSaving.value = false
  }

  // 4. Закрыть редактирование после успешного сохранения
  if (shouldClose) {
    cancelEdit()
  }
}

const handleBlur = () => {
  if (blurTimeoutId.value) clearTimeout(blurTimeoutId.value)
  // Capture which cell is blurring
  const blurringCell = editingCell.value ? { ...editingCell.value } : null
  blurTimeoutId.value = setTimeout(() => {
    blurTimeoutId.value = null
    // Only save if the same cell is still being edited
    if (
      editingCell.value && blurringCell &&
      editingCell.value.itemId === blurringCell.itemId &&
      editingCell.value.colName === blurringCell.colName
    ) {
      saveEdit(true) // Закрыть редактирование при blur
    }
  }, 150)
}

const handleKeydown = async (
  event: KeyboardEvent, 
  item: DirectoryItem, 
  col: DirectoryColumn, 
  rowIndex: number, 
  colIndex: number
) => {
  if (event.key === 'Escape') { event.preventDefault(); cancelEdit(); return }
  
  if (event.key === 'Enter' && !event.shiftKey) { 
    event.preventDefault()
    await saveEdit(true)
    return 
  }
  
  if (event.key === 'Tab') {
    event.preventDefault()
    await saveEdit(true)
    
    nextTick(() => {
      const cols = orderedColumns.value
      const rows = table.getRowModel().rows
      
      let nextColIndex = event.shiftKey ? colIndex - 1 : colIndex + 1
      let nextRowIndex = rowIndex
      
      if (nextColIndex >= cols.length) { nextColIndex = 0; nextRowIndex = rowIndex + 1 }
      else if (nextColIndex < 0) { nextColIndex = cols.length - 1; nextRowIndex = rowIndex - 1 }
      
      if (nextRowIndex >= 0 && nextRowIndex < rows.length) {
        const nextItem = rows[nextRowIndex].original
        const nextCol = cols[nextColIndex]
        if (nextItem && nextCol) startEdit(nextItem, nextCol)
      }
    })
  }
}

// --- Column Actions ---
const openColumnSettings = (_column: DirectoryColumn) => {
  emit('settings')
}

const hideColumn = (column: DirectoryColumn) => {
  hiddenColumnNames.value.add(column.name)
}

const showAllColumns = () => {
  hiddenColumnNames.value.clear()
}

const deleteColumn = (column: DirectoryColumn) => {
  if (columns.value.length <= 1) return
  emit('deleteColumn', column.name)
}

// --- Undo / Redo ---
const pushHistory = (entry: EditHistoryEntry) => {
  editHistory.value.push(entry)
  if (editHistory.value.length > MAX_HISTORY) editHistory.value.shift()
  redoStack.value = []
}

const canUndo = computed(() => editHistory.value.length > 0)
const canRedo = computed(() => redoStack.value.length > 0)

const undo = async () => {
  const entry = editHistory.value.pop()
  if (!entry) return
  redoStack.value.push(entry)
  const item = props.items.find(i => i.id === entry.itemId)
  if (!item) return
  const restoredData = { ...item.data, [entry.colName]: entry.oldValue }
  if (props.onUpdateItem) {
    await props.onUpdateItem(entry.itemId, restoredData)
  } else {
    emit('update', entry.itemId, restoredData)
  }
}

const redo = async () => {
  const entry = redoStack.value.pop()
  if (!entry) return
  editHistory.value.push(entry)
  const item = props.items.find(i => i.id === entry.itemId)
  if (!item) return
  const reappliedData = { ...item.data, [entry.colName]: entry.newValue }
  if (props.onUpdateItem) {
    await props.onUpdateItem(entry.itemId, reappliedData)
  } else {
    emit('update', entry.itemId, reappliedData)
  }
}

// --- Row Actions ---
const duplicateRow = (item: DirectoryItem) => {
  emit('create', { ...item.data })
}

// --- Global hotkeys ---
const handleGlobalKeydown = (e: KeyboardEvent) => {
  const isMod = e.ctrlKey || e.metaKey

  // Ctrl+Z → undo
  if (isMod && e.key === 'z' && !e.shiftKey) {
    if (canUndo.value) { e.preventDefault(); undo() }
    return
  }
  // Ctrl+Shift+Z or Ctrl+Y → redo
  if ((isMod && e.key === 'z' && e.shiftKey) || (isMod && e.key === 'y')) {
    if (canRedo.value) { e.preventDefault(); redo() }
    return
  }
  // Ctrl+N → new row  (only when table is focused, not in input)
  if (isMod && e.key === 'n' && !isAddRowSheetOpen.value && !editingCell.value) {
    e.preventDefault(); openAddRowSheet()
    return
  }
  // Delete / Backspace on selected rows
  if ((e.key === 'Delete' || e.key === 'Backspace') && !editingCell.value && !isAddRowSheetOpen.value) {
    const ids = selectedRowIds.value
    if (ids.length > 0) { e.preventDefault(); emit('deleteSelected', ids) }
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleGlobalKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleGlobalKeydown)
  if (blurTimeoutId.value) clearTimeout(blurTimeoutId.value)
})

// Reset selection when items change
watch(() => props.items, () => {
  rowSelection.value = {}
}, { deep: true })

// Cancel edit when page changes
watch(() => table.getState().pagination.pageIndex, () => { cancelEdit() })
</script>
