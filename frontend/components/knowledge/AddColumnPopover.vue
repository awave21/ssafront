<template>
  <Popover v-model:open="isOpen">
    <PopoverTrigger as-child>
      <TableHead class-name="w-40">
        <div class="flex justify-center">
          <button
            class="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
            title="Добавить столбец"
          >
            <Plus class="w-3.5 h-3.5" />
            Столбец
          </button>
        </div>
      </TableHead>
    </PopoverTrigger>
    <PopoverContent class="w-80" align="end">
      <div class="space-y-4">
        <div>
          <h4 class="font-medium text-sm text-slate-900 mb-2">Новый столбец</h4>
          <p class="text-xs text-slate-500">Добавьте столбец в справочник</p>
        </div>
        
        <div class="space-y-3">
          <div>
            <label class="text-xs font-medium text-slate-700 mb-1 block">Название</label>
            <input
              ref="labelInputRef"
              v-model="newColumn.label"
              type="text"
              placeholder="Цена"
              class="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 transition-all"
              @input="generateName"
              @keydown.enter="submit"
              @keydown.escape="cancel"
            />
          </div>

          <div>
            <label class="text-xs font-medium text-slate-700 mb-1 block">Код (slug)</label>
            <input
              v-model="newColumn.name"
              type="text"
              placeholder="price"
              pattern="^[a-z][a-z0-9_]*$"
              class="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white font-mono focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 transition-all"
              :class="{ 'border-red-300 bg-red-50': isDuplicate }"
            />
            <p v-if="isDuplicate" class="mt-1 text-xs text-red-600">
              Столбец с таким именем уже существует
            </p>
          </div>

          <div>
            <label class="text-xs font-medium text-slate-700 mb-1 block">Тип данных</label>
            <select
              v-model="newColumn.type"
              class="w-full px-3 py-2 text-sm border border-slate-200 rounded-lg bg-white focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 transition-all"
            >
              <option value="text">Текст</option>
              <option value="number">Число</option>
              <option value="date">Дата</option>
              <option value="bool">Да/Нет</option>
            </select>
          </div>

          <div class="flex items-center gap-4 pt-1">
            <label class="flex items-center gap-2 cursor-pointer">
              <input
                v-model="newColumn.required"
                type="checkbox"
                class="w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
              />
              <span class="text-xs text-slate-700">Обязательное</span>
            </label>
            <label class="flex items-center gap-2 cursor-pointer">
              <input
                v-model="newColumn.searchable"
                type="checkbox"
                class="w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
              />
              <span class="text-xs text-slate-700">Поиск</span>
            </label>
          </div>
        </div>

        <div class="flex gap-2 pt-2">
          <button
            @click="submit"
            :disabled="!newColumn.label || !newColumn.name || isDuplicate"
            class="flex-1 px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Добавить
          </button>
          <button
            @click="cancel"
            class="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
          >
            Отмена
          </button>
        </div>
      </div>
    </PopoverContent>
  </Popover>
</template>

<script setup lang="ts">
import { ref, computed, watch, nextTick } from 'vue'
import { Plus } from 'lucide-vue-next'
import type { DirectoryColumn } from '~/types/directories'
import { TableHead } from '~/components/ui/table'
import { Popover, PopoverContent, PopoverTrigger } from '~/components/ui/popover'
import { transliterate } from '~/utils/translit'

const props = defineProps<{
  existingColumns: DirectoryColumn[]
}>()

const emit = defineEmits<{
  (e: 'add', column: DirectoryColumn & { searchable: boolean }): void
}>()

const isOpen = ref(false)
const labelInputRef = ref<HTMLInputElement | null>(null)
const newColumn = ref({
  label: '',
  name: '',
  type: 'text',
  required: false,
  searchable: false
})

const isDuplicate = computed(() => {
  if (!newColumn.value.name) return false
  return props.existingColumns.some(c => c.name === newColumn.value.name)
})

const generateName = () => {
  if (!newColumn.value.label) {
    newColumn.value.name = ''
    return
  }
  newColumn.value.name = transliterate(newColumn.value.label)
}

const submit = () => {
  if (!newColumn.value.label || !newColumn.value.name || isDuplicate.value) return

  emit('add', {
    name: newColumn.value.name,
    label: newColumn.value.label,
    type: newColumn.value.type,
    required: newColumn.value.required,
    searchable: newColumn.value.searchable
  })

  cancel()
}

const cancel = () => {
  isOpen.value = false
  newColumn.value = {
    label: '',
    name: '',
    type: 'text',
    required: false,
    searchable: false
  }
}

watch(isOpen, (val) => {
  if (val) {
    nextTick(() => labelInputRef.value?.focus())
  }
})
</script>
