<template>
  <div class="space-y-3">
    <!-- Table-like grid -->
    <div v-if="columns.length > 0" class="rounded-lg border border-slate-200 overflow-hidden">
      <!-- Header -->
      <div class="grid grid-cols-[1fr_1fr_120px_52px_52px_68px] gap-0 bg-slate-50 border-b border-slate-200 px-2 py-2 text-xs font-medium text-slate-500">
        <div class="px-2">Название</div>
        <div class="px-2">Код</div>
        <div class="px-2">Тип</div>
        <div class="text-center">Обяз.</div>
        <div class="text-center">Поиск</div>
        <div></div>
      </div>

      <!-- Rows -->
      <draggable
        v-model="columns"
        item-key="id"
        handle=".drag-handle"
        ghost-class="opacity-50"
        @change="emitUpdate"
        tag="div"
      >
        <template #item="{ element: col, index }">
          <div class="border-b border-slate-100 last:border-b-0">
            <div
              class="grid grid-cols-[1fr_1fr_120px_52px_52px_68px] gap-0 items-center px-2 py-1.5 hover:bg-slate-50/50 transition-colors"
            >
              <!-- Label -->
              <div class="px-1">
                <input
                  v-model="col.label"
                  type="text"
                  placeholder="Название"
                  class="w-full px-2.5 py-1.5 text-sm border border-slate-200 rounded-md bg-white focus:bg-white focus:border-indigo-400 focus:ring-1 focus:ring-indigo-100 transition-all"
                  @input="generateName(col); emitUpdate()"
                />
              </div>

              <!-- Slug -->
              <div class="px-1">
                <input
                  v-model="col.name"
                  type="text"
                  placeholder="slug"
                  class="w-full px-2.5 py-1.5 text-sm font-mono border border-slate-200 rounded-md bg-white focus:bg-white focus:border-indigo-400 focus:ring-1 focus:ring-indigo-100 transition-all"
                  :class="{ 'border-red-300 bg-red-50': (col.name && !isValidName(col.name)) || isDuplicateName(col.name, index) }"
                  @input="emitUpdate"
                />
              </div>

              <!-- Type -->
              <div class="px-1">
                <select
                  v-model="col.type"
                  class="w-full px-2 py-1.5 text-sm border border-slate-200 rounded-md bg-white focus:border-indigo-400 focus:ring-1 focus:ring-indigo-100 transition-all appearance-none cursor-pointer"
                  @change="emitUpdate"
                >
                  <option value="text">Текст</option>
                  <option value="number">Число</option>
                  <option value="date">Дата</option>
                  <option value="bool">Да/Нет</option>
                </select>
              </div>

              <!-- Required -->
              <div class="flex items-center justify-center">
                <input
                  v-model="col.required"
                  type="checkbox"
                  class="w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                  @change="emitUpdate"
                />
              </div>

              <!-- Searchable -->
              <div class="flex items-center justify-center">
                <input
                  v-model="col.searchable"
                  type="checkbox"
                  class="w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                  @change="emitUpdate"
                />
              </div>

              <!-- Actions -->
              <div class="flex items-center justify-end gap-0.5 pr-1">
                <button
                  type="button"
                  class="drag-handle p-1.5 text-slate-300 hover:text-slate-500 cursor-grab rounded transition-colors"
                >
                  <GripVertical class="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  @click="removeColumn(index)"
                  class="p-1.5 text-slate-300 hover:text-red-500 hover:bg-red-50 rounded transition-colors"
                  :disabled="columns.length <= 1"
                  :class="{ 'opacity-30 cursor-not-allowed': columns.length <= 1 }"
                >
                  <X class="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            <!-- Validation errors inline -->
            <div
              v-if="(col.name && !isValidName(col.name)) || isDuplicateName(col.name, index)"
              class="px-4 pb-2"
            >
              <p v-if="col.name && !isValidName(col.name)" class="text-[11px] text-red-500">
                Код: только a-z, 0-9, _ начиная с буквы
              </p>
              <p v-if="isDuplicateName(col.name, index)" class="text-[11px] text-red-500">
                Код колонки должен быть уникальным
              </p>
            </div>
          </div>
        </template>
      </draggable>
    </div>

    <!-- Empty state -->
    <div v-else class="text-center py-6 bg-slate-50 rounded-lg border border-dashed border-slate-200">
      <p class="text-sm text-slate-500">Добавьте хотя бы одну колонку</p>
    </div>

    <!-- Add Column -->
    <button
      type="button"
      @click="addColumn"
      class="w-full flex items-center justify-center gap-1.5 px-3 py-2.5 text-sm font-medium text-slate-500 hover:text-indigo-600 border border-dashed border-slate-200 hover:border-indigo-300 hover:bg-indigo-50/50 rounded-lg transition-all"
      :disabled="columns.length >= maxColumns"
      :class="{ 'opacity-50 cursor-not-allowed': columns.length >= maxColumns }"
    >
      <Plus class="w-4 h-4" />
      Добавить колонку
    </button>

    <p v-if="columns.length > 0" class="text-xs text-slate-400 text-center">
      {{ columns.length }} из {{ maxColumns }} колонок
    </p>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Plus, GripVertical, X } from 'lucide-vue-next'
import draggable from 'vuedraggable'
import { transliterate } from '~/utils/translit'
import { isValidSlugName } from '~/utils/directory-helpers'

export type ColumnDefinition = {
  id: string
  name: string
  label: string
  type: string
  required: boolean
  searchable: boolean
}

const props = defineProps<{
  modelValue: ColumnDefinition[]
  maxColumns?: number
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: ColumnDefinition[]): void
}>()

const maxColumns = props.maxColumns || 15

const columns = ref<ColumnDefinition[]>([])
const isInternalUpdate = ref(false)

const generateId = () => Math.random().toString(36).substring(2, 9)

// Инициализация — пропускаем когда обновление пришло от нас самих
watch(() => props.modelValue, (value) => {
  if (isInternalUpdate.value) {
    isInternalUpdate.value = false
    return
  }
  if (value && value.length > 0) {
    columns.value = value.map(col => ({ ...col, id: col.id || generateId() }))
  }
}, { immediate: true })

const generateName = (col: ColumnDefinition) => {
  if (!col.label) {
    col.name = ''
    return
  }
  col.name = transliterate(col.label)
}

const isValidName = (name: string) => isValidSlugName(name)

const isDuplicateName = (name: string, currentIndex: number) => {
  if (!name) return false
  return columns.value.some((col, idx) => idx !== currentIndex && col.name === name)
}

const addColumn = () => {
  if (columns.value.length >= maxColumns) return
  
  columns.value.push({
    id: generateId(),
    name: '',
    label: '',
    type: 'text',
    required: false,
    searchable: false
  })
  emitUpdate()
}

const removeColumn = (index: number) => {
  if (columns.value.length <= 1) return
  columns.value.splice(index, 1)
  emitUpdate()
}

const emitUpdate = () => {
  isInternalUpdate.value = true
  const cleanColumns = columns.value.map(({ id, ...rest }) => rest)
  emit('update:modelValue', cleanColumns as ColumnDefinition[])
}

// Валидация для родителя
const isValid = () => {
  if (columns.value.length === 0) return false
  
  return columns.value.every(col => 
    col.name && 
    col.label && 
    isValidName(col.name) && 
    !isDuplicateName(col.name, columns.value.indexOf(col))
  )
}

defineExpose({ isValid })
</script>

<style scoped>
.ghost {
  opacity: 0.5;
  background: #f1f5f9;
}
</style>
