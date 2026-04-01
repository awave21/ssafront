<template>
  <div class="space-y-4">
    <div v-if="errorMessage" class="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
      <div class="flex items-center justify-between gap-3">
        <span>{{ errorMessage }}</span>
        <Button size="sm" variant="outline" @click="emit('retry')">Повторить</Button>
      </div>
    </div>

    <Table wrapper-class="rounded-3xl border border-slate-100 shadow-sm overflow-hidden">
      <colgroup>
        <col
          v-for="column in orderedColumns"
          :key="column.id"
          :style="{ width: `${columnWidths[column.id]}px` }"
        >
      </colgroup>

      <TableHeader class-name="bg-slate-50/50">
        <TableRow class-name="hover:bg-transparent border-b border-slate-100">
          <TableHead
            v-for="column in orderedColumns"
            :key="column.id"
            class-name="relative py-4"
            :style="columnCellStyle(column.id)"
          >
            <div
              class="flex items-center gap-1"
              draggable="true"
              @dragstart="onDragStart(column.id)"
              @dragover.prevent
              @drop.prevent="onDrop(column.id)"
              @dragend="onDragEnd"
            >
              <div
                class="flex h-5 w-5 items-center justify-center rounded text-slate-300 hover:text-slate-500 transition-colors cursor-grab active:cursor-grabbing"
                title="Перетащить столбец"
              >
                <GripVertical class="h-3 w-3" />
              </div>

              <Button
                v-if="column.sortBy"
                variant="ghost"
                size="sm"
                class="h-7 px-2 text-[11px] font-black uppercase tracking-wider text-slate-500 hover:bg-white hover:text-primary transition-all"
                @click="emitSort(column.sortBy)"
              >
                <span>{{ column.label }}</span>
                <span class="ml-1.5 inline-flex w-3 justify-center text-[10px] text-primary">{{ sortIndicator(column.sortBy) }}</span>
              </Button>
              <span v-else class="px-2 text-[11px] font-black uppercase tracking-wider text-slate-400">
                {{ column.label }}
              </span>
            </div>


            <button
              type="button"
              class="absolute right-0 top-0 h-full w-2 cursor-col-resize bg-transparent hover:bg-slate-200/70"
              title="Изменить ширину"
              @mousedown.stop.prevent="startResize($event, column.id)"
            />
          </TableHead>
        </TableRow>
      </TableHeader>

      <TableBody>
        <template v-if="loading && !items.length">
          <TableRow v-for="i in 10" :key="i">
            <TableCell v-for="column in orderedColumns" :key="column.id">
              <div class="h-4 rounded bg-slate-100 animate-pulse" />
            </TableCell>
          </TableRow>
        </template>

        <template v-else-if="items.length">
          <TableRow 
            v-for="item in items" 
            :key="item.commodity_key"
            class-name="group/row hover:bg-slate-50/80 transition-colors border-b border-slate-50 last:border-0"
          >
            <TableCell
              v-for="column in orderedColumns"
              :key="column.id"
              :class-name="column.id === 'commodity_name' ? 'font-bold text-slate-900' : 'text-slate-600'"
              :style="columnCellStyle(column.id)"
            >
              <template v-if="column.id === 'commodity_name'">
                <div class="flex items-center gap-3">
                  <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-[10px] font-black text-slate-400 group-hover/row:bg-primary group-hover/row:text-white transition-all">
                    {{ item.commodity_name.charAt(0).toUpperCase() }}
                  </div>
                  <div class="flex flex-col min-w-0">
                    <span class="truncate">{{ item.commodity_name }}</span>
                    <span v-if="item.commodity_category" class="text-[9px] font-bold uppercase tracking-tight text-slate-400">
                      {{ item.commodity_category }}
                    </span>
                  </div>
                  <Badge
                    v-if="item.commodity_name.toLowerCase() === 'не определено'"
                    variant="secondary"
                    class="bg-amber-50 text-amber-600 border-amber-100 text-[9px] font-bold"
                  >
                    NEW
                  </Badge>
                </div>
              </template>
              <template v-else-if="column.id === 'share_bookings'">
                <div class="flex items-center gap-2">
                  <div class="h-1.5 w-12 overflow-hidden rounded-full bg-slate-100">
                    <div 
                      class="h-full bg-primary transition-all duration-500"
                      :style="{ width: `${item.share_bookings * 100}%` }"
                    />
                  </div>
                  <span class="text-[11px] font-bold">{{ formatPercent(item.share_bookings * 100) }}</span>
                </div>
              </template>
              <template v-else>
                <span :class="{'font-black text-slate-900': column.id === 'revenue_total'}">
                  {{ renderItemCell(item, column.id) }}
                </span>
              </template>
            </TableCell>
          </TableRow>
        </template>


        <TableRow v-else>
          <TableCell class-name="text-center text-slate-500" :colspan="orderedColumns.length">
            Нет данных за выбранный период/фильтры
          </TableCell>
        </TableRow>
      </TableBody>

      <TableFooter v-if="totals && !loading">
        <TableRow class-name="hover:bg-transparent">
          <TableCell
            v-for="column in orderedColumns"
            :key="column.id"
            :class-name="column.id === 'commodity_name' ? 'font-semibold text-slate-900' : undefined"
            :style="columnCellStyle(column.id)"
          >
            {{ renderTotalsCell(column.id) }}
          </TableCell>
        </TableRow>
      </TableFooter>
    </Table>

    <div class="flex items-center justify-between">
      <p class="text-xs text-slate-500">
        Показано {{ items.length }} из {{ totalItems }}
      </p>
      <div class="flex items-center gap-2">
        <Button size="sm" variant="outline" :disabled="currentPage <= 1 || loading" @click="emit('page-change', currentPage - 1)">
          Назад
        </Button>
        <span class="text-xs text-slate-600">Страница {{ currentPage }} / {{ totalPages }}</span>
        <Button size="sm" variant="outline" :disabled="currentPage >= totalPages || loading" @click="emit('page-change', currentPage + 1)">
          Далее
        </Button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { GripVertical } from 'lucide-vue-next'
