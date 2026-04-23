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

        <div class="mx-4 mt-4 rounded-xl border border-border bg-background px-4 py-4 shadow-sm">
          <p class="text-[11px] font-semibold text-foreground">Быстрый переход к следующему шагу</p>
          <p class="mt-1 text-[10px] leading-relaxed text-muted-foreground">
            Если уже понятно, что должно идти дальше, выберите следующий шаг здесь. Это самый простой способ собрать карту разговора.
          </p>
          <div class="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center">
            <select v-model="selectedStepToConnect" class="insp-input sm:flex-1">
              <option value="">Выберите следующий шаг…</option>
              <option v-for="opt in availableScenarioStepOptions" :key="opt.id" :value="opt.id">
                {{ opt.title }}
              </option>
            </select>
            <button
              type="button"
              class="rounded-md border border-border px-3 py-2 text-[11px] font-medium hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
              :disabled="!selectedStepToConnect"
              @click="connectSelectedStep"
            >
              Добавить переход
            </button>
          </div>
        </div>

        <div class="mx-4 mt-4 rounded-xl border border-border bg-background px-4 py-4 shadow-sm">
          <div class="flex items-start justify-between gap-3">
            <div>
              <p class="text-[11px] font-semibold text-foreground">Связи этого шага на карте разговора</p>
              <p class="mt-1 text-[10px] leading-relaxed text-muted-foreground">
                Здесь можно быстро понять, что обычно происходит до этого шага и что идёт после него.
                Так проще собирать сценарий как живой разговор, а не как техническую схему.
              </p>
            </div>
            <span
              class="shrink-0 rounded-full border border-border px-2 py-0.5 text-[9px] font-medium text-muted-foreground"
            >
              {{ incomingConnections.length + outgoingConnections.length }} переходов
            </span>
          </div>

          <div v-if="hasScenarioConnections" class="mt-3 grid gap-3 xl:grid-cols-2">
            <div class="space-y-2">
              <p class="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                Что обычно приводит к этому шагу
              </p>
              <div v-if="incomingConnections.length" class="space-y-1.5">
                <div
                  v-for="conn in incomingConnections"
                  :key="`in-${conn.edgeId}`"
                  class="rounded-md border border-border bg-background px-2.5 py-2"
                >
                  <div class="flex items-start justify-between gap-3">
                    <div class="min-w-0">
                      <p class="text-[11px] font-medium text-foreground">{{ conn.title }}</p>
                      <p class="mt-0.5 text-[10px] text-muted-foreground">{{ conn.relationLabel }}</p>
                    </div>
                    <div class="shrink-0 flex flex-col items-end gap-1">
                      <button
                        type="button"
                        class="rounded-md border border-border px-2 py-1 text-[10px] hover:bg-muted"
                        @click="$emit('openNode', conn.nodeId)"
                      >
                        Перейти к шагу
                      </button>
                      <div class="flex items-center gap-2 text-[10px]">
                        <button
                          type="button"
                          class="text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
                          @click="$emit('focusNode', conn.nodeId)"
                        >
                          На схеме
                        </button>
                        <button
                          type="button"
                          class="text-destructive underline-offset-2 hover:underline"
                          @click="$emit('removeConnection', conn.edgeId)"
                        >
                          Убрать переход
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <p v-else class="text-[10px] leading-relaxed text-muted-foreground">
                Пока не задано, из каких шагов обычно приходят сюда.
              </p>
            </div>

            <div class="space-y-2">
              <p class="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                Что происходит дальше
              </p>
              <div v-if="outgoingConnections.length" class="space-y-1.5">
                <div
                  v-for="conn in outgoingConnections"
                  :key="`out-${conn.edgeId}`"
                  class="rounded-md border border-border bg-background px-2.5 py-2"
                >
                  <div class="flex items-start justify-between gap-3">
                    <div class="min-w-0">
                      <p class="text-[11px] font-medium text-foreground">{{ conn.title }}</p>
                      <p class="mt-0.5 text-[10px] text-muted-foreground">{{ conn.relationLabel }}</p>
                    </div>
                    <div class="shrink-0 flex flex-col items-end gap-1">
                      <button
                        type="button"
                        class="rounded-md border border-border px-2 py-1 text-[10px] hover:bg-muted"
                        @click="$emit('openNode', conn.nodeId)"
                      >
                        Перейти к шагу
                      </button>
                      <div class="flex items-center gap-2 text-[10px]">
                        <button
                          type="button"
                          class="text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
                          @click="$emit('focusNode', conn.nodeId)"
                        >
                          На схеме
                        </button>
                        <button
                          type="button"
                          class="text-destructive underline-offset-2 hover:underline"
                          @click="$emit('removeConnection', conn.edgeId)"
                        >
                          Убрать переход
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
              <p v-else class="text-[10px] leading-relaxed text-muted-foreground">
                Пока не задано, что должно происходить после этого шага.
              </p>
            </div>
          </div>

          <p v-else class="mt-3 text-[10px] leading-relaxed text-muted-foreground">
            Этот шаг пока не встроен в общий ход разговора.
          </p>
        </div>

        <component :is="activePanel" v-bind="panelExtraProps" />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, provide, ref, toRef, watch, type Component, type Ref } from 'vue'
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
  openNode: [id: string]
  focusNode: [id: string]
  removeConnection: [edgeId: string]
  addConnection: [targetNodeId: string]
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
  incomingConnections,
  outgoingConnections,
  hasScenarioConnections,
  availableScenarioStepOptions,
} = model

const selectedStepToConnect = ref('')

watch(() => props.nodeId, () => {
  selectedStepToConnect.value = ''
})

const connectSelectedStep = () => {
  const targetId = selectedStepToConnect.value.trim()
  if (!targetId)
    return
  emit('addConnection', targetId)
  selectedStepToConnect.value = ''
}

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
