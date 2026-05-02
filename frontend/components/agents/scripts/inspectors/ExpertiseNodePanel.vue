<template>
  <div class="script-flow-node-panel">
    <div class="space-y-4">
      <InspectorContextFields />
      <div class="rounded-xl border border-border/80 bg-background/95 px-4 py-3 shadow-sm space-y-1">
        <label class="insp-label">Ситуация клиента</label>
        <textarea
          v-model="localSituation"
          class="insp-input"
          placeholder="В каком состоянии, запросе или контексте клиента этот шаг особенно уместен"
          @input="flushNode"
          @focus="focusField('situation')"
        />
      </div>
    </div>

    <hr class="border-border/60 my-1" />

    <div class="space-y-4">
      <div class="rounded-xl border border-border/80 bg-background/95 px-4 py-3 shadow-sm space-y-3">
        <p class="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">Что говорить</p>
        <div class="space-y-1">
          <label class="insp-label">Что важно понять про клиента</label>
          <textarea
            v-model="localWhyItWorks"
            class="insp-input"
            placeholder="Почему эта мысль или подача должна сработать именно в такой ситуации"
            @input="flushNode"
            @focus="focusField('why_it_works')"
          />
        </div>
        <div class="space-y-1">
          <label class="insp-label">Что сказать и как подать мысль</label>
          <textarea
            v-model="localApproach"
            class="insp-input"
            placeholder="Коротко опишите основную мысль, логику и тон этого шага"
            @input="flushNode"
            @focus="focusField('approach')"
          />
        </div>
        <div class="space-y-1">
          <label class="insp-label">Примеры формулировок</label>
          <textarea
            v-model="localExamplePhrasesStr"
            class="insp-input font-mono text-[11px]"
            placeholder="По одной удачной фразе на строку"
            @input="flushNode"
            @focus="focusField('example_phrases')"
          />
        </div>
        <div class="space-y-1">
          <label class="insp-label">Чего не говорить</label>
          <textarea
            v-model="localWatchOut"
            class="insp-input"
            placeholder="Фразы, акценты или интонации, которых лучше избегать"
            @input="flushNode"
            @focus="focusField('watch_out')"
          />
        </div>
        <div class="space-y-1">
          <label class="insp-label">Чем логично продолжить разговор</label>
          <textarea
            v-model="localGoodQuestion"
            class="insp-input"
            placeholder="Какой следующий вопрос или переход лучше всего продолжает эту мысль"
            @input="flushNode"
            @focus="focusField('good_question')"
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

const m = inject(SCRIPT_FLOW_INSPECTOR_KEY)!
const {
  localSituation,
  localWhyItWorks,
  localApproach,
  localExamplePhrasesStr,
  localWatchOut,
  localGoodQuestion,
  lastFocusedField,
  flushNode,
} = m

const focusField = (k: string) => {
  lastFocusedField.value = k
}
</script>
