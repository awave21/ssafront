<template>
  <TooltipProvider :delay-duration="250">
    <div class="space-y-3">
    <div v-if="attributes.length > 0" class="overflow-hidden rounded-xl bg-slate-50/60">
      <div
        class="grid grid-cols-[36px_1fr_1fr_minmax(11.5rem,1.25fr)_72px_72px_56px] gap-0 border-b border-slate-200 bg-slate-50/90 px-2 py-2 text-xs font-medium text-slate-500"
      >
        <div class="flex items-center justify-center" aria-hidden="true" />
        <div class="px-2">Название</div>
        <div class="px-2">Код</div>
        <div class="flex items-center gap-1 px-2">
          <span>Тип</span>
          <Tooltip>
            <TooltipTrigger as-child>
              <button
                type="button"
                class="shrink-0 rounded-md p-0.5 text-slate-400 outline-none transition-colors hover:bg-slate-200/80 hover:text-slate-600 focus-visible:ring-2 focus-visible:ring-indigo-500/30"
                aria-label="Справка по типам данных"
                @click.prevent
              >
                <HelpCircle class="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="bottom" class="max-w-sm border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 shadow-lg">
              <p class="font-medium text-slate-900">Типы колонок</p>
              <p class="mt-1.5 leading-relaxed text-slate-600">
                Краткие обозначения в списке; ниже — соответствие типу в PostgreSQL и пояснение.
              </p>
              <ul class="mt-2 max-h-48 space-y-1.5 overflow-y-auto border-t border-slate-100 pt-2 text-[11px] leading-snug text-slate-600">
                <li v-for="opt in TABLE_ATTRIBUTE_TYPE_METAS" :key="opt.value">
                  <span class="font-medium text-slate-800">{{ opt.label }}</span>
                  <span class="font-mono text-slate-500"> · {{ opt.syntax }}</span>
                  — {{ opt.hint }}
                </li>
              </ul>
            </TooltipContent>
          </Tooltip>
        </div>
        <div class="text-center">Обяз.</div>
        <div class="text-center">Уник.</div>
        <div />
      </div>

      <Draggable
        v-model="attributes"
        item-key="id"
        handle=".table-attr-drag-handle"
        tag="div"
        class="divide-y divide-slate-100/80"
        ghost-class="opacity-50"
        chosen-class="z-10"
        drag-class="opacity-90"
        :animation="180"
        @end="onDragEnd"
      >
        <template #item="{ element: attr, index }">
          <div
            class="transition-colors duration-150"
            :class="
              isSystemAttribute(attr)
                ? 'bg-slate-200/55 text-slate-600 dark:bg-slate-800/40 dark:text-slate-400'
                : 'hover:bg-slate-100/50'
            "
          >
            <div class="grid grid-cols-[36px_1fr_1fr_minmax(11.5rem,1.25fr)_72px_72px_56px] items-center gap-0 px-2 py-1.5">
              <div class="flex items-center justify-center">
                <button
                  type="button"
                  class="table-attr-drag-handle shrink-0 cursor-grab touch-none rounded-lg p-1.5 text-slate-400 outline-none ring-0 transition-colors hover:text-slate-600 focus-visible:outline-none focus-visible:ring-0 active:cursor-grabbing"
                  :class="isSystemAttribute(attr) ? 'text-slate-500 hover:text-slate-600' : ''"
                  aria-label="Перетащить колонку"
                  title="Перетащить"
                  @click.stop
                >
                  <GripVertical class="h-4 w-4" />
                </button>
              </div>
          <div class="px-1">
            <input
              v-model="attr.label"
              type="text"
              placeholder="Название"
              class="w-full rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-sm outline-none ring-0 transition-colors focus:border-slate-400 focus:ring-0 focus-visible:outline-none focus-visible:ring-0 selection:bg-slate-200/50 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-600 dark:disabled:bg-slate-900/50 dark:disabled:text-slate-400"
              :disabled="isSystemAttribute(attr)"
              @input="generateName(attr); emitUpdate()"
            />
          </div>
          <div class="px-1">
            <input
              v-model="attr.name"
              type="text"
              placeholder="slug"
              class="w-full rounded-md border border-slate-200 bg-white px-2.5 py-1.5 font-mono text-sm outline-none ring-0 transition-colors focus:border-slate-400 focus:ring-0 focus-visible:outline-none focus-visible:ring-0 selection:bg-slate-200/50 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-600 dark:disabled:bg-slate-900/50 dark:disabled:text-slate-400"
              :disabled="isSystemAttribute(attr)"
              @input="emitUpdate"
            />
          </div>
          <div class="min-w-0 px-1">
            <select
              v-model="attr.attribute_type"
              class="w-full min-w-0 cursor-pointer appearance-none rounded-md border border-slate-200 bg-white px-2 py-1.5 text-xs outline-none ring-0 transition-colors focus:border-slate-400 focus:ring-0 focus-visible:outline-none focus-visible:ring-0 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-600 dark:disabled:bg-slate-900/50 dark:disabled:text-slate-400 sm:text-sm"
              :disabled="isSystemAttribute(attr)"
              @change="handleTypeChange(attr); emitUpdate()"
            >
              <option
                v-for="opt in TABLE_ATTRIBUTE_TYPE_METAS"
                :key="opt.value"
                :value="opt.value"
              >
                {{ tableAttributeTypeSelectLabel(opt) }}
              </option>
            </select>
          </div>
          <div class="flex justify-center">
            <input v-model="attr.is_required" type="checkbox" class="h-4 w-4 cursor-pointer rounded border-slate-300 text-indigo-600 focus:ring-0 focus:ring-offset-0" :disabled="isSystemAttribute(attr)" @change="emitUpdate" />
          </div>
          <div class="flex justify-center">
            <input v-model="attr.is_unique" type="checkbox" class="h-4 w-4 cursor-pointer rounded border-slate-300 text-indigo-600 focus:ring-0 focus:ring-offset-0" :disabled="isSystemAttribute(attr)" @change="emitUpdate" />
          </div>
              <div class="flex justify-end pr-1">
                <button
                  type="button"
                  class="rounded p-1.5 text-slate-400 outline-none ring-0 transition-colors hover:text-red-600 focus-visible:outline-none focus-visible:ring-0"
                  :disabled="attributes.length <= 1 || isSystemAttribute(attr)"
                  @click="removeAttribute(index)"
                >
                  <X class="h-3.5 w-3.5" />
                </button>
              </div>
            </div>

          </div>
        </template>
      </Draggable>
    </div>

    <button
      type="button"
      class="flex w-full items-center justify-center gap-1.5 rounded-lg border border-dashed border-slate-200 px-3 py-2.5 text-sm font-medium text-slate-500 outline-none ring-0 transition-colors hover:text-slate-700 focus-visible:outline-none focus-visible:ring-0"
      :disabled="attributes.length >= maxAttributes"
      @click="addAttribute"
    >
      <Plus class="h-4 w-4" />
      Добавить атрибут
    </button>
    </div>
  </TooltipProvider>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import Draggable from 'vuedraggable'
