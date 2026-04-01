<template>
  <KnowledgeSheetShell
    :open="isOpen"
    title="Настройки таблицы"
    :subtitle="initialName"
    :loading="saving"
    :submit-disabled="!name.trim()"
    submit-text="Сохранить"
    size="lg"
    @close="handleClose"
    @cancel="handleClose"
    @submit="handleSave"
  >
    <div class="space-y-6 p-6">
      <div>
        <label class="text-sm font-medium text-slate-700">Название <span class="text-red-500">*</span></label>
        <input
          v-model.trim="name"
          type="text"
          class="mt-1.5 w-full rounded-md border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm text-slate-900 outline-none ring-0 transition-colors duration-200 focus:border-slate-400 focus:bg-white focus:ring-0 focus-visible:outline-none focus-visible:ring-0 selection:bg-slate-200/50"
        />
      </div>
      <div>
        <label class="text-sm font-medium text-slate-700">Описание</label>
        <textarea
          v-model.trim="description"
          rows="2"
          class="mt-1.5 w-full resize-none rounded-md border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm text-slate-900 outline-none ring-0 transition-colors duration-200 focus:border-slate-400 focus:bg-white focus:ring-0 focus-visible:outline-none focus-visible:ring-0 selection:bg-slate-200/50"
        />
      </div>

      <div class="rounded-2xl bg-slate-50/80 p-4 sm:p-5">
        <p class="text-sm font-medium text-slate-700">Колонки</p>
        <p class="mb-3 mt-1 text-xs leading-relaxed text-slate-500">
          У пользовательских колонок можно менять подпись, код (slug), тип и опции. Системные поля «ID» и «Дата создания» не редактируются. Новые колонки — кнопкой ниже. Порядок — перетаскиванием за иконку слева. Смена кода переносит данные в записях; смена типа может потребовать привести значения к новому формату.
        </p>
        <TableAttributesEditor v-model="attributes" :max-attributes="95" />
      </div>

      <p v-if="submitError" class="text-sm text-red-600">{{ submitError }}</p>
    </div>
  </KnowledgeSheetShell>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import KnowledgeSheetShell from './KnowledgeSheetShell.vue'
import TableAttributesEditor from './TableAttributesEditor.vue'
import type { TableAttribute, TableAttributeType, TableRead } from '~/types/tables'

const SYSTEM = new Set(['id', 'created_at'])

const props = defineProps<{
  isOpen: boolean
  table: TableRead | null
  tablesApi: {
    updateTable: (id: string, p: { name?: string; description?: string | null }) => Promise<TableRead>
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
      }
    ) => Promise<TableAttribute>
    updateAttribute: (
      tableId: string,
      attributeId: string,
      body: Record<string, unknown>
    ) => Promise<unknown>
    deleteAttribute: (tableId: string, attributeId: string) => Promise<void>
    reorderAttributes: (tableId: string, attributeIds: string[]) => Promise<void>
  }
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'saved'): void
}>()

type Draft = {
  id: string
  name: string
  label: string
  attribute_type: TableAttributeType
  type_config: Record<string, unknown>
  is_required: boolean
  is_searchable: boolean
  is_unique: boolean
  is_system?: boolean
}

const initialName = computed(() => props.table?.name ?? '')

const name = ref('')
const description = ref('')
const attributes = ref<Draft[]>([])
const initialSnapshot = ref<TableRead | null>(null)
const saving = ref(false)
const submitError = ref('')

function isUuid(s: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(s)
}

function attrsToDraft(attrs: TableAttribute[]): Draft[] {
  return [...attrs]
    .sort((a, b) => a.order_index - b.order_index)
    .map((a) => ({
      id: a.id,
      name: a.name,
      label: a.label,
      attribute_type: a.attribute_type as TableAttributeType,
      type_config: { ...(a.type_config || {}) },
      is_required: a.is_required,
      is_searchable: a.is_searchable,
      is_unique: a.is_unique,
      is_system: SYSTEM.has(a.name),
    }))
}

