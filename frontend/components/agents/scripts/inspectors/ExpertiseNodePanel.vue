<template>
  <div class="script-flow-node-panel">
    <div class="space-y-4">
      <InspectorContextFields />
      <div class="rounded-xl border border-border/80 bg-background/95 px-4 py-3 shadow-sm space-y-1">
        <label class="insp-label inline-flex items-center gap-2">
          <span>Ситуация клиента</span>
          <FieldHelpIcons
            field-key="expertise.situation"
            node-type="expertise"
            :node-id="nodeId"
            :current-node-data="currentNodeData"
            :current-value="localSituation"
            @ai-fill="(t: string) => applyAi('situation', t)"
          />
        </label>
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
          <label class="insp-label inline-flex items-center gap-2">
            <span>Что важно понять про клиента</span>
            <FieldHelpIcons
              field-key="expertise.why_it_works"
              node-type="expertise"
              :node-id="nodeId"
              :current-node-data="currentNodeData"
              :current-value="localWhyItWorks"
              @ai-fill="(t: string) => applyAi('why_it_works', t)"
            />
          </label>
          <textarea
            v-model="localWhyItWorks"
            class="insp-input"
            placeholder="Почему эта мысль или подача должна сработать именно в такой ситуации"
            @input="flushNode"
            @focus="focusField('why_it_works')"
          />
        </div>
        <div class="space-y-1">
          <label class="insp-label inline-flex items-center gap-2">
            <span>Что сказать и как подать мысль</span>
            <FieldHelpIcons
              field-key="expertise.approach"
              node-type="expertise"
              :node-id="nodeId"
              :current-node-data="currentNodeData"
              :current-value="localApproach"
              @ai-fill="(t: string) => applyAi('approach', t)"
            />
          </label>
          <textarea
            v-model="localApproach"
            class="insp-input"
            placeholder="Коротко опишите основную мысль, логику и тон этого шага"
            @input="flushNode"
            @focus="focusField('approach')"
          />
        </div>
        <div class="space-y-1">
          <label class="insp-label inline-flex items-center gap-2">
            <span>Примеры формулировок</span>
            <FieldHelpIcons
              field-key="expertise.example_phrases"
              node-type="expertise"
              :node-id="nodeId"
              :current-node-data="currentNodeData"
              :current-value="localExamplePhrasesStr"
              @ai-fill="(t: string) => applyAi('example_phrases', t)"
            />
          </label>
          <textarea
            v-model="localExamplePhrasesStr"
            class="insp-input font-mono text-[11px]"
            placeholder="По одной удачной фразе на строку"
            @input="flushNode"
            @focus="focusField('example_phrases')"
          />
        </div>
        <div class="space-y-1">
          <label class="insp-label inline-flex items-center gap-2">
            <span>Чего не говорить</span>
            <FieldHelpIcons
              field-key="expertise.watch_out"
              node-type="expertise"
              :node-id="nodeId"
              :current-node-data="currentNodeData"
              :current-value="localWatchOut"
              @ai-fill="(t: string) => applyAi('watch_out', t)"
            />
          </label>
          <textarea
            v-model="localWatchOut"
            class="insp-input"
            placeholder="Фразы, акценты или интонации, которых лучше избегать"
            @input="flushNode"
            @focus="focusField('watch_out')"
          />
        </div>
        <div class="space-y-1">
          <label class="insp-label inline-flex items-center gap-2">
            <span>Чем логично продолжить разговор</span>
            <FieldHelpIcons
              field-key="expertise.good_question"
              node-type="expertise"
              :node-id="nodeId"
              :current-node-data="currentNodeData"
              :current-value="localGoodQuestion"
              @ai-fill="(t: string) => applyAi('good_question', t)"
            />
          </label>
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
import { SCRIPT_FLOW_INSPECTOR_KEY } from '~/composables/useScriptFlowInspectorModel'
import InspectorContextFields from './InspectorContextFields.vue'
import InspectorKgLinks from './InspectorKgLinks.vue'
import FieldHelpIcons from './FieldHelpIcons.vue'

const m = inject(SCRIPT_FLOW_INSPECTOR_KEY)!
const {
  nodeId,
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

const currentNodeData = computed(() => ({
  situation: localSituation.value,
  why_it_works: localWhyItWorks.value,
  approach: localApproach.value,
  example_phrases: localExamplePhrasesStr.value
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean),
  watch_out: localWatchOut.value,
  good_question: localGoodQuestion.value,
}))

const FIELD_REFS: Record<string, { value: string }> = {
  situation: localSituation,
  why_it_works: localWhyItWorks,
  approach: localApproach,
  example_phrases: localExamplePhrasesStr,
  watch_out: localWatchOut,
  good_question: localGoodQuestion,
}

const applyAi = (field: string, text: string) => {
  const ref = FIELD_REFS[field]
  if (!ref) return
  ref.value = text
  flushNode()
}
</script>
