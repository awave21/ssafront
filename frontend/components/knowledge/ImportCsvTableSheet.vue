<template>
  <Sheet :open="open" @update:open="onOpenChange">
    <SheetContent side="right" class-name="flex w-full max-w-2xl flex-col">
      <TooltipProvider :delay-duration="250">
      <SheetHeader>
        <div class="flex items-center justify-between">
          <SheetTitle>Импорт из CSV</SheetTitle>
          <SheetClose />
        </div>
        <p class="mt-1 text-sm text-slate-500">
          Перетащите файл или выберите с диска. Новые колонки из заголовков будут созданы автоматически.
        </p>
      </SheetHeader>

      <div class="flex min-h-0 flex-1 flex-col overflow-hidden">
        <!-- Upload -->
        <div v-if="step === 'upload'" class="flex flex-1 flex-col overflow-y-auto p-6">
          <div
            class="cursor-pointer rounded-lg border-2 border-dashed border-slate-200 p-8 text-center transition-all hover:border-indigo-300 hover:bg-indigo-50/30"
            :class="{ 'border-indigo-400 bg-indigo-50': isDragging }"
            @dragover.prevent="isDragging = true"
            @dragleave.prevent="isDragging = false"
            @drop.prevent="onDrop"
            @click="triggerFileInput"
          >
            <input
              ref="fileInputRef"
              type="file"
              accept=".csv,text/csv"
              class="hidden"
              @change="onFileInputChange"
            />
            <Upload class="mx-auto mb-4 h-12 w-12 text-slate-400" />
            <p class="font-medium text-slate-700">Перетащите CSV сюда</p>
            <p class="mt-1 text-sm text-slate-500">или нажмите для выбора</p>
            <p class="mt-3 text-xs text-slate-400">До 10 МБ, разделитель «,» или «;»</p>
          </div>
          <p v-if="uploadError" class="mt-4 text-sm text-red-600">{{ uploadError }}</p>
        </div>

        <!-- Review -->
        <div v-else-if="step === 'review'" class="flex min-h-0 flex-1 flex-col overflow-hidden">
          <div class="flex-1 space-y-5 overflow-y-auto p-6">
            <div class="flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50 p-4">
              <div class="flex min-w-0 items-center gap-3">
                <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-white">
                  <FileSpreadsheet class="h-5 w-5 text-emerald-600" />
                </div>
                <div class="min-w-0">
                  <p class="truncate text-sm font-medium text-slate-900">{{ fileName }}</p>
                  <p class="text-xs text-slate-500">{{ dataRowCount }} строк данных</p>
                </div>
              </div>
              <button
                type="button"
                class="shrink-0 rounded-lg p-2 text-slate-400 transition-colors hover:bg-red-50 hover:text-red-500"
                title="Другой файл"
                @click="resetFile"
              >
                <Trash2 class="h-4 w-4" />
              </button>
            </div>

            <p v-if="attributeLimitWarning" class="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
              {{ attributeLimitWarning }}
            </p>

            <div v-if="existingMapped.length > 0">
              <p class="mb-2 text-sm font-medium text-slate-700">Колонки таблицы (есть в файле)</p>
              <p class="mb-2 text-xs text-slate-500">
                Сопоставлено автоматически: {{ existingMapped.filter((s) => s.enabled).length }} из
                {{ existingMapped.length }}. Отключите чип, чтобы не импортировать колонку.
              </p>
              <div class="flex flex-wrap gap-2">
                <button
                  v-for="st in existingMapped"
                  :key="'ex-' + st.columnIndex"
                  type="button"
                  class="inline-flex max-w-full items-center gap-1.5 rounded-full border px-3 py-1.5 text-left text-xs font-semibold transition-colors"
                  :class="
                    st.enabled
                      ? 'border-indigo-200 bg-indigo-50 text-indigo-900 hover:bg-indigo-100'
                      : 'border-slate-200 bg-slate-100 text-slate-400 line-through'
                  "
                  @click="st.enabled = !st.enabled"
                >
                  <span class="truncate">{{ st.existingAttr?.label }}</span>
                  <span
                    v-if="st.existingAttr"
                    class="shrink-0 text-[10px] text-slate-500"
                    :title="getTableAttributeTypeMeta(st.existingAttr.attribute_type).hint"
                  >
                    {{ getTableAttributeTypeMeta(st.existingAttr.attribute_type).label }}
                  </span>
                  <span
                    v-if="st.enabled && previewIssueCount(st) > 0"
                    class="shrink-0 rounded bg-amber-100 px-1 text-[10px] text-amber-800"
                  >
                    ⚠ {{ previewIssueCount(st) }}
                  </span>
                </button>
              </div>
            </div>

            <div v-if="newColumns.length > 0">
              <p class="mb-2 text-sm font-medium text-slate-700">Новые колонки из файла</p>
              <p class="mb-3 text-xs text-slate-500">
                Будут созданы атрибуты таблицы. Код (slug) должен быть латиницей: a–z, цифры, «_».
              </p>
              <div class="space-y-3">
                <div
                  v-for="st in newColumns"
                  :key="'nw-' + st.columnIndex"
                  class="rounded-lg border border-slate-100 bg-white p-3"
                  :class="{ 'opacity-50': !st.enabled }"
                >
                  <div class="flex flex-wrap items-start gap-2">
                    <div class="min-w-0 flex-1">
                      <p class="truncate text-sm font-medium text-slate-800">«{{ st.headerRaw }}»</p>
                      <div class="mt-2 flex flex-wrap items-center gap-2">
                        <label class="text-xs text-slate-500">Код</label>
                        <input
                          v-model="st.slug"
                          type="text"
                          class="min-w-[8rem] flex-1 rounded-md border border-slate-200 px-2 py-1 font-mono text-xs"
                          @blur="normalizeSlug(st)"
                        />
                        <div class="flex items-center gap-0.5">
                          <span class="text-xs text-slate-500">Тип</span>
                          <Tooltip>
                            <TooltipTrigger as-child>
                              <button
                                type="button"
                                class="shrink-0 rounded p-0.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
                                :aria-label="`Справка: ${newColumnTypeMeta(st).label}`"
                                @click.prevent
                              >
                                <HelpCircle class="h-3.5 w-3.5" aria-hidden="true" />
                              </button>
                            </TooltipTrigger>
                            <TooltipContent side="top" class="max-w-xs border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 shadow-lg">
                              <p class="font-semibold text-slate-900">{{ newColumnTypeMeta(st).label }}</p>
                              <p class="mt-0.5 font-mono text-[11px] text-slate-500">{{ newColumnTypeMeta(st).syntax }}</p>
                              <p class="mt-2 leading-relaxed text-slate-600">{{ newColumnTypeMeta(st).hint }}</p>
                            </TooltipContent>
                          </Tooltip>
                        </div>
                        <select
                          v-model="st.attributeType"
                          class="max-w-[min(100%,14rem)] rounded-md border border-slate-200 px-2 py-1 text-xs"
                          @change="onNewTypeChange(st)"
                        >
                          <option
                            v-for="opt in TABLE_ATTRIBUTE_TYPE_METAS"
                            :key="opt.value"
                            :value="opt.value"
                          >
                            {{ tableAttributeTypeSelectLabel(opt) }}
                          </option>
                        </select>
                        <button
                          type="button"
                          class="ml-auto rounded p-1 text-slate-400 hover:bg-rose-50 hover:text-rose-600"
                          title="Не импортировать колонку"
                          @click="st.enabled = !st.enabled"
                        >
                          <X class="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="previewColumns.length > 0">
              <p class="mb-2 text-sm font-medium text-slate-700">Превью (первые {{ previewLimit }} строк)</p>
              <div class="max-w-full overflow-x-auto rounded-lg border border-slate-200">
                <table class="w-full min-w-max text-xs">
                  <thead>
                    <tr class="border-b border-slate-200 bg-slate-50">
                      <th
                        v-for="pc in previewColumns"
                        :key="pc.key"
                        class="whitespace-nowrap px-2 py-2 text-left font-bold uppercase tracking-wide text-slate-500"
                      >
                        {{ pc.title }}
                      </th>
                    </tr>
                  </thead>
                  <tbody class="divide-y divide-slate-100">
                    <tr v-for="(pr, ri) in previewRows" :key="ri">
                      <td
                        v-for="pc in previewColumns"
                        :key="pc.key"
                        class="max-w-[200px] truncate px-2 py-1.5 text-slate-600"
                        :class="cellPreviewClass(pc, pr[pc.columnIndex] ?? '')"
                      >
                        {{ pr[pc.columnIndex] || '—' }}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div class="rounded-lg border border-slate-100 bg-slate-50/80 p-3 text-sm text-slate-700">
              <p>Строк к импорту: {{ dataRowCount }}</p>
              <p>Новых атрибутов: {{ enabledNewCount }}</p>
              <p v-if="rowsWithIssues > 0" class="text-amber-800">
                Строк с проблемами коercion (будут пропущены): ~{{ rowsWithIssues }} (оценка по превью)
              </p>
            </div>

            <p v-if="reviewError" class="text-sm text-red-600">{{ reviewError }}</p>
          </div>

          <SheetFooter class-name="shrink-0 border-t border-slate-100 bg-slate-50 p-4">
            <div class="flex flex-wrap justify-end gap-2">
              <button
                type="button"
                class="rounded-md border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100"
                @click="closeSheet"
              >
                Отмена
              </button>
              <button
                type="button"
                class="inline-flex items-center gap-2 rounded-md bg-indigo-600 px-5 py-2 text-sm font-bold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
                :disabled="importing || !!attributeLimitWarning || !canRunImport"
                @click="runImport"
              >
                <Loader2 v-if="importing" class="h-4 w-4 animate-spin" />
                {{ importing ? 'Импорт…' : 'Импортировать' }}
              </button>
            </div>
          </SheetFooter>
        </div>

        <!-- Result -->
        <div v-else-if="step === 'result'" class="flex flex-1 flex-col overflow-y-auto p-6">
          <div class="rounded-lg border border-slate-100 bg-white p-6 text-center">
            <div
              class="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full"
              :class="resultHasServerErrors ? 'bg-amber-100' : 'bg-emerald-100'"
            >
              <AlertCircle v-if="resultHasServerErrors" class="h-8 w-8 text-amber-600" />
              <CheckCircle v-else class="h-8 w-8 text-emerald-600" />
            </div>
            <h3 class="text-lg font-bold text-slate-900">
              {{ resultHasServerErrors ? 'Импорт завершён с предупреждениями' : 'Импорт завершён' }}
            </h3>
            <p class="mt-2 text-slate-600">Создано атрибутов: {{ resultAttrsCreated }}</p>
            <p class="text-slate-600">Импортировано строк: {{ resultRowsCreated }}</p>
            <p v-if="resultRowsFailed > 0" class="text-amber-700">Ошибок на сервере: {{ resultRowsFailed }}</p>
            <p v-if="resultSkippedCoerce > 0" class="text-slate-600">
              Пропущено при разборе строк: {{ resultSkippedCoerce }}
            </p>
            <button
              v-if="resultErrorsJson"
              type="button"
              class="mt-4 text-sm font-semibold text-indigo-600 hover:text-indigo-800"
              @click="downloadErrorLog"
            >
              Скачать лог ошибок (JSON)
            </button>
          </div>
          <div class="mt-6 flex justify-end">
            <button
              type="button"
              class="rounded-md bg-indigo-600 px-6 py-2 text-sm font-bold text-white hover:bg-indigo-700"
              @click="finishResult"
            >
              Готово
            </button>
          </div>
        </div>
      </div>
      </TooltipProvider>
    </SheetContent>
  </Sheet>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import {
  AlertCircle,
  CheckCircle,
  FileSpreadsheet,
  HelpCircle,
  Loader2,
  Trash2,
  Upload,
  X,
} from 'lucide-vue-next'
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '~/components/ui/sheet'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '~/components/ui/tooltip'
import { useToast } from '~/composables/useToast'
import { decodeCsvBuffer } from '~/utils/csvTextDecode'
import { ensureUniqueSlug, slugifyHeader } from '~/utils/slugify'
import {
  checkCellType,
  coercePayloadFromData,
  countTypeIssuesInPreview,
  inferColumnType,
  normHeaderCell,
  parseCsvTable,
  type ParsedCsvTable,
} from '~/utils/tableCsvImport'
import {
  getTableAttributeTypeMeta,
  TABLE_ATTRIBUTE_TYPE_METAS,
  tableAttributeTypeSelectLabel,
} from '~/utils/tableAttributeTypes'
import type { TableAttribute, TableAttributeType, TableRecordsBulkCreateResponse } from '~/types/tables'