function syncFromTable(t: TableRead | null) {
  if (!t) {
    name.value = ''
    description.value = ''
    attributes.value = []
    initialSnapshot.value = null
    return
  }
  initialSnapshot.value = JSON.parse(JSON.stringify(t)) as TableRead
  name.value = t.name
  description.value = t.description ?? ''
  attributes.value = attrsToDraft(t.attributes)
}

watch(
  () => [props.isOpen, props.table] as const,
  ([open, t]) => {
    if (open && t) {
      syncFromTable(t)
      submitError.value = ''
    }
  },
  { immediate: true }
)

const handleClose = () => {
  emit('close')
}

const patchAttrDiff = (cur: Draft, ini: TableAttribute): Record<string, unknown> | null => {
  const patch: Record<string, unknown> = {}
  if (cur.label !== ini.label) patch.label = cur.label
  if (cur.name !== ini.name) patch.name = cur.name
  if (cur.attribute_type !== ini.attribute_type) patch.attribute_type = cur.attribute_type
  const ctc = JSON.stringify(cur.type_config || {})
  const itc = JSON.stringify(ini.type_config || {})
  if (ctc !== itc) patch.type_config = cur.type_config || {}
  if (cur.is_required !== ini.is_required) patch.is_required = cur.is_required
  if (cur.is_searchable !== ini.is_searchable) patch.is_searchable = cur.is_searchable
  if (cur.is_unique !== ini.is_unique) patch.is_unique = cur.is_unique
  return Object.keys(patch).length ? patch : null
}

const handleSave = async () => {
  const t = props.table
  const initial = initialSnapshot.value
  if (!t || !initial) return
  if (!name.value.trim()) {
    submitError.value = 'Введите название'
    return
  }
  saving.value = true
  submitError.value = ''
  try {
    if (
      name.value.trim() !== initial.name ||
      (description.value.trim() || null) !== (initial.description ?? null)
    ) {
      await props.tablesApi.updateTable(t.id, {
        name: name.value.trim(),
        description: description.value.trim() || null,
      })
    }

    const initialById = new Map(initial.attributes.map((a) => [a.id, a]))
    const currentIds = new Set(attributes.value.map((a) => a.id))

    for (const ia of initial.attributes) {
      if (SYSTEM.has(ia.name)) continue
      if (!currentIds.has(ia.id)) {
        await props.tablesApi.deleteAttribute(t.id, ia.id)
      }
    }

    const shortIdToUuid = new Map<string, string>()

    for (const a of attributes.value) {
      if (SYSTEM.has(a.name)) continue
      if (!isUuid(a.id)) {
        const created = await props.tablesApi.createAttribute(t.id, {
          name: a.name,
          label: a.label,
          attribute_type: a.attribute_type,
          type_config: a.type_config || {},
          is_required: a.is_required,
          is_searchable: a.is_searchable,
          is_unique: a.is_unique,
          order_index: 0,
        })
        shortIdToUuid.set(a.id, created.id)
      }
    }

    for (const a of attributes.value) {
      if (SYSTEM.has(a.name)) continue
      if (!isUuid(a.id)) continue
      const ini = initialById.get(a.id)
      if (!ini) continue
      const patch = patchAttrDiff(a, ini)
      if (patch) {
        await props.tablesApi.updateAttribute(t.id, a.id, patch)
      }
    }

    const orderedIds: string[] = []
    for (const a of attributes.value) {
      if (isUuid(a.id)) {
        orderedIds.push(a.id)
      } else if (shortIdToUuid.has(a.id)) {
        orderedIds.push(shortIdToUuid.get(a.id)!)
      }
    }
    if (orderedIds.length > 0) {
      await props.tablesApi.reorderAttributes(t.id, orderedIds)
    }

    emit('saved')
    emit('close')
  } catch (e: any) {
    submitError.value = e?.message ?? 'Не удалось сохранить'
  } finally {
    saving.value = false
  }
}
</script>
