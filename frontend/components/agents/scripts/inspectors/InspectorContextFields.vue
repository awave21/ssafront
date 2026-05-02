<template>
  <div class="space-y-3">
    <p class="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Когда использовать</p>
    <div class="grid grid-cols-2 gap-2">
      <div class="space-y-1">
        <label class="insp-label">Этап разговора</label>
        <select v-model="localStage" class="insp-input" @change="flushNode">
          <option :value="null">— Любой —</option>
          <option v-for="st in CONVERSATION_STAGES" :key="st.value" :value="st.value">
            {{ st.label }}
          </option>
        </select>
      </div>
      <div class="space-y-1">
        <label class="insp-label">Приоритет шага</label>
        <input v-model.number="localLevel" type="number" min="1" max="5" class="insp-input" @input="flushNode">
      </div>
    </div>
    <div class="flex items-center justify-between rounded-xl border border-border/80 bg-background/95 px-3 py-2.5 shadow-sm">
      <div>
        <p class="text-[10px] font-semibold text-foreground">Использовать в ответах ассистента</p>
        <p class="text-[9px] text-muted-foreground">Шаг будет участвовать в подборе сценария и формулировок ответа</p>
      </div>
      <button
        type="button"
        class="relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors"
        :class="localIsEntryPoint ? 'bg-primary' : 'bg-muted-foreground/30'"
        @click="localIsEntryPoint = !localIsEntryPoint; flushNode()"
      >
        <span
          class="inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform"
          :class="localIsEntryPoint ? 'translate-x-4' : 'translate-x-1'"
        />
      </button>
    </div>

    <FunctionVariablePicker />
  </div>
</template>

<script setup lang="ts">
import { inject } from 'vue'
import { SCRIPT_FLOW_INSPECTOR_KEY } from '~/composables/useScriptFlowInspectorModel'
import FunctionVariablePicker from './FunctionVariablePicker.vue'

const {
  localStage,
  localLevel,
  localIsEntryPoint,
  flushNode,
  CONVERSATION_STAGES,
} = inject(SCRIPT_FLOW_INSPECTOR_KEY)!
</script>
