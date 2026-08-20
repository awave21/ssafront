<template>
  <div class="script-flow-node-panel">
    <div class="rounded-xl border border-indigo-200/70 bg-indigo-50/60 px-4 py-3 shadow-sm dark:bg-indigo-950/10">
      <p class="text-[11px] font-semibold text-foreground">Когда разговор должен стартовать по этому сценарию</p>
      <p class="mt-1 text-[10px] leading-relaxed text-muted-foreground">
        Опишите, как клиент обычно заходит в тему и по каким сигналам ассистент должен понять:
        пора открыть именно этот маршрут разговора.
      </p>
    </div>
    <div class="flex items-center justify-between rounded-xl border border-border/80 bg-background/95 px-4 py-3.5 shadow-sm">
      <div>
        <p class="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">1. Как использовать вход</p>
        <p class="text-[11px] font-semibold text-foreground">Показывать как основной вход</p>
        <p class="text-[10px] leading-relaxed text-muted-foreground">Этот шаг будет считаться явным стартом карты разговора</p>
      </div>
      <button
        type="button"
        class="relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors"
        :class="localIsFlowEntry ? 'bg-primary' : 'bg-muted-foreground/30'"
        @click="localIsFlowEntry = !localIsFlowEntry; flushNode()"
      >
        <span
          class="inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform"
          :class="localIsFlowEntry ? 'translate-x-4' : 'translate-x-1'"
        />
      </button>
    </div>
    <div class="rounded-xl border border-border/80 bg-background/95 px-4 py-4 shadow-sm space-y-3">
      <div>
        <p class="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">2. Как клиент заходит в тему</p>
        <p class="mt-1 text-[10px] leading-relaxed text-muted-foreground">
          Соберите типичные формулировки и признаки, по которым ассистент поймет, что нужно открыть этот сценарий.
        </p>
      </div>

      <div class="space-y-1">
        <label class="insp-label inline-flex items-center gap-2">
          <span>Как клиент обычно это формулирует</span>
          <FieldHelpIcons
            field-key="trigger.client_phrase_examples"
            node-type="trigger"
            :node-id="nodeId"
            :current-node-data="currentNodeData"
            :current-value="localClientPhraseExamplesStr"
            @ai-fill="(t: string) => applyAi('client_phrase_examples', t)"
          />
        </label>
        <textarea
          v-model="localClientPhraseExamplesStr"
          class="insp-input font-mono text-[11px]"
          placeholder="Например: Хочу записаться... / Сколько стоит... / Что вы посоветуете..."
          @input="flushNode"
          @focus="focusField('client_phrase_examples')"
        />
      </div>
      <div class="space-y-1">
        <label class="insp-label inline-flex items-center gap-2">
          <span>Когда сценарий уместен</span>
          <FieldHelpIcons
            field-key="trigger.when_relevant"
            node-type="trigger"
            :node-id="nodeId"
            :current-node-data="currentNodeData"
            :current-value="localWhenRelevant"
            @ai-fill="(t: string) => applyAi('when_relevant', t)"
          />
        </label>
        <textarea
          v-model="localWhenRelevant"
          class="insp-input"
          placeholder="Опишите ситуацию, в которой этот сценарий действительно нужен"
          @input="flushNode"
          @focus="focusField('when_relevant')"
        />
      </div>
      <div class="space-y-1">
        <label class="insp-label inline-flex items-center gap-2">
          <span>Слова и сигналы, по которым это можно узнать</span>
          <FieldHelpIcons
            field-key="trigger.keyword_hints"
            node-type="trigger"
            :node-id="nodeId"
            :current-node-data="currentNodeData"
            :current-value="localKeywordHintsStr"
            @ai-fill="(t: string) => applyAi('keyword_hints', t)"
          />
        </label>
        <textarea
          v-model="localKeywordHintsStr"
          class="insp-input font-mono text-[11px]"
          placeholder="По одному слову или сигналу на строку"
          @input="flushNode"
          @focus="focusField('keyword_hints')"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, inject } from 'vue'
import { SCRIPT_FLOW_INSPECTOR_KEY } from '~/composables/useScriptFlowInspectorModel'
import FieldHelpIcons from './FieldHelpIcons.vue'

const {
  nodeId,
  localWhenRelevant,
  localClientPhraseExamplesStr,
  localKeywordHintsStr,
  localIsFlowEntry,
  lastFocusedField,
  flushNode,
} = inject(SCRIPT_FLOW_INSPECTOR_KEY)!

const focusField = (k: string) => {
  lastFocusedField.value = k
}

const splitLines = (s: string) =>
  s
    .split('\n')
    .map((x) => x.trim())
    .filter(Boolean)

const currentNodeData = computed(() => ({
  client_phrase_examples: splitLines(localClientPhraseExamplesStr.value),
  when_relevant: localWhenRelevant.value,
  keyword_hints: splitLines(localKeywordHintsStr.value),
  is_flow_entry: localIsFlowEntry.value,
}))

const FIELD_REFS: Record<string, { value: string }> = {
  client_phrase_examples: localClientPhraseExamplesStr,
  when_relevant: localWhenRelevant,
  keyword_hints: localKeywordHintsStr,
}

const applyAi = (field: string, text: string) => {
  const ref = FIELD_REFS[field]
  if (!ref) return
  ref.value = text
  flushNode()
}
</script>