import Button from '~/components/ui/button/Button.vue'
import { Badge } from '~/components/ui/badge'
import Table from '~/components/ui/table/Table.vue'
import TableBody from '~/components/ui/table/TableBody.vue'
import TableCell from '~/components/ui/table/TableCell.vue'
import TableFooter from '~/components/ui/table/TableFooter.vue'
import TableHead from '~/components/ui/table/TableHead.vue'
import TableHeader from '~/components/ui/table/TableHeader.vue'
import TableRow from '~/components/ui/table/TableRow.vue'
import type {
  AnalyticsCommodityTableItem,
  AnalyticsCommoditiesTableTotals,
  CommoditiesTableSortBy,
  CommoditiesTableSortOrder,
} from '~/types/analytics'

type ColumnId =
  | 'commodity_name'
  | 'commodity_category'
  | 'bookings_total'
  | 'arrived_total'
  | 'primary_total'
  | 'primary_arrived_total'
  | 'repeat_total'
  | 'repeat_arrived_total'
  | 'conversion'
  | 'revenue_total'
  | 'payments_total'
  | 'avg_check'
  | 'share_bookings'

type ColumnDef = {
  id: ColumnId
  label: string
  sortBy?: CommoditiesTableSortBy
}

const STORAGE_KEY = 'analytics-commodities-table-columns-v1'
const MIN_COLUMN_WIDTH = 90

const DEFAULT_COLUMNS: ColumnDef[] = [
  { id: 'commodity_name', label: 'Товар', sortBy: 'commodity_name' },
  { id: 'commodity_category', label: 'Категория' },
  { id: 'bookings_total', label: 'Записи', sortBy: 'bookings_total' },
  { id: 'arrived_total', label: 'Дошедшие', sortBy: 'arrived_total' },
  { id: 'primary_total', label: 'Первичные', sortBy: 'primary_total' },
  { id: 'primary_arrived_total', label: 'Перв. дошедшие', sortBy: 'primary_arrived_total' },
  { id: 'repeat_total', label: 'Повторные', sortBy: 'repeat_total' },
  { id: 'repeat_arrived_total', label: 'Повт. дошедшие' },
  { id: 'conversion', label: 'Конверсия %' },
  { id: 'revenue_total', label: 'Выручка', sortBy: 'revenue_total' },
  { id: 'payments_total', label: 'Платежи' },
  { id: 'avg_check', label: 'Средний чек', sortBy: 'avg_check' },
  { id: 'share_bookings', label: 'Доля записей %' },
]