const MAX_FILE_BYTES = 10 * 1024 * 1024
const MAX_ATTRIBUTES_PER_TABLE = 100
const BATCH_BULK = 1000
const PREVIEW_LIMIT = 10

type ColumnImportState = {
  columnIndex: number
  headerRaw: string
  kind: 'existing' | 'new'
  existingAttr: TableAttribute | null
  slug: string
  attributeType: TableAttributeType
  enabled: boolean
}

const newColumnTypeMeta = (st: ColumnImportState) => getTableAttributeTypeMeta(st.attributeType)

const props = defineProps<{
  open: boolean
  tableId: string
  attributes: TableAttribute[]
  totalAttributeCount: number
  tablesApi: {
    createAttribute: (
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
    ) => Promise<TableAttribute>
    bulkCreateRecords: (
      tableId: string,
      records: Record<string, unknown>[]
    ) => Promise<TableRecordsBulkCreateResponse>
  }
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  imported: []
}>()

const { error: toastError, success: toastSuccess } = useToast()

const step = ref<'upload' | 'review' | 'result'>('upload')
const isDragging = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)
const uploadError = ref('')
const reviewError = ref('')
const fileName = ref('')
const parsed = ref<ParsedCsvTable | null>(null)
const columnStates = ref<ColumnImportState[]>([])
const importing = ref(false)

