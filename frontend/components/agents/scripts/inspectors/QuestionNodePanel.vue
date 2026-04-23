<template>
  <div class="script-flow-node-panel">
    <div class="rounded-xl border border-indigo-200/70 bg-indigo-50/60 px-4 py-3 shadow-sm dark:bg-indigo-950/10">
      <p class="text-[11px] font-semibold text-foreground">Шаг, который помогает продвинуть разговор</p>
      <p class="mt-1 text-[10px] leading-relaxed text-muted-foreground">
        Слева задайте контекст, а во вкладке ниже сформулируйте сам вопрос так,
        чтобы эксперту было понятно: что спросить, зачем и какой ответ ожидается.
      </p>
    </div>
    <div class="flex rounded-xl border border-border/80 bg-background/95 p-1.5 gap-1.5 shadow-sm">
      <button
        type="button"
        class="flex-1 rounded-lg px-3.5 py-2.5 text-[11px] font-semibold transition-colors"
        :class="axisTab === 'context' ? 'bg-background shadow-sm' : 'text-muted-foreground'"
        @click="setAxisTab('context')"
      >
        Когда применять
      </button>
      <button
        type="button"
        class="flex-1 rounded-lg px-3.5 py-2.5 text-[11px] font-semibold transition-colors"
        :class="axisTab === 'content' ? 'bg-background shadow-sm' : 'text-muted-foreground'"
        @click="setAxisTab('content')"
      >
        Что спросить
      </button>
    </div>
    <div v-show="axisTab === 'context'" class="space-y-4">
      <InspectorContextFields />
    </div>
    <div v-show="axisTab === 'content'" class="space-y-4">
      <div class="rounded-xl border border-border/80 bg-background/95 px-4 py-4 shadow-sm space-y-3">
        <div>
          <p class="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">2. Что спросить на этом шаге</p>
          <p class="mt-1 text-[10px] leading-relaxed text-muted-foreground">
            Сформулируйте основной вопрос, ожидаемый тип ответа и запасные варианты формулировок.
          </p>
        </div>
        <div class="space-y-1">
          <label class="insp-label">Основной вопрос клиенту</label>
          <textarea
            v-model="localGoodQuestion"
            class="insp-input"
            placeholder="Напишите вопрос так, как его должен задать ассистент"
            @input="flushNode"
            @focus="focusField('good_question')"
          />
        </div>
        <div class="space-y-1">
          <label class="insp-label">Какой ответ ожидаем</label>
          <select
            v-model="localExpectedAnswerType"
            class="insp-input"
            @change="flushNode()"
          >
            <option value="open">
              Открытый текст
            </option>
            <option value="yes_no">
              Да / нет
            </option>
            <option value="choice">
              Выбор из вариантов
            </option>
            <option value="number">
              Число / сумма
            </option>
          </select>
        </div>
        <div class="space-y-1">
          <label class="insp-label">Зачем задаем этот вопрос</label>
          <textarea
            v-model="localWhyWeAsk"
            class="insp-input"
            placeholder="Какую информацию этот вопрос помогает получить или уточнить"
            @input="flushNode"
            @focus="focusField('why_we_ask')"
          />
        </div>
        <div class="space-y-1">
          <label class="insp-label">Другие удачные формулировки</label>
          <textarea
            v-model="localAlternativePhrasingsStr"
            class="insp-input font-mono text-[11px]"
            placeholder="По одной формулировке на строку"
            @input="flushNode"
            @focus="focusField('alternative_phrasings')"
          />
        </div>
      </div>
      <div class="border-t border-border pt-4">
        <InspectorKgLinks />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { inject } from 'vue'
import { SCRIPT_FLOW_INSPECTOR_KEY } from '~/composables/useScriptFlowInspectorModel'
import InspectorContextFields from './InspectorContextFields.vue'
import InspectorKgLinks from './InspectorKgLinks.vue'

const {
  localGoodQuestion,
  localWhyWeAsk,
  localAlternativePhrasingsStr,
  localExpectedAnswerType,
  lastFocusedField,
  flushNode,
  axisTab,
} = inject(SCRIPT_FLOW_INSPECTOR_KEY)!

const setAxisTab = (t: 'context' | 'content') => {
  axisTab.value = t
}

const focusField = (k: string) => {
  lastFocusedField.value = k
}
</script>