const DEFAULT_WIDTHS: Record<ColumnId, number> = {
  commodity_name: 260,
  commodity_category: 170,
  bookings_total: 120,
  arrived_total: 120,
  primary_total: 120,
  primary_arrived_total: 150,
  repeat_total: 120,
  repeat_arrived_total: 150,
  conversion: 130,
  revenue_total: 150,
  payments_total: 110,
  avg_check: 140,
  share_bookings: 140,
}

const props = defineProps<{
  items: AnalyticsCommodityTableItem[]
  loading: boolean
  errorMessage: string | null
  totals: AnalyticsCommoditiesTableTotals | null
  totalItems: number
  currentPage: number
  totalPages: number
  sortBy: CommoditiesTableSortBy
  sortOrder: CommoditiesTableSortOrder
}>()

const emit = defineEmits<{
  (e: 'sort-change', sortBy: CommoditiesTableSortBy): void
  (e: 'page-change', page: number): void
  (e: 'retry'): void
}>()

const intFormatter = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 })
const moneyFormatter = new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 0, maximumFractionDigits: 2 })
const percentFormatter = new Intl.NumberFormat('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 })

const formatInt = (value: number) => intFormatter.format(Number.isFinite(value) ? value : 0)
const formatMoney = (value: number) => `${moneyFormatter.format(Number.isFinite(value) ? value : 0)} ₽`
const formatPercent = (value: number) => `${percentFormatter.format(Number.isFinite(value) ? value : 0)}%`

const columnsById = DEFAULT_COLUMNS.reduce<Record<ColumnId, ColumnDef>>((acc, column) => {
  acc[column.id] = column
  return acc
}, {} as Record<ColumnId, ColumnDef>)

const columnOrder = ref<ColumnId[]>(DEFAULT_COLUMNS.map(column => column.id))
const columnWidths = ref<Record<ColumnId, number>>({ ...DEFAULT_WIDTHS })

const orderedColumns = computed(() => columnOrder.value.map(id => columnsById[id]).filter(Boolean))

const saveColumnsState = () => {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({
      order: columnOrder.value,
      widths: columnWidths.value,
    }),
  )
}

onMounted(() => {
  if (typeof window === 'undefined') return
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return
    const parsed = JSON.parse(raw) as { order?: ColumnId[]; widths?: Partial<Record<ColumnId, number>> }
    if (Array.isArray(parsed.order) && parsed.order.length === DEFAULT_COLUMNS.length) {
      const valid = parsed.order.every(id => Object.prototype.hasOwnProperty.call(columnsById, id))
      if (valid) columnOrder.value = parsed.order
    }
    if (parsed.widths && typeof parsed.widths === 'object') {
      columnWidths.value = {
        ...DEFAULT_WIDTHS,
        ...Object.fromEntries(
          Object.entries(parsed.widths).map(([key, value]) => [key, Math.max(MIN_COLUMN_WIDTH, Number(value) || DEFAULT_WIDTHS[key as ColumnId])]),
        ) as Record<ColumnId, number>,
      }
    }
  } catch {
    // Ignore corrupted localStorage payload
  }
})

watch(columnOrder, saveColumnsState, { deep: true })
watch(columnWidths, saveColumnsState, { deep: true })

const draggingColumn = ref<ColumnId | null>(null)
const onDragStart = (id: ColumnId) => {
  draggingColumn.value = id
}
const onDragEnd = () => {
  draggingColumn.value = null
}
const onDrop = (targetId: ColumnId) => {
  if (!draggingColumn.value || draggingColumn.value === targetId) return
  const current = [...columnOrder.value]
  const sourceIndex = current.indexOf(draggingColumn.value)
  const targetIndex = current.indexOf(targetId)
  if (sourceIndex < 0 || targetIndex < 0) return
  const [moved] = current.splice(sourceIndex, 1)
  current.splice(targetIndex, 0, moved)
  columnOrder.value = current
}