const resultAttrsCreated = ref(0)
const resultRowsCreated = ref(0)
const resultRowsFailed = ref(0)
const resultSkippedCoerce = ref(0)
const resultErrorsJson = ref<string | null>(null)

const previewLimit = PREVIEW_LIMIT

const dataRowCount = computed(() => parsed.value?.rowCount ?? 0)

const existingMapped = computed(() => columnStates.value.filter((s) => s.kind === 'existing'))

const newColumns = computed(() => columnStates.value.filter((s) => s.kind === 'new'))

const enabledNewCount = computed(() => newColumns.value.filter((s) => s.enabled).length)

const attributeLimitWarning = computed(() => {
  const add = enabledNewCount.value
  if (add === 0) return ''
  if (props.totalAttributeCount + add > MAX_ATTRIBUTES_PER_TABLE) {
    return `Превышен лимит атрибутов (${MAX_ATTRIBUTES_PER_TABLE}). Сейчас ${props.totalAttributeCount}, при импорте добавится ${add}. Отключите лишние новые колонки.`
  }
  return ''
})

const enabledStates = computed(() => columnStates.value.filter((s) => s.enabled))

const previewColumns = computed(() => {
  const p = parsed.value
  if (!p) return []
  return enabledStates.value.map((st) => ({
    key: `${st.columnIndex}-${st.slug}`,
    columnIndex: st.columnIndex,
    title:
      st.kind === 'existing'
        ? `${st.existingAttr?.label ?? st.slug}`
        : `${st.headerRaw} (новый)`,
    state: st,
  }))
})

