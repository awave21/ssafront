<template>
  <div class="script-flow-node-panel">
    <div class="rounded-xl border border-indigo-200/70 bg-indigo-50/60 px-4 py-3 shadow-sm dark:bg-indigo-950/10">
      <p class="text-[11px] font-semibold text-foreground">К какому итогу ведем эту ветку</p>
      <p class="mt-1 text-[10px] leading-relaxed text-muted-foreground">
        Этот шаг завершает текущую часть разговора. Зафиксируйте результат и опишите,
        чем должен закончиться диалог со стороны ассистента.
      </p>
    </div>
    <div class="rounded-xl border border-border/80 bg-background/95 px-4 py-4 shadow-sm space-y-3">
      <div>
        <p class="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">2. Чем завершить ветку</p>
        <p class="mt-1 text-[10px] leading-relaxed text-muted-foreground">
          Выберите итог и коротко зафиксируйте, какое финальное действие или сообщение ожидается от ассистента.
        </p>
      </div>
      <div class="space-y-1">
        <label class="insp-label">Итог разговора в этой ветке</label>
        <select v-model="localOutcomeType" class="insp-input" @change="flushNode">
          <option :value="null">— Не указан —</option>
          <option v-for="opt in OUTCOME_OPTIONS" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
      </div>
      <div class="space-y-1">
        <label class="insp-label">Что ассистент должен сделать или сказать в финале</label>
        <textarea
          v-model="localFinalAction"
          rows="4"
          class="insp-input resize-none"
          placeholder="Например: подтвердить запись, зафиксировать интерес, предложить вернуться позже"
          @input="flushNode"
          @focus="focusField('final_action')"
        />
      </div>
    </div>
    <div class="border-t border-border pt-4">
      <InspectorKgLinks :show-outcome="true" :include-constraint="false" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { inject } from 'vue'
import { SCRIPT_FLOW_INSPECTOR_KEY } from '~/composables/useScriptFlowInspectorModel'
import InspectorKgLinks from './InspectorKgLinks.vue'

const OUTCOME_OPTIONS = [
  { value: 'success', label: '✅ Успех' },
  { value: 'pending', label: '⏳ Отложено' },
  { value: 'lost', label: '❌ Отказ' },
] as const

const { localOutcomeType, localFinalAction, lastFocusedField, flushNode } = inject(SCRIPT_FLOW_INSPECTOR_KEY)!

const focusField = (k: string) => {
  lastFocusedField.value = k
}
</script>