const resizingColumn = ref<ColumnId | null>(null)
const resizeStartX = ref(0)
const resizeStartWidth = ref(0)

const onMouseMove = (event: MouseEvent) => {
  if (!resizingColumn.value) return
  const delta = event.clientX - resizeStartX.value
  const nextWidth = Math.max(MIN_COLUMN_WIDTH, resizeStartWidth.value + delta)
  columnWidths.value = {
    ...columnWidths.value,
    [resizingColumn.value]: nextWidth,
  }
}

const stopResize = () => {
  if (!resizingColumn.value) return
  resizingColumn.value = null
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', stopResize)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}

const startResize = (event: MouseEvent, id: ColumnId) => {
  if (typeof window === 'undefined') return
  resizingColumn.value = id
  resizeStartX.value = event.clientX
  resizeStartWidth.value = columnWidths.value[id]
  document.body.style.cursor = 'col-resize'
  document.body.style.userSelect = 'none'
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', stopResize)
}

onBeforeUnmount(() => {
  if (typeof window === 'undefined') return
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', stopResize)
})

const emitSort = (sortBy: CommoditiesTableSortBy) => emit('sort-change', sortBy)
const sortIndicator = (column: CommoditiesTableSortBy) => {
  if (props.sortBy !== column) return '·'
  return props.sortOrder === 'asc' ? '↑' : '↓'
}

const columnCellStyle = (id: ColumnId) => {
  const width = columnWidths.value[id]
  return {
    width: `${width}px`,
    minWidth: `${width}px`,
    maxWidth: `${width}px`,
  }
}

const renderItemCell = (item: AnalyticsCommodityTableItem, columnId: ColumnId) => {
  switch (columnId) {
    case 'commodity_category':
      return item.commodity_category || '—'
    case 'bookings_total':
      return formatInt(item.bookings_total)
    case 'arrived_total':
      return formatInt(item.arrived_total)
    case 'primary_total':
      return formatInt(item.primary_total)
    case 'primary_arrived_total':
      return formatInt(item.primary_arrived_total)
    case 'repeat_total':
      return formatInt(item.repeat_total)
    case 'repeat_arrived_total':
      return formatInt(item.repeat_arrived_total)
    case 'conversion':
      return formatPercent(item.bookings_total > 0 ? (item.arrived_total / item.bookings_total) * 100 : 0)
    case 'revenue_total':
      return formatMoney(item.revenue_total)
    case 'payments_total':
      return formatInt(item.payments_total)
    case 'avg_check':
      return formatMoney(item.avg_check)
    case 'share_bookings':
      return formatPercent(item.share_bookings * 100)
    default:
      return ''
  }
}

const renderTotalsCell = (columnId: ColumnId) => {
  if (!props.totals) return ''
  switch (columnId) {
    case 'commodity_name':
      return 'Итого'
    case 'commodity_category':
      return '—'
    case 'bookings_total':
      return formatInt(props.totals.bookings_total)
    case 'arrived_total':
      return formatInt(props.totals.arrived_total)
    case 'primary_total':
      return formatInt(props.totals.primary_total)
    case 'primary_arrived_total':
      return formatInt(props.totals.primary_arrived_total)
    case 'repeat_total':
      return formatInt(props.totals.repeat_total)
    case 'repeat_arrived_total':
      return formatInt(props.totals.repeat_arrived_total)
    case 'conversion':
      return formatPercent(props.totals.bookings_total > 0 ? (props.totals.arrived_total / props.totals.bookings_total) * 100 : 0)
    case 'revenue_total':
      return formatMoney(props.totals.revenue_total)
    case 'payments_total':
      return formatInt(props.totals.payments_total)
    case 'avg_check':
      return formatMoney(props.totals.avg_check)
    case 'share_bookings':
      return '100%'
    default:
      return ''
  }
}
</script>