const previewRows = computed(() => {
  const p = parsed.value
  if (!p) return []
  const lim = Math.min(PREVIEW_LIMIT, p.dataRows.length)
  return p.dataRows.slice(0, lim)
})

const syntheticAttr = (st: ColumnImportState): TableAttribute => {
  return {
    id: 'tmp',
    table_id: props.tableId,
    name: st.slug,
    label: st.headerRaw.slice(0, 200),
    attribute_type: st.attributeType,
    type_config: {},
    is_required: false,
    is_searchable: true,
    is_unique: false,
    order_index: 999,
  }
}

const attrForPreview = (st: ColumnImportState): TableAttribute => {
  if (st.kind === 'existing' && st.existingAttr) return st.existingAttr
  return syntheticAttr(st)
}

const previewIssueCount = (st: ColumnImportState): number => {
  const p = parsed.value
  if (!p || !st.enabled) return 0
  return countTypeIssuesInPreview(st.columnIndex, PREVIEW_LIMIT, p, attrForPreview(st))
}

const cellPreviewClass = (pc: { columnIndex: number; state: ColumnImportState }, cell: string) => {
  const st = pc.state
  if (!st.enabled) return ''
  const ok = checkCellType(cell, attrForPreview(st))
  return ok ? '' : 'bg-amber-50 text-amber-900'
}

