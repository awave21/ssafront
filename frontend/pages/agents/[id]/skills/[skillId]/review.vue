<template>
  <AgentPageShell title="Ревью навыка" :hide-actions="true" :contained="true">
    <div class="max-w-full space-y-5">
      <!-- Header -->
      <div class="flex items-center justify-between gap-3">
        <NuxtLink
          :to="`/agents/${agentId}/skills/${skillId}`"
          class="inline-flex h-9 items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50"
        >
          <ArrowLeft class="h-4 w-4" />
          К навыку
        </NuxtLink>
        <button
          type="button"
          class="inline-flex h-9 items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          :disabled="loading"
          @click="load"
        >
          <RefreshCw class="h-4 w-4" :class="loading ? 'animate-spin' : ''" />
          Обновить
        </button>
      </div>

      <div class="flex items-start gap-3 rounded-2xl border border-indigo-100 bg-indigo-50/50 px-4 py-3 text-sm text-indigo-900">
        <Inbox class="mt-0.5 h-4 w-4 shrink-0 text-indigo-500" />
        <p>
          Реальные ходы агента по услугам навыка. Отметьте, где агент ответил верно, ушёл в
          общие слова или пережал — и продиктуйте, «как надо». Правка попадёт прямо в навык.
        </p>
      </div>

      <div v-if="!hasServiceLink" class="rounded-2xl border border-amber-200 bg-amber-50/50 px-4 py-3 text-sm text-amber-800">
        У навыка не привязаны услуги — показаны последние диалоги агента. Привяжите услугу,
        чтобы видеть только релевантные разговоры.
      </div>

      <!-- Loading -->
      <div v-if="loading" class="flex justify-center py-16">
        <Loader2 class="h-8 w-8 animate-spin text-indigo-600" />
      </div>

      <!-- Empty -->
      <div
        v-else-if="!dialogs.length"
        class="rounded-3xl border-2 border-dashed border-slate-100 bg-white p-10 text-center"
      >
        <Inbox class="mx-auto mb-3 h-10 w-10 text-slate-300" />
        <p class="text-sm font-medium text-slate-700">Диалогов для ревью пока нет</p>
        <p class="mt-1 text-xs text-slate-500">Появятся, когда пациенты начнут писать по этим услугам.</p>
      </div>

      <!-- Dialogs -->
      <div v-else class="space-y-3">
        <div
          v-for="d in dialogs"
          :key="d.run_id"
          class="overflow-hidden rounded-3xl border border-slate-100 bg-white shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]"
        >
          <div class="space-y-2.5 p-5">
            <!-- patient -->
            <div class="flex gap-2.5">
              <span class="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-[10px] font-bold text-slate-500">П</span>
              <p class="rounded-2xl rounded-tl-sm bg-slate-50 px-3 py-2 text-sm text-slate-800">{{ d.input }}</p>
            </div>
            <!-- agent -->
            <div class="flex gap-2.5">
              <span class="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-indigo-100 text-[10px] font-bold text-indigo-600">А</span>
              <div class="min-w-0 flex-1">
                <p class="rounded-2xl rounded-tl-sm bg-indigo-50/60 px-3 py-2 text-sm text-slate-800">
                  {{ d.output || '—' }}
                </p>
                <div v-if="d.tool_names.length" class="mt-1 flex flex-wrap gap-1">
                  <span
                    v-for="(t, i) in d.tool_names"
                    :key="`${d.run_id}-t-${i}`"
                    class="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-500"
                  >{{ t }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- review controls -->
          <div class="flex flex-wrap items-center gap-2 border-t border-slate-100 bg-slate-50/60 px-5 py-3">
            <div class="flex overflow-hidden rounded-lg border border-slate-200">
              <button
                v-for="mk in marks"
                :key="mk.key"
                type="button"
                class="px-2.5 py-1 text-[11px] font-semibold transition-colors"
                :class="markState[d.run_id] === mk.key ? mk.active : 'bg-white text-slate-500 hover:bg-slate-50'"
                @click="setMark(d, mk.key)"
              >
                {{ mk.label }}
              </button>
            </div>
            <button
              v-if="!correctingId || correctingId !== d.run_id"
              type="button"
              class="inline-flex items-center gap-1 rounded-lg border border-indigo-200 bg-white px-2.5 py-1 text-[11px] font-medium text-indigo-700 hover:bg-indigo-50"
              @click="startCorrection(d)"
            >
              <Pencil class="h-3 w-3" /> Как надо
            </button>
          </div>

          <!-- correction form -->
          <div v-if="correctingId === d.run_id" class="space-y-2 border-t border-indigo-100 bg-indigo-50/30 px-5 py-4">
            <input
              v-model="draft.situation"
              placeholder="Ситуация (когда так отвечать)"
              class="w-full rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm outline-none focus:border-indigo-400"
            >
            <textarea
              v-model="draft.phrase"
              rows="2"
              placeholder="Как надо ответить (фраза эксперта). Пусто — отметить как пробел."
              class="w-full resize-none rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm outline-none focus:border-indigo-400"
            />
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div class="flex overflow-hidden rounded-lg border border-slate-200">
                <button
                  v-for="lvl in levels"
                  :key="lvl"
                  type="button"
                  class="px-2 py-1 text-[10px] font-semibold transition-colors"
                  :class="draft.level === lvl ? levelActiveClass(lvl) : 'bg-white text-slate-400 hover:bg-slate-50'"
                  @click="draft.level = lvl"
                >
                  {{ lvl }}
                </button>
              </div>
              <div class="flex items-center gap-2">
                <button
                  type="button"
                  class="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50"
                  @click="cancelCorrection"
                >
                  Отмена
                </button>
                <button
                  type="button"
                  :disabled="savingCorrection || !draft.situation.trim()"
                  class="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-indigo-700 disabled:opacity-50"
                  @click="submitCorrection(d)"
                >
                  <Loader2 v-if="savingCorrection" class="h-3.5 w-3.5 animate-spin" />
                  В навык
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </AgentPageShell>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute } from '#app'
import { ArrowLeft, Inbox, Loader2, Pencil, RefreshCw } from 'lucide-vue-next'
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import { useExpertSkills } from '~/composables/useExpertSkills'
import { useToast } from '~/composables/useToast'
import type { ReviewDialog, SkillPhraseLevel } from '~/types/scriptFlow'

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth',
})