import { GripVertical, HelpCircle, Plus, X } from 'lucide-vue-next'
import { transliterate } from '~/utils/translit'
import {
  TABLE_ATTRIBUTE_TYPE_METAS,
  tableAttributeTypeSelectLabel,
} from '~/utils/tableAttributeTypes'
import type { TableAttributeType } from '~/types/tables'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '~/components/ui/tooltip'

type TableAttributeDraft = {
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

const props = defineProps<{
  modelValue: TableAttributeDraft[]
  maxAttributes?: number
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: TableAttributeDraft[]): void
}>()

const maxAttributes = props.maxAttributes ?? 30
const attributes = ref<TableAttributeDraft[]>([])
const isInternalUpdate = ref(false)

const generateId = () => Math.random().toString(36).slice(2, 9)

watch(() => props.modelValue, (value) => {
  if (isInternalUpdate.value) {
    isInternalUpdate.value = false
    return
  }
  attributes.value = (value || []).map((item) => ({ ...item, id: item.id || generateId() }))
}, { immediate: true })

const emitUpdate = () => {
  isInternalUpdate.value = true
  emit('update:modelValue', attributes.value.map(({ id, ...rest }) => ({ ...rest, id })))
}

const onDragEnd = () => {
  emitUpdate()
}

const generateName = (attr: TableAttributeDraft) => {
  if (!attr.label) {
    attr.name = ''
    return
  }
  // Не затираем вручную заданный slug при правке только подписи
  if (!String(attr.name ?? '').trim()) {
    attr.name = transliterate(attr.label)
  }
}

const addAttribute = () => {
  if (attributes.value.length >= maxAttributes) return
  attributes.value.push({
    id: generateId(),
    name: '',
    label: '',
    attribute_type: 'text',
    type_config: {},
    is_required: false,
    is_searchable: true,
    is_unique: false,
    is_system: false,
  })
  emitUpdate()
}

const removeAttribute = (index: number) => {
  if (attributes.value.length <= 1) return
  attributes.value.splice(index, 1)
  emitUpdate()
}

const isSystemAttribute = (attr: TableAttributeDraft) => !!attr.is_system

const handleTypeChange = (_attr: TableAttributeDraft) => {
  // no extra config needed for current types
}
</script>

