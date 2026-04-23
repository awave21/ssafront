<template>
  <div class="space-y-2">
    <div class="flex items-center justify-between">
      <div>
        <span class="insp-label">Источники данных (подключённые функции агента)</span>
        <p class="mt-0.5 text-[9px] text-muted-foreground">
          Показываются только <strong>пользовательские функции</strong> из вкладки «Функции»
          со статусом <strong>Активна</strong>.
        </p>
      </div>
      <button
        v-if="agentFunctions.length"
        type="button"
        class="flex shrink-0 items-center gap-1 rounded border border-dashed border-border px-2 py-0.5 text-[11px] text-indigo-600 hover:border-indigo-400 hover:bg-indigo-50 transition-colors"
        @click="showPicker = !showPicker"
      >
        <Plus class="size-3" />
        Привязать
      </button>
      <span v-else class="shrink-0 text-[10px] text-muted-foreground">Нет активных инструментов</span>
    </div>

    <!-- Picker dropdown -->
    <div
      v-if="showPicker"
      class="rounded-xl border border-border/80 bg-background/95 shadow-lg"
    >
      <div class="border-b border-border px-3 py-2">
        <p class="text-[11px] font-semibold text-foreground">Выберите функцию</p>
        <p class="text-[10px] text-muted-foreground">
          Выбирайте из пользовательских функций агента (активные привязки). Добавит переменную
          <code>&#123;&#123;имя&#125;&#125;</code> и вставит в активное поле ноды — в скомпилированном тексте будет явная подсказка вызвать этот инструмент.
        </p>
      </div>
      <div class="max-h-52 overflow-y-auto divide-y divide-border">
        <button
          v-for="fn in agentFunctions"
          :key="fn.id!"
          type="button"
          class="flex w-full flex-col gap-0.5 px-3 py-2.5 text-left transition-colors hover:bg-muted/50"
          @click="openAddForm(fn)"
        >
          <span class="text-[12px] font-semibold text-foreground">{{ fn.name }}</span>
          <span v-if="fn.description" class="line-clamp-1 text-[10px] text-muted-foreground">{{ fn.description }}</span>
        </button>
      </div>
    </div>

    <!-- Add form (after picking a function) -->
    <div
      v-if="addingFor"
      class="space-y-2 rounded-xl border border-indigo-200/80 bg-indigo-50/50 p-3 shadow-sm dark:bg-indigo-950/20"
    >
      <p class="text-[11px] font-semibold text-foreground">
        Функция: <span class="text-indigo-700">{{ addingFor.name }}</span>
      </p>
      <div class="space-y-1">
        <label class="insp-label">Что возвращает (argument_hint)</label>
        <input
          v-model="draftHint"
          type="text"
          class="insp-input"
          placeholder="напр. «название услуги + цена»"
          @keydown.enter.prevent="confirmAdd"
        />
      </div>
      <div class="space-y-1">
        <label class="insp-label">Инструкция для модели (опц.)</label>
        <textarea
          v-model="draftInstruction"
          rows="2"
          class="insp-input resize-none"
          placeholder="напр. «Вызови функцию, чтобы узнать актуальную цену перед ответом»"
        />
      </div>
      <div class="flex gap-2">
        <button
          type="button"
          class="flex-1 rounded-md bg-indigo-600 px-3 py-1.5 text-[11px] font-semibold text-white hover:bg-indigo-700 disabled:opacity-40"
          :disabled="!draftHint.trim()"
          @click="confirmAdd"
        >
          Добавить переменную
        </button>
        <button
          type="button"
          class="rounded-md border border-border px-3 py-1.5 text-[11px] text-muted-foreground hover:bg-muted"
          @click="cancelAdd"
        >
          Отмена
        </button>
      </div>
    </div>

    <!-- Existing function variables list -->
    <template v-if="functionEntries.length">
      <div
        v-for="entry in functionEntries"
        :key="entry.name"
        class="group rounded-xl border border-border/80 bg-background/95 p-3 space-y-1.5 shadow-sm"
      >
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0">
            <code class="text-[11px] font-mono text-indigo-700 bg-indigo-50 px-1 rounded">
              &#123;&#123;{{ entry.name }}&#125;&#125;
            </code>
            <span class="ml-1.5 text-[10px] text-muted-foreground">
              → {{ fnName(entry.binding) }}
            </span>
          </div>
          <div class="flex shrink-0 items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              type="button"
              class="rounded p-0.5 text-[11px] text-indigo-600 hover:bg-indigo-50"
              title="Вставить в активное поле"
              @click="insertVar(entry.name)"
            >
              <CornerDownLeft class="size-3" />
            </button>
            <button
              type="button"
              class="rounded p-0.5 text-destructive hover:bg-destructive/10"
              title="Удалить переменную"
              @click="removeVariable(entry.name)"
            >
              <X class="size-3" />
            </button>
          </div>
        </div>

        <!-- hint + instruction (editable inline) -->
        <input
          :value="(entry.binding as FunctionBinding).argument_hint"
          type="text"
          class="insp-input text-[11px]"
          placeholder="Что возвращает функция…"
          @change="updateFunctionVariable(entry.name, { argument_hint: ($event.target as HTMLInputElement).value })"
        />
        <textarea
          :value="(entry.binding as FunctionBinding).llm_instruction ?? ''"
          rows="2"
          class="insp-input resize-none text-[11px]"
          placeholder="Инструкция для модели (опц.)…"
          @change="updateFunctionVariable(entry.name, { llm_instruction: ($event.target as HTMLTextAreaElement).value })"
        />
      </div>
    </template>
    <p v-else-if="!agentFunctions.length" class="text-[10px] italic text-muted-foreground">
      Не найдено активных пользовательских функций. Добавьте их на вкладке «Функции» и включите статус «Активна».
    </p>
    <p v-else class="text-[10px] text-muted-foreground">
      Привяжите функцию — модель будет вызывать её в нужный момент и подставлять актуальные данные.
    </p>
  </div>
