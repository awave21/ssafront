<template>
  <div class="space-y-3">
    <div class="space-y-1.5 rounded-xl border border-border/80 bg-background/95 px-3 py-3 shadow-sm">
      <p class="text-[11px] font-semibold text-foreground">
        Смысловые связи шага
      </p>
      <p class="text-[11px] leading-relaxed text-muted-foreground">
        Покажите, на какие знания опирается этот шаг с точки зрения эксперта:
        какой мотив он раскрывает, какими аргументами подкрепляется, какие возражения снимает
        и к какому итогу ведёт.
      </p>
      <p class="text-[11px] leading-relaxed text-muted-foreground">
        Сами элементы добавляются в
        <a :href="libraryHref" target="_blank" class="font-medium underline">библиотеке знаний</a>,
        а здесь вы связываете их с конкретным шагом сценария.
      </p>
    </div>

    <div v-for="bucket in BUCKETS" :key="bucket.key" class="space-y-1.5">
      <div class="flex items-center justify-between">
        <div class="min-w-0">
          <label class="insp-label">
            {{ bucket.label }}
            <span class="ml-1 text-[10px] text-muted-foreground">
              ({{ selected(bucket.type).length }})
            </span>
          </label>
          <p class="mt-0.5 text-[10px] leading-relaxed text-muted-foreground">
            {{ bucket.description }}
          </p>
        </div>
        <span v-if="!optionsByType[bucket.type].length" class="shrink-0 text-[9px] text-muted-foreground">
          добавьте в библиотеке
        </span>
      </div>

      <div v-if="optionsByType[bucket.type].length" class="flex flex-wrap gap-1.5">
        <button
          v-for="opt in optionsByType[bucket.type]"
          :key="opt.id"
          type="button"
          class="rounded-md border px-2 py-0.5 text-[10px]"
          :class="isSelected(bucket.type, opt.id)
            ? 'border-primary bg-primary/10 text-primary'
            : 'border-border hover:bg-muted'"
          :title="opt.description || ''"
          @click="toggleKgLink(bucket.key, opt.id)"
        >
          {{ opt.name }}
        </button>
      </div>

      <div
        v-if="bucket.type === 'motive' && selectedMotiveCards.length"
        class="space-y-2 rounded-xl border border-violet-200/70 bg-violet-50/60 px-3 py-3 shadow-sm dark:bg-violet-950/15"
      >
        <p class="text-[10px] font-semibold uppercase tracking-wide text-violet-700">
          Подсказки по выбранным мотивам
        </p>
        <div
          v-for="card in selectedMotiveCards"
          :key="card.id"
          class="rounded-lg border border-violet-200/70 bg-background/95 px-3 py-2.5 shadow-sm"
        >
          <p class="text-[11px] font-semibold text-foreground">{{ card.name }}</p>
          <p class="mt-1 text-[10px] leading-relaxed text-muted-foreground">
            {{ card.summary }}
          </p>

          <div v-if="card.markers.length" class="mt-2 space-y-1">
            <p class="text-[10px] font-medium text-foreground">На что обратить внимание в речи пациента</p>
            <div class="flex flex-wrap gap-1">
              <span
                v-for="marker in card.markers"
                :key="marker"
                class="rounded-full border border-violet-200 bg-violet-50 px-2 py-0.5 text-[10px] text-violet-800"
              >
                {{ marker }}
              </span>
            </div>
          </div>

          <div class="mt-2 grid gap-2 lg:grid-cols-2">
            <div class="rounded-md bg-background/85 px-2.5 py-2 shadow-sm">
              <p class="text-[10px] font-medium text-foreground">Как работать с мотивом</p>
              <p class="mt-1 text-[10px] leading-relaxed text-muted-foreground">
                {{ card.howToWork }}
              </p>
            </div>
            <div class="rounded-md bg-background/85 px-2.5 py-2 shadow-sm">
              <p class="text-[10px] font-medium text-foreground">Пример формулировки</p>
              <p class="mt-1 text-[10px] leading-relaxed text-muted-foreground">
                {{ card.example }}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showOutcome" class="space-y-1.5">
      <div>
        <label class="insp-label">К какому итогу ведёт этот шаг</label>
        <p class="mt-0.5 text-[10px] leading-relaxed text-muted-foreground">
          Укажите результат, к которому должен вести этот фрагмент разговора.
        </p>
      </div>
      <select
        :value="outcomeId ?? ''"
        class="insp-input"
        @change="onOutcomeChange(($event.target as HTMLSelectElement).value)"
      >
        <option value="">—</option>
        <option v-for="opt in optionsByType.outcome" :key="opt.id" :value="opt.id">
          {{ opt.name }}
        </option>
      </select>
    </div>

    <InspectorHelperHints />
  </div>
</template>

<script setup lang="ts">
import { computed, inject, type Ref } from 'vue'
import { useRoute } from 'vue-router'
import { SCRIPT_FLOW_INSPECTOR_KEY } from '~/composables/useScriptFlowInspectorModel'
import { SCRIPT_FLOW_MOTIVE_PROFILES } from '~/constants/scriptFlowMotiveProfiles'
import type { MotiveMeta } from '~/types/kgEntities'
import InspectorHelperHints from './InspectorHelperHints.vue'

