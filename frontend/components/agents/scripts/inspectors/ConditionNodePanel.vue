<template>
  <div class="script-flow-node-panel">
    <div class="rounded-xl border border-indigo-200/70 bg-indigo-50/60 px-4 py-3 shadow-sm dark:bg-indigo-950/10">
      <p class="text-[11px] font-semibold text-foreground">Развилка по ответу клиента</p>
      <p class="mt-1 text-[10px] leading-relaxed text-muted-foreground">
        Здесь не нужно писать длинную схему. Достаточно описать, как понять ответ клиента,
        и перечислить основные варианты, от которых на карте пойдут разные ветки.
      </p>
    </div>
    <div class="rounded-xl border border-border/80 bg-background/95 p-4 shadow-sm space-y-3">
      <div>
        <p class="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">2. Как разложить ответы по веткам</p>
        <p class="mt-1 text-[10px] leading-relaxed text-muted-foreground">
          Сначала опишите общую логику развилки, потом перечислите главные варианты ответа клиента.
        </p>
      </div>
      <div class="space-y-1">
        <label class="insp-label">Как интерпретировать ответ клиента</label>
        <textarea
          v-model="localRoutingHint"
          rows="3"
          class="insp-input resize-none"
          placeholder="Например: если клиент сомневается в цене, идем в работу с возражением; если готов — ведем к записи"
          @input="flushNode"
          @focus="focusField('routing_hint')"
        />
      </div>
      <div class="space-y-2">
        <label class="insp-label">Основные варианты ответа клиента</label>
        <p class="text-[10px] text-muted-foreground">
          Для каждого варианта можно провести свою линию к следующему шагу. Ветка «По умолчанию» на схеме — без текста.
        </p>
      <div v-for="(br, i) in localBranches" :key="br.id" class="flex gap-1 items-center">
        <input
          :value="localBranches[i]?.label ?? ''"
          type="text"
          class="insp-input flex-1"
          :placeholder="`Вариант ${i + 1}`"
          @input="updateCondition(i, ($event.target as HTMLInputElement).value)"
        >
        <button
          type="button"
          class="shrink-0 rounded border border-destructive/30 px-2 py-1 text-[10px] text-destructive"
          @click="removeCondition(i)"
        >
          ✕
        </button>
      </div>
      <button
        type="button"
        class="w-full rounded-lg border border-dashed border-primary/40 bg-background/80 py-2 text-[11px] font-medium text-primary shadow-sm"
        @click="addCondition"
      >
        + Добавить вариант
      </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { inject } from 'vue'
import { SCRIPT_FLOW_INSPECTOR_KEY } from '~/composables/useScriptFlowInspectorModel'

const {
  localRoutingHint,
  localBranches,
  lastFocusedField,
  flushNode,
  updateCondition,
  addCondition,
  removeCondition,
} = inject(SCRIPT_FLOW_INSPECTOR_KEY)!

const focusField = (k: string) => {
  lastFocusedField.value = k
}
</script>