const route = useRoute()
const agentId = route.params.id as string
const skillId = route.params.skillId as string
const { getReviewDialogs, addReviewCorrection } = useExpertSkills(agentId)
const { success: toastSuccess, error: toastError } = useToast()

const levels: SkillPhraseLevel[] = ['пример', 'дословно', 'обязательно']
const marks = [
  { key: 'ok', label: '✓ Верно', active: 'bg-emerald-500 text-white' },
  { key: 'generic', label: 'Ушёл в генерик', active: 'bg-amber-500 text-white' },
  { key: 'overpushed', label: 'Пережал', active: 'bg-rose-500 text-white' },
] as const

const dialogs = ref<ReviewDialog[]>([])
const hasServiceLink = ref(true)
const loading = ref(true)
const markState = reactive<Record<string, string>>({})

const load = async () => {
  loading.value = true
  try {
    const res = await getReviewDialogs(skillId)
    dialogs.value = res.dialogs
    hasServiceLink.value = res.has_service_link
  } catch (err: unknown) {
    toastError(err instanceof Error ? err.message : 'Не удалось загрузить диалоги')
  } finally {
    loading.value = false
  }
}

const setMark = (d: ReviewDialog, mark: string) => {
  markState[d.run_id] = markState[d.run_id] === mark ? '' : mark
}

// ── Правка ────────────────────────────────────────────────────────────────────
const correctingId = ref<string | null>(null)
const savingCorrection = ref(false)
const draft = reactive<{ situation: string; phrase: string; level: SkillPhraseLevel }>({
  situation: '',
  phrase: '',
  level: 'пример',
})

const startCorrection = (d: ReviewDialog) => {
  correctingId.value = d.run_id
  draft.situation = d.input.slice(0, 120)
  draft.phrase = ''
  draft.level = 'пример'
}
const cancelCorrection = () => {
  correctingId.value = null
}

const submitCorrection = async (d: ReviewDialog) => {
  if (!draft.situation.trim()) return
  savingCorrection.value = true
  try {
    await addReviewCorrection(skillId, {
      situation: draft.situation.trim(),
      trigger_when: d.input,
      phrase: draft.phrase.trim() || null,
      level: draft.level,
      mark: markState[d.run_id] || null,
    })
    toastSuccess(draft.phrase.trim() ? 'Обработка добавлена в навык' : 'Пробел добавлен в навык')
    correctingId.value = null
  } catch (err: unknown) {
    toastError(err instanceof Error ? err.message : 'Не удалось сохранить правку')
  } finally {
    savingCorrection.value = false
  }
}

const levelActiveClass = (lvl: SkillPhraseLevel) => {
  if (lvl === 'обязательно') return 'bg-rose-500 text-white'
  if (lvl === 'дословно') return 'bg-indigo-500 text-white'
  return 'bg-slate-600 text-white'
}

onMounted(load)
</script>
