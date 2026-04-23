<template>
  <div class="space-y-3">
    <div class="rounded-xl border border-border/80 bg-background/95 px-3 py-3 shadow-sm">
      <p class="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">1. Когда использовать этот шаг</p>
      <p class="mt-1 text-[10px] leading-relaxed text-muted-foreground">
        Помогите ассистенту понять, в какой части разговора и с каким приоритетом этот шаг уместен.
      </p>
    </div>
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

    <div class="rounded-xl border border-dashed border-violet-300/70 bg-violet-50/50 px-3 py-3 shadow-sm dark:bg-violet-950/10">
      <p class="text-[10px] font-semibold uppercase tracking-wide text-violet-700 dark:text-violet-300">Опоры из данных и функций</p>
      <p class="mt-1 text-[10px] leading-relaxed text-muted-foreground">
        Если в этом шаге нужны переменные или данные из функций, подключите их ниже.
      </p>
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