</template>

<script setup lang="ts">
import { inject, ref, type Ref } from 'vue'
import { Plus, X, CornerDownLeft } from 'lucide-vue-next'
import { useFlowVariables } from '~/composables/useFlowVariables'
import { SCRIPT_FLOW_INSPECTOR_KEY } from '~/composables/useScriptFlowInspectorModel'
import type { VariableBinding } from '~/types/scriptFlow'
import type { Tool } from '~/types/tool'

type FunctionBinding = Extract<VariableBinding, { source_type: 'function' }>

const flowAgentFunctions = inject<Ref<Tool[]>>('flowAgentFunctions', ref([]))
const flowVariables = inject<Ref<Record<string, VariableBinding> | undefined>>('flowVariables', ref(undefined))
const onFlowVariablesUpdate = inject<(v: Record<string, VariableBinding>) => void>('onFlowVariablesUpdate', () => {})

const { insertVar } = inject(SCRIPT_FLOW_INSPECTOR_KEY)!

const { functionEntries, addFunctionVariable, updateFunctionVariable, removeVariable } = useFlowVariables(
  flowVariables,
  onFlowVariablesUpdate,
)

const agentFunctions = flowAgentFunctions

const showPicker = ref(false)
const addingFor = ref<Tool | null>(null)
const draftHint = ref('')
const draftInstruction = ref('')

const openAddForm = (fn: Tool) => {
  addingFor.value = fn
  draftHint.value = ''
  draftInstruction.value = ''
  showPicker.value = false
}

const cancelAdd = () => {
  addingFor.value = null
}

const confirmAdd = () => {
  if (!addingFor.value || !draftHint.value.trim()) return
  addFunctionVariable(
    {
      functionId: addingFor.value.id!,
      functionName: addingFor.value.name,
      argumentHint: draftHint.value.trim(),
      llmInstruction: draftInstruction.value.trim() || undefined,
    },
    insertVar,
  )
  addingFor.value = null
}

const fnName = (binding: VariableBinding): string => {
  if (binding.source_type !== 'function') return ''
  const fn = agentFunctions.value.find(f => f.id === (binding as FunctionBinding).function_id)
  return fn ? fn.name : (binding as FunctionBinding).function_id
}
</script>
