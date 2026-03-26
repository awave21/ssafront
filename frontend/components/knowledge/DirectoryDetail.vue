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

    <!-- Hint bar + hidden columns -->
    <div v-if="items.length > 0" class="flex items-center justify-between gap-4 flex-wrap">
      <p class="text-xs text-slate-400">
        Клик по ячейке открывает запись в боковой панели.
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
            <TableHead class="w-10 min-w-10 max-w-10"></TableHead>
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
        <Table
          :style="{
            width: `${table.getTotalSize() + selectAndActionsChromeWidth}px`,
            minWidth: '100%',
          }"
        >
          <TableHeader>
            <TableRow>
              <TableHead class-name="w-10 min-w-10 max-w-10 !px-0">
                <div class="flex items-center justify-center h-full py-2">
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
                @dragenter.prevent="onDragEnterHeader(header.index - 1)"
                @dragleave="handleDragLeave"
                @drop="handleDrop($event, header.index - 1)"
                @dragend="handleDragEnd"
                :class-name="`relative select-none ${!isColumnStructureLocked && dragOverIndex === header.index - 1 && dragIndex !== header.index - 1 ? 'bg-indigo-100' : ''} ${!isColumnStructureLocked && dragIndex === header.index - 1 ? 'opacity-50' : ''}`"
                :style="{ width: `${header.getSize()}px` }"
              >
                <template v-if="isColumnStructureLocked">
                  <div class="flex items-center px-2 py-1 min-h-[36px]">
                    <span class="text-xs font-semibold text-slate-500 uppercase tracking-wide truncate">
                      {{ (header.column.columnDef.meta as DirectoryColumn).label }}
                    </span>
                  </div>
                </template>
                <ColumnHeaderDropdown
                  v-else
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
              <!-- Add column: только для custom / clipboard_import -->
              <TableHead v-if="!isColumnStructureLocked" class-name="w-40">
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
              <TableRow class="group">
                <TableCell class-name="w-10 min-w-10 max-w-10 !px-0">
                  <div class="flex items-center justify-center h-full py-2">
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
                  class-name="px-1 py-1 cursor-pointer"
                  :style="{ width: `${getColSize(col.name)}px` }"
                  @click.stop="openEditRowSheet(row.original)"
                >
                  <EditableCell
                    :column="col"
                    :display-value="row.original.data[col.name]"
                    :model-value="row.original.data[col.name]"
                    :editing="false"
                  />
                </TableCell>
                <TableCell v-if="!isColumnStructureLocked" class-name="px-2 py-2 w-40"></TableCell>
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
      :row-save="handleSheetSave"
      @update:open="isAddRowSheetOpen = $event"
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
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
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
  Trash2,
  EyeOff,
  X,
  Plus,
} from 'lucide-vue-next'
import type { Directory, DirectoryItem, DirectoryColumn } from '~/types/directories'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '~/components/ui/table'
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
  onCreateItem?: (data: Record<string, any>) => Promise<void>
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

/** Во вкладке «Справочники» только шаблон custom уходит на «Таблицы» с редактируемыми колонками; остальное — фиксированные столбцы без меню в заголовке */
const isColumnStructureLocked = computed(() => props.directory.template !== 'custom')

/** Ширина колонок вне TanStack: чекбокс + опционально «Столбец» + колонка действий */
const selectAndActionsChromeWidth = computed(() => {
  const selectCol = 40 // w-10
  const actionsCol = 64 // w-16
  const addColumnCol = isColumnStructureLocked.value ? 0 : 160 // w-40
  return selectCol + actionsCol + addColumnCol
})

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
  if (isColumnStructureLocked.value) return
  dragIndex.value = index
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', String(index))
  }
}

const onDragEnterHeader = (index: number) => {
  if (isColumnStructureLocked.value) return
  dragOverIndex.value = index
}

const handleDragOver = (event: DragEvent, _index: number) => {
  if (isColumnStructureLocked.value) return
  event.preventDefault()
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'move'
  }
}

const handleDragLeave = () => {}

const handleDrop = (event: DragEvent, targetIndex: number) => {
  if (isColumnStructureLocked.value) return
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
  isAddRowSheetOpen.value = true
}

const handleSheetSave = async (data: Record<string, any>) => {
  if (isSavingNewRow.value) return
  isSavingNewRow.value = true
  try {
    if (props.onCreateItem) {
      await props.onCreateItem(data)
    } else {
      emit('create', data)
    }
  } finally {
    isSavingNewRow.value = false
  }
}

// --- Edit Row Sheet ---
const openEditRowSheet = (item: DirectoryItem) => {
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

// --- Column Actions ---
const openColumnSettings = (_column: DirectoryColumn) => {
  emit('settings')
}

const hideColumn = (column: DirectoryColumn) => {
  if (isColumnStructureLocked.value) return
  hiddenColumnNames.value.add(column.name)
}

const showAllColumns = () => {
  hiddenColumnNames.value.clear()
}

const deleteColumn = (column: DirectoryColumn) => {
  if (isColumnStructureLocked.value) return
  if (columns.value.length <= 1) return
  emit('deleteColumn', column.name)
}

// --- Row Actions ---
const duplicateRow = async (item: DirectoryItem) => {
  const data = { ...item.data }
  if (props.onCreateItem) {
    await props.onCreateItem(data)
  } else {
    emit('create', data)
  }
}

// --- Global hotkeys ---
const handleGlobalKeydown = (e: KeyboardEvent) => {
  const isMod = e.ctrlKey || e.metaKey
  const sheetOrModalOpen = isAddRowSheetOpen.value || isEditRowSheetOpen.value

  if (isMod && e.key === 'n' && !sheetOrModalOpen) {
    e.preventDefault()
    openAddRowSheet()
    return
  }
  if ((e.key === 'Delete' || e.key === 'Backspace') && !sheetOrModalOpen) {
    const ids = selectedRowIds.value
    if (ids.length > 0) {
      e.preventDefault()
      emit('deleteSelected', ids)
    }
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleGlobalKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleGlobalKeydown)
})

// Reset selection when items change
watch(() => props.items, () => {
  rowSelection.value = {}
}, { deep: true })

</script>