type KgOption = {
  id: string
  name: string
  description?: string | null
  entity_type: string
  meta?: Record<string, unknown>
}

const props = defineProps<{
  showOutcome?: boolean
  includeConstraint?: boolean
}>()

const m = inject(SCRIPT_FLOW_INSPECTOR_KEY)!
const {
  localMotiveIds,
  localArgumentIds,
  localProofIds,
  localObjectionIds,
  localConstraintIds,
  localOutcomeId,
  toggleKgLink,
  setOutcomeEntity,
} = m

const kgEntityOptions = inject<Ref<KgOption[]>>('flowKgEntityOptions', { value: [] } as unknown as Ref<KgOption[]>)

const optionsByType = computed<Record<string, KgOption[]>>(() => {
  const acc: Record<string, KgOption[]> = {
    motive: [], argument: [], proof: [], objection: [], constraint: [], outcome: [],
  }
  for (const e of kgEntityOptions.value) {
    if (acc[e.entity_type]) acc[e.entity_type].push(e)
  }
  return acc
})

const normalizeMotiveKey = (value: string): string =>
  value
    .toLowerCase()
    .replace(/ё/g, 'е')
    .replace(/[()]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()

const resolveMotiveProfile = (name: string, description?: string | null) => {
  const hay = `${normalizeMotiveKey(name)} ${normalizeMotiveKey(description || '')}`
  return SCRIPT_FLOW_MOTIVE_PROFILES.find((profile) => {
    const title = normalizeMotiveKey(profile.title)
    if (hay.includes(title))
      return true
    if (profile.key === 'location_visualization')
      return hay.includes('локация') || hay.includes('визуализац')
    if (profile.key === 'recommendation')
      return hay.includes('рекомендац')
    return hay.includes(profile.key)
  }) || null
}

const selectedMotiveCards = computed(() =>
  optionsByType.value.motive
    .filter((opt) => localMotiveIds.value.includes(opt.id))
    .map((opt) => {
      const profile = resolveMotiveProfile(opt.name, opt.description)
      const meta = (opt.meta || {}) as MotiveMeta
      const fallback = (opt.description || '').trim()
      return {
        id: opt.id,
        name: opt.name,
        summary: String(meta.summary ?? '').trim()
          || profile?.summary
          || fallback
          || 'Опишите, почему этот мотив важен для пациента и как он проявляется в разговоре.',
        markers: Array.isArray(meta.verbal_markers)
          ? meta.verbal_markers.map(x => String(x).trim()).filter(Boolean)
          : (profile?.markers || []),
        howToWork: String(meta.how_to_work ?? '').trim()
          || profile?.howToWork
          || 'Добавьте в описание мотива словесные маркеры и правило аргументации, чтобы эксперт быстрее ориентировался.',
        example: String(meta.example_response ?? '').trim()
          || profile?.example
          || 'Добавьте пример формулировки в библиотеке знаний, и он будет служить опорой для этого шага.',
      }
    }),
)

const BUCKETS_FULL = [
  {
    key: 'motive',
    type: 'motive',
    label: 'На какой мотив опирается шаг',
    description: 'Почему клиенту вообще может быть важен этот разговорный ход.',
  },
  {
    key: 'argument',
    type: 'argument',
    label: 'Какие аргументы здесь используются',
    description: 'Какие мысли, выгоды или объяснения эксперт хочет донести в этом шаге.',
  },
  {
    key: 'proof',
    type: 'proof',
    label: 'Чем это можно подтвердить',
    description: 'Факты, примеры, кейсы или подтверждения, которые усиливают этот шаг.',
  },
  {
    key: 'objection',
    type: 'objection',
    label: 'Какие возражения шаг помогает снять',
    description: 'Какие сомнения или барьеры клиента закрывает этот шаг.',
  },
  {
    key: 'constraint',
    type: 'constraint',
    label: 'Какие ограничения нужно учитывать',
    description: 'Ограничения, рамки или условия, которые важно помнить в этом месте сценария.',
  },
] as const

const BUCKETS = computed(() =>
  props.includeConstraint === false
    ? BUCKETS_FULL.filter((b) => b.key !== 'constraint')
    : [...BUCKETS_FULL],
)

const selected = (type: string): string[] => {
  switch (type) {
    case 'motive':     return localMotiveIds.value
    case 'argument':   return localArgumentIds.value
    case 'proof':      return localProofIds.value
    case 'objection':  return localObjectionIds.value
    case 'constraint': return localConstraintIds.value
    default:           return []
  }
}

const isSelected = (type: string, id: string): boolean => selected(type).includes(id)

const outcomeId = computed(() => localOutcomeId.value)

const onOutcomeChange = (v: string) => {
  setOutcomeEntity(v || null)
}

const route = useRoute()
const libraryHref = computed(() => `/agents/${route.params.id}/scripts/library`)
</script>

<style src="./inspector-panel.css"></style>
