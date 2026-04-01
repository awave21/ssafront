<template>
  <KnowledgeSheetShell
    :open="isOpen"
    title="Добавить таблицу"
    subtitle="Создайте структуру таблицы и атрибуты."
    :loading="isSubmitting"
    :submit-disabled="isSubmitDisabled"
    submit-text="Создать таблицу"
    size="lg"
    @close="$emit('close')"
    @cancel="$emit('close')"
    @submit="handleSubmit"
  >
    <div class="space-y-6 p-6">
      <div>
        <label class="text-sm font-medium text-slate-700">Название таблицы <span class="text-red-500">*</span></label>
        <input
          v-model.trim="name"
          type="text"
          placeholder="Клиенты"
          class="mt-1.5 w-full rounded-md border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm text-slate-900 outline-none ring-0 transition-colors duration-200 focus:border-slate-400 focus:bg-white focus:ring-0 focus-visible:outline-none focus-visible:ring-0 selection:bg-slate-200/50"
        />
      </div>
      <div>
        <label class="text-sm font-medium text-slate-700">Описание</label>
        <textarea
          v-model.trim="description"
          rows="2"
          placeholder="Таблица контактов клиентов и статусов"
          class="mt-1.5 w-full resize-none rounded-md border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm text-slate-900 outline-none ring-0 transition-colors duration-200 focus:border-slate-400 focus:bg-white focus:ring-0 focus-visible:outline-none focus-visible:ring-0 selection:bg-slate-200/50"
        />
      </div>

      <div class="rounded-2xl bg-slate-50/80 p-4 sm:p-5">
        <p class="text-sm font-medium text-slate-700">Колонки</p>
        <p class="mb-3 mt-1 text-xs text-slate-500">
          Порядок колонок можно задать перетаскиванием за иконку слева — он сохранится при создании таблицы.
        </p>
        <TableAttributesEditor v-model="attributes" :max-attributes="25" />
      </div>

      <p v-if="submitError" class="text-sm text-red-600">{{ submitError }}</p>
    </div>
  </KnowledgeSheetShell>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import KnowledgeSheetShell from './KnowledgeSheetShell.vue'
import TableAttributesEditor from './TableAttributesEditor.vue'
import type { TableAttributeType } from '~/types/tables'

const props = defineProps<{
  isOpen: boolean
}>()

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'submit', payload: {
    name: string
    description?: string
    attributes: Array<{
      name: string
      label: string
      attribute_type: TableAttributeType
      type_config: Record<string, unknown>
      is_required: boolean
      is_searchable: boolean
      is_unique: boolean
    }>
  }): void
}>()

const name = ref('')
const description = ref('')
const attributes = ref<Array<{
  id: string
  name: string
  label: string
  attribute_type: TableAttributeType
  type_config: Record<string, unknown>
  is_required: boolean
  is_searchable: boolean
  is_unique: boolean
  is_system?: boolean
}>>([
  {
    id: 'system_id',
    name: 'id',
    label: 'ID',
    attribute_type: 'integer',
    type_config: {},
    is_required: true,
    is_searchable: false,
    is_unique: true,
    is_system: true,
  },
  {
    id: 'system_created_at',
    name: 'created_at',
    label: 'Дата создания',
    attribute_type: 'timestamp',
    type_config: {},
    is_required: true,
    is_searchable: false,
    is_unique: false,
    is_system: true,
  },
])
const isSubmitting = ref(false)
const submitError = ref('')

const isSubmitDisabled = computed(() => isSubmitting.value || !name.value.trim() || attributes.value.length === 0)

watch(
  () => props.isOpen,
  (open) => {
    if (!open) {
      name.value = ''
      description.value = ''
      submitError.value = ''
      isSubmitting.value = false
      attributes.value = [{
        id: 'system_id',
        name: 'id',
        label: 'ID',
        attribute_type: 'integer',
        type_config: {},
        is_required: true,
        is_searchable: false,
        is_unique: true,
        is_system: true,
      },
      {
        id: 'system_created_at',
        name: 'created_at',
        label: 'Дата создания',
        attribute_type: 'timestamp',
        type_config: {},
        is_required: true,
        is_searchable: false,
        is_unique: false,
        is_system: true,
      }]
    }
  }
)

const handleSubmit = async () => {
  submitError.value = ''
  if (!name.value.trim()) {
    submitError.value = 'Введите название таблицы'
    return
  }
  if (attributes.value.length === 0) {
    submitError.value = 'Добавьте хотя бы один атрибут'
    return
  }
  const hasInvalid = attributes.value.some((item) => !item.name.trim() || !item.label.trim())
  if (hasInvalid) {
    submitError.value = 'Заполните название и код для каждого атрибута'
    return
  }
  isSubmitting.value = true
  emit('submit', {
    name: name.value.trim(),
    description: description.value.trim() || undefined,
    attributes: attributes.value.map(({ id: _id, is_system: _isSystem, name, label, attribute_type, type_config, is_required, is_unique }) => ({
      name,
      label,
      attribute_type,
      type_config,
      is_required,
      is_searchable: true,
      is_unique,
    })),
  })
}

const setSubmitting = (value: boolean) => {
  isSubmitting.value = value
}

const setError = (message: string) => {
  submitError.value = message
}

defineExpose({
  setSubmitting,
  setError,
})
</script>

