<template>
  <div class="script-flow-node-panel">
    <div class="rounded-xl border border-indigo-200/70 bg-indigo-50/60 px-4 py-3 shadow-sm dark:bg-indigo-950/10">
      <p class="text-[11px] font-semibold text-foreground">Переход к другой теме или отдельному сценарию</p>
      <p class="mt-1 text-[10px] leading-relaxed text-muted-foreground">
        Используйте этот шаг, когда разговор нужно мягко перевести в другой поток,
        не теряя понятную связку между темами.
      </p>
    </div>
    <div class="rounded-xl border border-border/80 bg-background/95 px-4 py-4 shadow-sm space-y-3">
      <div>
        <p class="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">2. Куда и как перевести разговор</p>
        <p class="mt-1 text-[10px] leading-relaxed text-muted-foreground">
          Выберите целевой сценарий и опишите фразу, которая мягко связывает текущую тему со следующей.
        </p>
      </div>
      <div class="space-y-1">
        <label class="insp-label">К какой теме или сценарию перейти</label>
        <select
          class="insp-input"
          :value="localTargetFlowId ?? ''"
          @change="onTargetFlowChange"
        >
          <option value="">
            — не выбран —
          </option>
          <option
            v-for="opt in gotoOptions"
            :key="opt.id"
            :value="opt.id"
          >
            {{ opt.name }}
            {{ opt.flow_status === 'published' ? '· опубликован' : '· черновик' }}
          </option>
        </select>
        <p v-if="!gotoOptions.length" class="text-[10px] text-muted-foreground">
          Нет других потоков — создайте второй поток агента в списке «Потоки эксперта».
        </p>
      </div>
      <div class="space-y-1">
        <label class="insp-label">Внутренний шаг в целевом сценарии (необязательно)</label>
        <input
          v-model="localTargetNodeRef"
          type="text"
          class="insp-input font-mono text-[11px]"
          placeholder="ID шага, если нужен точный вход"
          @input="flushNode"
          @focus="focusField('target_node_ref')"
        >
      </div>
      <div class="space-y-1">
        <label class="insp-label">Как мягко перевести разговор</label>
        <textarea
          v-model="localTransitionPhrase"
          rows="2"
          class="insp-input resize-none"
          placeholder="Фраза, которая связывает текущую тему со следующим сценарием"
          @input="flushNode"
          @focus="focusField('transition_phrase')"
        />
      </div>
      <div class="space-y-1">
        <label class="insp-label">Когда такой переход уместен</label>
        <textarea
          v-model="localTriggerSituation"
          rows="2"
          class="insp-input resize-none"
          placeholder="Опишите ситуацию, в которой разговор стоит перевести дальше"
          @input="flushNode"
          @focus="focusField('trigger_situation')"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, inject, type ComputedRef } from 'vue'
import { SCRIPT_FLOW_INSPECTOR_KEY } from '~/composables/useScriptFlowInspectorModel'

type GotoOpt = { id: string; name: string; flow_status: string }

const emptyOpts = computed((): GotoOpt[] => [])
const gotoFlowOptionsRef = inject<ComputedRef<GotoOpt[]>>(
  'scriptFlowGotoOptions',
  emptyOpts,
)
const gotoOptions = computed(() => gotoFlowOptionsRef.value)

const {
  localTransitionPhrase,
  localTriggerSituation,
  localTargetFlowId,
  localTargetNodeRef,
  lastFocusedField,
  flushNode,
} = inject(SCRIPT_FLOW_INSPECTOR_KEY)!

const focusField = (k: string) => {
  lastFocusedField.value = k
}

const onTargetFlowChange = (e: Event) => {
  const v = (e.target as HTMLSelectElement).value.trim()
  localTargetFlowId.value = v.length ? v : null
  flushNode()
}
</script>