/** Грубая оценка: сколько строк в превью не пройдут coerce (все включённые колонки). */
const rowsWithIssues = computed(() => {
  const p = parsed.value
  if (!p || previewRows.value.length === 0) return 0
  const merged = attrsMergedForCoerce()
  let bad = 0
  for (let r = 0; r < previewRows.value.length; r++) {
    const row = buildRowStrings(r)
    try {
      coercePayloadFromData(row, merged)
    } catch {
      bad++
    }
  }
  return bad
})

const canRunImport = computed(() => {
  if (!parsed.value || dataRowCount.value === 0) return false
  if (enabledStates.value.length === 0) return false
  return true
})

const resultHasServerErrors = computed(() => resultRowsFailed.value > 0 || !!resultErrorsJson.value)

const resetAll = () => {
  step.value = 'upload'
  uploadError.value = ''
  reviewError.value = ''
  fileName.value = ''
  parsed.value = null
  columnStates.value = []
  importing.value = false
  resultAttrsCreated.value = 0
  resultRowsCreated.value = 0
  resultRowsFailed.value = 0
  resultSkippedCoerce.value = 0
  resultErrorsJson.value = null
}

watch(
  () => props.open,
  (v) => {
    if (!v) resetAll()
  }
)

const onOpenChange = (v: boolean) => {
  if (!v) emit('update:open', false)
  else emit('update:open', true)
}

const closeSheet = () => {
  emit('update:open', false)
}

const triggerFileInput = () => {
  fileInputRef.value?.click()
}

const processFile = async (file: File | null | undefined) => {
  uploadError.value = ''
  if (!file) return
  if (!file.name.toLowerCase().endsWith('.csv')) {
    uploadError.value = 'Нужен файл с расширением .csv'
    return
  }
  if (file.size > MAX_FILE_BYTES) {
    uploadError.value = 'Файл больше 10 МБ'
    return
  }
  try {
    const buffer = await file.arrayBuffer()
    const text = decodeCsvBuffer(buffer)
    const table = parseCsvTable(text)
    if (!table) {
      uploadError.value = 'Пустой CSV или нет строки заголовков и данных'
      return
    }
    fileName.value = file.name
    parsed.value = table
    columnStates.value = buildColumnStates(table, props.attributes)
    step.value = 'review'
  } catch {
    uploadError.value = 'Не удалось прочитать файл'
  }
}

const buildColumnStates = (table: ParsedCsvTable, userAttrs: TableAttribute[]): ColumnImportState[] => {
  const used = new Set<string>()
  const reserved = new Set(userAttrs.map((a) => a.name))
  const states: ColumnImportState[] = []

  for (let i = 0; i < table.headerCells.length; i++) {
    const headerRaw = table.headerCells[i]
    const n = normHeaderCell(headerRaw)
    const attr = userAttrs.find(
      (a) =>
        !used.has(a.name) && (normHeaderCell(a.name) === n || normHeaderCell(a.label) === n)
    )
    const samples = table.dataRows.map((row) => row[i] ?? '').slice(0, 20)

    if (attr) {
      used.add(attr.name)
      states.push({
        columnIndex: i,
        headerRaw,
        kind: 'existing',
        existingAttr: attr,
        slug: attr.name,
        attributeType: attr.attribute_type,
        enabled: true,
      })
    } else {
      const inferred = inferColumnType(samples)
      const slug = ensureUniqueSlug(slugifyHeader(headerRaw), reserved)
      states.push({
        columnIndex: i,
        headerRaw,
        kind: 'new',
        existingAttr: null,
        slug,
        attributeType: inferred,
        enabled: true,
      })
    }
  }
  return states
}

const onDrop = (e: DragEvent) => {
  isDragging.value = false
  const f = e.dataTransfer?.files?.[0]
  void processFile(f)
}

const onFileInputChange = (e: Event) => {
  const input = e.target as HTMLInputElement
  const f = input.files?.[0]
  input.value = ''
  void processFile(f)
}

const resetFile = () => {
  step.value = 'upload'
  parsed.value = null
  columnStates.value = []
  fileName.value = ''
  uploadError.value = ''
}

const normalizeSlug = (st: ColumnImportState) => {
  if (st.kind !== 'new') return
  const taken = new Set(props.attributes.map((a) => a.name))
  for (const s of columnStates.value) {
    if (s.kind === 'new' && s !== st) taken.add(s.slug)
  }
  taken.delete(st.slug)
  st.slug = ensureUniqueSlug(slugifyHeader(st.slug), taken)
}

