<template>
  <aside class="flex flex-col gap-2 rounded-lg border border-border bg-card/95 p-3 shadow-xl backdrop-blur-md w-72">
    <div class="flex items-center justify-between gap-2">
      <h4 class="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
        Проверка поиска ответа
      </h4>
      <button
        type="button"
        class="text-[10px] text-muted-foreground hover:text-foreground"
        @click="$emit('close')"
      >
        ✕
      </button>
    </div>
    <p class="text-[10px] leading-snug text-muted-foreground">
      Показывает, какие фрагменты сценария ассистент подберёт по фразе клиента.
      <template v-if="flowName">
        Строки текущего сценария подсвечиваются по названию потока.
      </template>
    </p>

    <form class="flex gap-1.5" @submit.prevent="run">
      <input
        v-model="query"
        type="text"
        class="min-w-0 flex-1 rounded-md border border-border bg-background px-2 py-1.5 text-xs"
        placeholder="Например: «У вас дорого»"
      />
      <button
        type="submit"
        class="rounded-md bg-primary px-3 text-xs text-primary-foreground disabled:opacity-50"
        :disabled="loading || !query.trim()"
      >
        {{ loading ? '…' : 'Поиск' }}
      </button>
    </form>

    <div v-if="error" class="rounded-md border border-destructive/40 bg-destructive/10 px-2 py-1.5 text-[10px]">
      {{ error }}
    </div>

    <div v-if="result" class="max-h-[50vh] overflow-auto rounded-md border border-border p-2 text-[11px]">
      <p v-if="statusMessage" class="mb-1 text-[10px] text-muted-foreground">
        {{ statusMessage }}
      </p>
      <template v-if="lightragMatches.length">
        <div
          v-for="(m, i) in lightragMatches"
          :key="i"
          class="mb-2 rounded-md border border-dashed border-border p-1.5"
          :class="isCurrentFlowMatch(m) ? 'ring-2 ring-primary/35 bg-primary/5' : ''"
        >
          <p class="font-semibold">{{ m.tactic_title || '(без названия)' }}</p>
          <p v-if="m.flow_name" class="text-muted-foreground">
            Сценарий: {{ m.flow_name }}<span v-if="m.stage"> · этап: {{ m.stage }}</span>
          </p>
          <ul class="mt-1 space-y-0.5">
            <li v-if="m.motives.length">
              <span class="text-muted-foreground">Мотивы:</span> {{ m.motives.join(', ') }}
            </li>
            <li v-if="m.objections_answered.length">
              <span class="text-muted-foreground">Закрывает возражения:</span> {{ m.objections_answered.join(', ') }}
            </li>
            <li v-if="m.arguments.length">
              <span class="text-muted-foreground">Аргументы:</span> {{ m.arguments.join(' · ') }}
            </li>
            <li v-if="m.proofs.length">
              <span class="text-muted-foreground">Доказательства:</span> {{ m.proofs.join(' · ') }}
            </li>
            <li v-if="m.constraints.length" class="text-destructive/80">
              Ограничения: {{ m.constraints.join(' · ') }}
            </li>
            <li v-if="m.required_followup_question" class="mt-1 rounded border border-primary/40 bg-primary/10 p-1">
              ОБЯЗАТЕЛЬНЫЙ ВОПРОС: «{{ m.required_followup_question }}»
            </li>
          </ul>
        </div>
      </template>
      <template v-else-if="result.raw">
        <pre class="whitespace-pre-wrap break-words text-[10px] leading-snug">{{ result.raw }}</pre>
      </template>
      <template v-else-if="!statusMessage">
        <p class="text-muted-foreground">Ничего не найдено.</p>
      </template>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useScriptFlows } from '~/composables/useScriptFlows'
import { getReadableErrorMessage } from '~/utils/api-errors'
import type { ScriptFlowSearchTestMatchLightRag, ScriptFlowSearchTestResult } from '~/types/scriptFlow'

const props = defineProps<{
  agentId: string
  /** Имя открытого потока — для подсветки матчей в редакторе */
  flowName?: string | null
  flowId?: string | null
}>()
defineEmits<{ close: [] }>()

const { testSearch } = useScriptFlows(props.agentId)

const query = ref('')
const loading = ref(false)
const error = ref<string | null>(null)
const result = ref<ScriptFlowSearchTestResult | null>(null)

const statusMessage = computed(() => {
  if (!result.value) return null
  if (result.value.status === 'disabled') return 'Расширенный поиск по базе отключён в настройках.'
  if (result.value.status === 'no_index') return 'В память ассистента ещё не загружен ни один поток.'
  if (result.value.status === 'error') return result.value.error ?? 'Ошибка поиска.'
  return null
})

const isLightRagMatch = (m: unknown): m is ScriptFlowSearchTestMatchLightRag =>
  !!m && typeof m === 'object' && 'tactic_title' in (m as Record<string, unknown>)

const lightragMatches = computed<ScriptFlowSearchTestMatchLightRag[]>(() => {
  const arr = result.value?.matches ?? []
  return (arr as unknown[]).filter(isLightRagMatch)
})

const isCurrentFlowMatch = (m: ScriptFlowSearchTestMatchLightRag) => {
  const fn = (m.flow_name || '').trim()
  const cur = (props.flowName || '').trim()
  if (!fn || !cur)
    return false
  return fn === cur
}

const run = async () => {
  error.value = null
  loading.value = true
  try {
    result.value = await testSearch(query.value.trim())
  } catch (e: unknown) {
    error.value = getReadableErrorMessage(e, 'Не удалось выполнить поиск')
  } finally {
    loading.value = false
  }
}
</script>
