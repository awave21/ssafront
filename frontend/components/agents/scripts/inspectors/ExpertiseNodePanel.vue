<template>
  <div class="script-flow-node-panel">
    <div class="rounded-xl border border-indigo-200/70 bg-indigo-50/60 px-4 py-3 shadow-sm dark:bg-indigo-950/10">
      <p class="text-[11px] font-semibold text-foreground">Основной смысловой шаг разговора</p>
      <p class="mt-1 text-[10px] leading-relaxed text-muted-foreground">
        Здесь эксперт описывает саму тактику: в какой ситуации этот шаг нужен, что стоит донести клиенту,
        каких формулировок избегать и каким вопросом мягко вести разговор дальше.
        Мотив можно оформить в <a :href="libraryHref" target="_blank" class="font-medium text-indigo-600 underline">библиотеке</a> и привязать ниже.
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
        Что сказать
      </button>
    </div>
    <div v-show="axisTab === 'context'" class="space-y-4">
      <InspectorContextFields />
      <div class="rounded-xl border border-border/80 bg-background/95 px-4 py-4 shadow-sm space-y-3">
        <div>
          <p class="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Контекст клиента</p>
          <p class="mt-1 text-[10px] leading-relaxed text-muted-foreground">
            Опишите, в каком запросе, настроении или ситуации этот смысловой шаг особенно полезен.
          </p>
        </div>
        <div class="space-y-1">
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
    </div>
    <div v-show="axisTab === 'content'" class="space-y-4">
      <div class="rounded-xl border border-border/80 bg-background/95 px-4 py-4 shadow-sm space-y-3">
        <div>
          <p class="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">2. Что говорить на этом шаге</p>
          <p class="mt-1 text-[10px] leading-relaxed text-muted-foreground">
            Соберите суть, удачные формулировки и ограничения, чтобы шаг был легко понятен любому эксперту.
          </p>
        </div>
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
import { computed, inject } from 'vue'
import { useRoute } from 'vue-router'
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
  axisTab,
} = m

const setAxisTab = (t: 'context' | 'content') => {
  axisTab.value = t
}

const focusField = (k: string) => {
  lastFocusedField.value = k
}

const route = useRoute()
const libraryHref = computed(() => `/agents/${route.params.id}/scripts/library`)
</script>