const onNewTypeChange = (_st: ColumnImportState) => {
  reviewError.value = ''
}

const typeConfigForNew = (_st: ColumnImportState): Record<string, unknown> => {
  return {}
}

const maxOrderIndex = computed(() =>
  props.attributes.length ? Math.max(...props.attributes.map((a) => a.order_index)) : 0
)

/** Атрибуты для coerce: только включённые существующие колонки + новые (ещё не в props до refetch). */
const attrsMergedForCoerce = (): TableAttribute[] => {
  const enabledExisting = enabledStates.value
    .filter((s): s is ColumnImportState & { existingAttr: TableAttribute } => s.kind === 'existing' && s.existingAttr !== null)
    .map((s) => s.existingAttr)
  const newSynth = enabledStates.value.filter((s) => s.kind === 'new').map((s) => syntheticAttr(s))
  return [...enabledExisting, ...newSynth]
}

const buildRowStrings = (rowIndex: number): Record<string, string> => {
  const p = parsed.value!
  const obj: Record<string, string> = {}
  for (const st of enabledStates.value) {
    const cell = p.dataRows[rowIndex]?.[st.columnIndex] ?? ''
    if (st.kind === 'existing' && st.existingAttr) obj[st.existingAttr.name] = cell
    else obj[st.slug] = cell
  }
  return obj
}

const runImport = async () => {
  const p = parsed.value
  if (!p) return
  reviewError.value = ''

  importing.value = true
  resultErrorsJson.value = null
  let attrsCreated = 0
  let totalCreated = 0
  let totalFailed = 0
  const allErrors: Record<string, unknown>[] = []

  try {
    const newEnabled = newColumns.value.filter((s) => s.enabled)
    let orderBase = maxOrderIndex.value + 1

    const takenForSlug = new Set(props.attributes.map((a) => a.name))
    for (let i = 0; i < newEnabled.length; i++) {
      const st = newEnabled[i]
      st.slug = ensureUniqueSlug(slugifyHeader(st.slug), takenForSlug)
      await props.tablesApi.createAttribute(props.tableId, {
        name: st.slug,
        label: st.headerRaw.slice(0, 200),
        attribute_type: st.attributeType,
        type_config: typeConfigForNew(st),
        is_required: false,
        is_searchable: true,
        is_unique: false,
        order_index: orderBase + i,
      })
      attrsCreated++
    }

    const attrsMerged = attrsMergedForCoerce()

    const payloads: Record<string, unknown>[] = []
    let skipped = 0
    for (let r = 0; r < p.dataRows.length; r++) {
      const rowObj = buildRowStrings(r)
      try {
        payloads.push(coercePayloadFromData(rowObj, attrsMerged))
      } catch {
        skipped++
      }
    }

    for (let i = 0; i < payloads.length; i += BATCH_BULK) {
      const chunk = payloads.slice(i, i + BATCH_BULK)
      if (chunk.length === 0) continue
      const res = await props.tablesApi.bulkCreateRecords(props.tableId, chunk)
      totalCreated += res.created
      totalFailed += res.failed
      if (Array.isArray(res.errors) && res.errors.length) allErrors.push(...res.errors)
    }

    resultAttrsCreated.value = attrsCreated
    resultRowsCreated.value = totalCreated
    resultRowsFailed.value = totalFailed
    resultSkippedCoerce.value = skipped
    resultErrorsJson.value = allErrors.length ? JSON.stringify(allErrors, null, 2) : null
    emit('imported')

    if (totalFailed === 0) {
      const parts: string[] = []
      if (attrsCreated > 0) parts.push(`Новых колонок: ${attrsCreated}`)
      parts.push(`Импортировано строк: ${totalCreated}`)
      if (skipped > 0) parts.push(`Пропущено при разборе: ${skipped}`)
      toastSuccess('Импорт завершён', parts.join(' · '))
      emit('update:open', false)
    } else {
      step.value = 'result'
    }
  } catch (e: any) {
    toastError(e?.message ?? 'Импорт не удался')
  } finally {
    importing.value = false
  }
}

const downloadErrorLog = () => {
  if (!resultErrorsJson.value) return
  const blob = new Blob([resultErrorsJson.value], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'import-errors.json'
  a.click()
  URL.revokeObjectURL(url)
}

const finishResult = () => {
  emit('update:open', false)
}
</script>
