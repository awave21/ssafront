<template>
  <div class="script-flow-inspector-panel flex h-full min-h-0 flex-col bg-background text-left">
    <div
      v-if="!nodeId"
      class="flex flex-1 flex-col items-center justify-center gap-2 p-6 text-center text-sm text-muted-foreground"
    >
      <p class="font-medium text-foreground">Шаг разговора не выбран</p>
      <p class="max-w-[260px] text-xs leading-relaxed">
        Выберите карточку на карте разговора. Справа откроется <strong class="text-foreground">редактор этого шага</strong>.
      </p>
    </div>

    <template v-else>
      <!-- Цвет типа + название шага -->
      <div class="shrink-0 flex items-stretch gap-0 border-b border-border">
        <div
          class="w-1 shrink-0 rounded-tl-sm"
          :style="{ background: headerAccent }"
        />
        <div class="min-w-0 flex-1 py-2.5 pl-2 pr-2">
          <div class="flex items-center gap-2">
            <p class="text-xs font-semibold leading-tight text-foreground truncate">
              {{ headerTitle }}
            </p>
            <span
              v-if="kgLinkTotal > 0"
              class="inline-flex shrink-0 items-center rounded-full border border-indigo-200 bg-indigo-50 px-1.5 py-0.5 text-[9px] font-semibold text-indigo-700 tabular-nums"
              :title="`Связано с ${kgLinkTotal} материалами из библиотеки знаний`"
            >
              Связи&nbsp;{{ kgLinkTotal }}
            </span>
            <span
              v-else-if="kgHintRelevant"
              class="inline-flex shrink-0 items-center rounded-full border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[9px] font-semibold text-amber-700"
              title="Добавьте связи с библиотекой: мотив, аргумент, типичное возражение"
            >
              без связей
            </span>
          </div>
          <p class="mt-0.5 text-[10px] text-muted-foreground truncate" :title="nodeId ?? ''">
            Внутренний ID: {{ nodeId }}
          </p>
        </div>
        <button
          type="button"
          class="shrink-0 self-start m-2 rounded-md border border-border px-2 py-1 text-[10px] hover:bg-muted"
          @click="$emit('clear')"
        >
          ✕
        </button>
      </div>

      <div class="shrink-0 space-y-2.5 border-b border-border px-4 py-3">
        <div class="rounded-xl border border-indigo-200/70 bg-indigo-50/60 px-3 py-2.5 shadow-sm dark:bg-indigo-950/10">
          <p class="text-[11px] font-semibold text-foreground">Редактор шага разговора</p>
          <p class="mt-1 text-[10px] leading-relaxed text-muted-foreground">
            Сначала дайте шагу понятное название, потом заполните смысл справа ниже: когда он нужен,
            что здесь говорить или спрашивать, и куда разговор должен пойти дальше.
          </p>
        </div>
        <div class="space-y-1">
          <label class="insp-label">Как называется этот шаг</label>
          <input
            v-model="localTitle"
            type="text"
            class="insp-input"
            placeholder="Короткое понятное название для карты"
            @input="flushNode"
            @focus="clearLastFocused"
          >
        </div>
      </div>

      <div class="min-h-0 flex-1 overflow-y-auto">
        <div
          v-if="flowVarNames.length"
          class="mx-4 mt-4 rounded-xl border border-dashed border-violet-300/60 bg-violet-50/60 px-3 py-2.5 dark:bg-violet-950/10"
        >
          <p class="text-[9px] font-bold uppercase tracking-wider text-violet-500 mb-1.5">Переменные сценария</p>
          <div class="flex flex-wrap gap-1">
            <button
              v-for="varName in flowVarNames"
              :key="varName"
              type="button"
              class="rounded-md bg-violet-100 px-2 py-0.5 text-[10px] font-mono text-violet-700 dark:bg-violet-800/40 dark:text-violet-300"
              @click="insertVar(varName)"
            >
              {{ '{' + '{' + varName + '}' + '}' }}
            </button>
          </div>
        </div>

        <component :is="activePanel" v-bind="panelExtraProps" />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, provide, ref, toRef, type Component, type Ref } from 'vue'
import {
  SCRIPT_FLOW_INSPECTOR_KEY,
  useScriptFlowInspectorModel,
} from '~/composables/useScriptFlowInspectorModel'
import { NODE_TYPES, NODE_TYPE_COLORS, type NodeType } from '~/types/scriptFlow'
import TacticInspectorPanel from './inspectors/TacticInspectorPanel.vue'
import QuestionInspectorPanel from './inspectors/QuestionInspectorPanel.vue'
import BusinessRuleNodePanel from './inspectors/BusinessRuleNodePanel.vue'

const props = defineProps<{
  nodeId: string | null
}>()

const emit = defineEmits<{
  clear: []
}>()

const nodeIdRef = toRef(props, 'nodeId')

const model = useScriptFlowInspectorModel(nodeIdRef)
provide(SCRIPT_FLOW_INSPECTOR_KEY, model)

const {
  localTitle,
  localNodeType,
  lastFocusedField,
  flushNode,
  insertVar,
  localMotiveIds,
  localArgumentIds,
  localProofIds,
  localObjectionIds,
  localConstraintIds,
  localOutcomeId,
} = model

const kgLinkTotal = computed(() =>
  localMotiveIds.value.length
  + localArgumentIds.value.length
  + localProofIds.value.length
  + localObjectionIds.value.length
  + localConstraintIds.value.length
  + (localOutcomeId.value ? 1 : 0),
)

const kgHintRelevant = computed(() =>
  ['expertise', 'question', 'end', 'business_rule'].includes(localNodeType.value),
)

const flowVarNames = inject<Ref<string[]>>('flowVarNames', ref([]))

const PANEL_BY_TYPE: Partial<Record<NodeType, Component>> = {
  trigger: TacticInspectorPanel,
  expertise: TacticInspectorPanel,
  question: QuestionInspectorPanel,
  condition: QuestionInspectorPanel,
  goto: TacticInspectorPanel,
  business_rule: BusinessRuleNodePanel,
  end: TacticInspectorPanel,
}

const activePanel = computed(() => {
  const t = localNodeType.value as NodeType
  return PANEL_BY_TYPE[t] ?? TacticInspectorPanel
})

const headerAccent = computed(() => NODE_TYPE_COLORS[localNodeType.value] || '#6366f1')

const headerTitle = computed(() => {
  const meta = NODE_TYPES.find((x) => x.value === localNodeType.value)
  return meta?.label ?? localNodeType.value
})

const panelExtraProps = computed(() => {
  if (localNodeType.value === 'business_rule')
    return { nodeId: props.nodeId }
  return {}
})

const clearLastFocused = () => {
  lastFocusedField.value = ''
}
</script>

<style src="./inspectors/inspector-panel.css"></style>
