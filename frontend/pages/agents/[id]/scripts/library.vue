<template>
  <AgentPageShell title="Библиотека знаний эксперта" :hide-actions="true" :contained="true">
    <div class="flex min-h-0 flex-1 flex-col gap-3">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <NuxtLink
          :to="`/agents/${agentId}/scripts`"
          class="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-muted"
        >
          ← К потокам
        </NuxtLink>
        <p class="text-xs text-muted-foreground">
          Общие сущности переиспользуются между потоками и попадают в граф знаний (LightRAG).
        </p>
      </div>

      <div class="flex flex-wrap gap-2">
        <button
          v-for="t in KG_ENTITY_TYPES"
          :key="t.value"
          type="button"
          class="rounded-md border px-3 py-1.5 text-xs"
          :class="activeType === t.value
            ? 'border-primary bg-primary/10 text-primary'
            : 'border-border hover:bg-muted'"
          @click="activeType = t.value"
        >
          {{ t.label }}
          <span class="ml-1 text-[10px] text-muted-foreground">{{ countByType[t.value] ?? 0 }}</span>
        </button>
      </div>

      <p class="text-xs text-muted-foreground">{{ activeHelper }}</p>

      <div
        v-if="activeType === 'motive'"
        class="flex flex-wrap items-center gap-2 rounded-md border border-border bg-muted/30 px-3 py-2"
      >
        <label class="inline-flex cursor-pointer items-center gap-2 text-xs">
          <input v-model="motiveOnlyNeedsWork" type="checkbox" class="h-4 w-4" />
          <span>Показывать только мотивы, которые нужно дополнить</span>
        </label>
      </div>

      <section class="grid min-h-0 flex-1 gap-3 lg:grid-cols-[1fr_360px]">
        <div class="min-h-0 overflow-auto rounded-lg border border-border bg-card p-3">
          <div v-if="loading" class="text-sm text-muted-foreground">Загрузка…</div>
          <div v-else-if="loadError" class="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm">
            {{ loadError }}
          </div>
          <div v-else-if="!filteredEntities.length" class="rounded-md border border-dashed border-border p-4 text-sm text-muted-foreground">
            Пока нет сущностей этого типа. Добавьте справа.
          </div>
          <ul v-else class="space-y-1.5">
            <li
              v-for="e in filteredEntities"
              :key="e.id"
              class="rounded-md border border-border p-2.5 hover:border-primary/60"
              :class="editingId === e.id ? 'border-primary bg-primary/5' : ''"
            >
              <div class="flex items-start justify-between gap-2">
                <div class="min-w-0 flex-1">
                  <div class="flex flex-wrap items-center gap-2">
                    <span class="truncate text-sm font-medium">{{ e.name }}</span>
                    <span
                      v-if="e.entity_type === 'motive'"
                      class="rounded-sm px-1.5 py-0.5 text-[10px]"
                      :class="motiveCompletenessBadgeClass(e)"
                    >
                      {{ motiveCompletenessLabel(e) }}
                    </span>
                    <span
                      v-if="e.usage_count > 0"
                      class="rounded-sm bg-primary/10 px-1.5 py-0.5 text-[10px] text-primary"
                    >
                      используется {{ e.usage_count }}×
                    </span>
                  </div>
                  <p v-if="e.description" class="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
                    {{ e.description }}
                  </p>

                  <template v-if="e.entity_type === 'motive'">
                    <p v-if="motiveSummary(e)" class="mt-1 text-[11px] leading-relaxed text-foreground/90">
                      {{ motiveSummary(e) }}
                    </p>
                    <div v-if="motiveMarkersPreview(e).length" class="mt-2 flex flex-wrap gap-1">
                      <span
                        v-for="marker in motiveMarkersPreview(e)"
                        :key="marker"
                        class="rounded-full border border-violet-200 bg-violet-50 px-2 py-0.5 text-[10px] text-violet-800"
                      >
                        {{ marker }}
                      </span>
                    </div>
                    <p v-if="motiveHowToWork(e)" class="mt-2 text-[10px] leading-relaxed text-muted-foreground">
                      <span class="font-medium text-foreground">Как работать:</span>
                      {{ motiveHowToWork(e) }}
                    </p>
                  </template>
                </div>
                <div class="flex shrink-0 gap-1">
                  <button
                    type="button"
                    class="rounded border border-border px-2 py-1 text-xs hover:bg-muted"
                    @click="startEdit(e)"
                  >
                    Ред.
                  </button>
                  <button
                    type="button"
                    class="rounded border border-destructive/40 px-2 py-1 text-xs text-destructive hover:bg-destructive/10 disabled:opacity-50"
                    :disabled="e.usage_count > 0"
                    :title="e.usage_count > 0 ? 'Сначала отвяжите от узлов' : 'Удалить'"
                    @click="handleDelete(e)"
                  >
                    Удалить
                  </button>
                </div>
              </div>
            </li>
          </ul>
        </div>

        <aside class="rounded-lg border border-border bg-card p-3">
          <h3 class="mb-2 text-sm font-semibold">
            {{ editingId ? 'Редактировать сущность' : `Добавить: ${activeLabel}` }}
          </h3>

          <form class="space-y-2" @submit.prevent="handleSubmit">
            <div>
              <label class="mb-1 block text-xs font-medium text-muted-foreground">Название</label>
              <input
                v-model="formName"
                type="text"
                required
                class="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                :placeholder="namePlaceholder"
              />
            </div>

            <div>
              <label class="mb-1 block text-xs font-medium text-muted-foreground">Описание</label>
              <textarea
                v-model="formDescription"
                rows="4"
                class="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                :placeholder="descPlaceholder"
              />
            </div>

            <div v-if="activeType === 'objection'">
              <label class="mb-1 block text-xs font-medium text-muted-foreground">Категория (BANT-T)</label>
              <select
                v-model="formBantCategory"
                class="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
              >
                <option value="">—</option>
                <option v-for="c in BANT_T_CATEGORIES" :key="c.value" :value="c.value">
                  {{ c.label }}
                </option>
              </select>
            </div>

            <div v-if="activeType === 'motive'" class="rounded-md border border-dashed border-border p-2.5 text-xs text-muted-foreground">
              Опишите мотив так, чтобы эксперт мог быстро его распознать и правильно отработать в разговоре: в чём его смысл, по каким фразам он слышен и как лучше строить ответ.
            </div>

            <template v-if="activeType === 'motive'">
              <div>
                <label class="mb-1 block text-xs font-medium text-muted-foreground">Суть мотива</label>
                <textarea
                  v-model="formMotiveSummary"
                  rows="3"
                  class="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                  placeholder="Коротко объясните, что именно пациент хочет проверить или почувствовать через этот мотив"
                />
              </div>

              <div>
                <label class="mb-1 block text-xs font-medium text-muted-foreground">Словесные маркеры</label>
                <textarea
                  v-model="formMotiveMarkers"
                  rows="5"
                  class="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                  placeholder="Каждый маркер с новой строки: что говорит пациент, когда проявляется этот мотив"
                />
              </div>

              <div>
                <label class="mb-1 block text-xs font-medium text-muted-foreground">Как работать с мотивом</label>
                <textarea
                  v-model="formMotiveHowToWork"
                  rows="4"
                  class="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                  placeholder="Опишите, на чём строить аргументацию и какие смыслы должны усиливать доверие"
                />
              </div>

              <div>
                <label class="mb-1 block text-xs font-medium text-muted-foreground">Пример формулировки</label>
                <textarea
                  v-model="formMotiveExample"
                  rows="5"
                  class="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                  placeholder="Пример ответа, который помогает правильно отработать этот мотив"
                />
              </div>
            </template>

            <div v-if="activeType === 'constraint'">
              <label class="inline-flex cursor-pointer items-center gap-2 text-xs">
                <input v-model="formIsHardConstraint" type="checkbox" class="h-4 w-4" />
                <span>Жёсткое ограничение (LLM нельзя нарушать ни при каких условиях)</span>
              </label>
              <p class="mt-1 text-[11px] text-muted-foreground">
                Если не отмечено — ограничение воспринимается как гайдлайн (стиль, тон), а не запрет.
              </p>
            </div>

            <div v-if="submitError" class="rounded-md border border-destructive/40 bg-destructive/10 px-2 py-1.5 text-xs">
              {{ submitError }}
            </div>

            <div class="flex gap-2 pt-1">
              <button
                type="submit"
                class="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-50"
                :disabled="submitting || !formName.trim()"
              >
                {{ editingId ? 'Сохранить' : 'Добавить' }}
              </button>
              <button
                v-if="editingId"
                type="button"
                class="rounded-md border border-border px-3 py-1.5 text-sm hover:bg-muted"
                @click="resetForm"
              >
                Отмена
              </button>
            </div>
          </form>
        </aside>
      </section>
    </div>
  </AgentPageShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import { useAgentKgEntities } from '~/composables/useAgentKgEntities'
import {
  BANT_T_CATEGORIES,
  KG_ENTITY_TYPES,
  type AgentKgEntity,
  type AgentKgEntityType,
  type MotiveMeta,
} from '~/types/kgEntities'
import { getReadableErrorMessage } from '~/utils/api-errors'

definePageMeta({ middleware: 'auth' })

const route = useRoute()
const agentId = route.params.id as string

const { entities, isLoading, error: listError, fetchEntities, createEntity, updateEntity, deleteEntity } =
  useAgentKgEntities(agentId)

const activeType = ref<AgentKgEntityType>('motive')
const loading = computed(() => isLoading.value)
const loadError = computed(() => listError.value)

const filteredEntities = computed(() => {
  const base = entities.value.filter((e) => e.entity_type === activeType.value)
  if (activeType.value !== 'motive')
    return base

  const filtered = motiveOnlyNeedsWork.value
    ? base.filter(e => motiveCompletenessScore(e) < 4)
    : base

  return [...filtered].sort((a, b) => {
    const sa = motiveCompletenessScore(a)
    const sb = motiveCompletenessScore(b)
    if (sa !== sb)
      return sa - sb
    return a.name.localeCompare(b.name, 'ru')
  })
})

const countByType = computed<Record<string, number>>(() => {
  const acc: Record<string, number> = {}
  for (const e of entities.value) acc[e.entity_type] = (acc[e.entity_type] || 0) + 1
  return acc
})

const activeLabel = computed(
  () => KG_ENTITY_TYPES.find((t) => t.value === activeType.value)?.label ?? '',
)
const activeHelper = computed(
  () => KG_ENTITY_TYPES.find((t) => t.value === activeType.value)?.helper ?? '',
)

const motiveMetaOf = (e: AgentKgEntity): MotiveMeta =>
  (e.meta ?? {}) as MotiveMeta

const motiveSummary = (e: AgentKgEntity): string =>
  String(motiveMetaOf(e).summary ?? '').trim()

const motiveMarkers = (e: AgentKgEntity): string[] =>
  Array.isArray(motiveMetaOf(e).verbal_markers)
    ? motiveMetaOf(e).verbal_markers!.map(x => String(x).trim()).filter(Boolean)
    : []

const motiveMarkersPreview = (e: AgentKgEntity): string[] =>
  motiveMarkers(e).slice(0, 3)

const motiveHowToWork = (e: AgentKgEntity): string =>
  String(motiveMetaOf(e).how_to_work ?? '').trim()

const motiveCompletenessScore = (e: AgentKgEntity): number => {
  const meta = motiveMetaOf(e)
  let score = 0
  if (String(meta.summary ?? '').trim()) score += 1
  if (Array.isArray(meta.verbal_markers) && meta.verbal_markers.some(x => String(x).trim())) score += 1
  if (String(meta.how_to_work ?? '').trim()) score += 1
  if (String(meta.example_response ?? '').trim()) score += 1
  return score
}

const motiveCompletenessLabel = (e: AgentKgEntity): string => {
  const score = motiveCompletenessScore(e)
  if (score >= 4) return 'Заполнен'
  if (score >= 2) return 'Частично заполнен'
  return 'Нужно дополнить'
}

const motiveCompletenessBadgeClass = (e: AgentKgEntity): string => {
  const score = motiveCompletenessScore(e)
  if (score >= 4) return 'bg-emerald-50 text-emerald-700'
  if (score >= 2) return 'bg-amber-50 text-amber-700'
  return 'bg-slate-100 text-slate-600'
}

const namePlaceholders: Record<AgentKgEntityType, string> = {
  motive: 'Например: страх обесценивания',
  argument: 'Например: стоимость часа врача',
  proof: 'Например: кейс доктора Ивановой',
  objection: 'Например: «дорого»',
  constraint: 'Например: не обещать результат',
  outcome: 'Например: запись подтверждена',
}
const descPlaceholders: Record<AgentKgEntityType, string> = {
  motive: 'Чего боится клиент и что его мотивирует — короткое описание боли или драйвера',
  argument: 'Рациональный или эмоциональный довод, которым закрываем возражение',
  proof: 'Конкретный факт/кейс/статистика/отзыв',
  objection: 'Что говорит клиент + почему (budget/trust/…)',
  constraint: 'Что строго запрещено делать/говорить',
  outcome: 'Описание итога ветки диалога',
}
const namePlaceholder = computed(() => namePlaceholders[activeType.value])
const descPlaceholder = computed(() => descPlaceholders[activeType.value])

const editingId = ref<string | null>(null)
const formName = ref('')
const formDescription = ref('')
const formBantCategory = ref('')
const formIsHardConstraint = ref(false)
const formMotiveSummary = ref('')
const formMotiveMarkers = ref('')
const formMotiveHowToWork = ref('')
const formMotiveExample = ref('')
const motiveOnlyNeedsWork = ref(false)
const submitting = ref(false)
const submitError = ref<string | null>(null)

const resetForm = () => {
  editingId.value = null
  formName.value = ''
  formDescription.value = ''
  formBantCategory.value = ''
  formIsHardConstraint.value = false
  formMotiveSummary.value = ''
  formMotiveMarkers.value = ''
  formMotiveHowToWork.value = ''
  formMotiveExample.value = ''
  submitError.value = null
}

const startEdit = (e: AgentKgEntity) => {
  editingId.value = e.id
  formName.value = e.name
  formDescription.value = e.description ?? ''
  const meta = (e.meta ?? {}) as Record<string, unknown>
  formBantCategory.value = String(meta.bant_category ?? '')
  formIsHardConstraint.value = meta.is_hard === true
  const motiveMeta = meta as MotiveMeta
  formMotiveSummary.value = String(motiveMeta.summary ?? '')
  formMotiveMarkers.value = Array.isArray(motiveMeta.verbal_markers)
    ? motiveMeta.verbal_markers.map(x => String(x).trim()).filter(Boolean).join('\n')
    : ''
  formMotiveHowToWork.value = String(motiveMeta.how_to_work ?? '')
  formMotiveExample.value = String(motiveMeta.example_response ?? '')
  submitError.value = null
}

const handleSubmit = async () => {
  submitting.value = true
  submitError.value = null
  try {
    const meta: Record<string, unknown> = {}
    if (activeType.value === 'motive') {
      meta.summary = formMotiveSummary.value.trim() || undefined
      meta.verbal_markers = formMotiveMarkers.value
        .split('\n')
        .map(x => x.trim())
        .filter(Boolean)
      meta.how_to_work = formMotiveHowToWork.value.trim() || undefined
      meta.example_response = formMotiveExample.value.trim() || undefined
    }
    if (activeType.value === 'objection' && formBantCategory.value) {
      meta.bant_category = formBantCategory.value
    }
    if (activeType.value === 'constraint') {
      meta.is_hard = formIsHardConstraint.value
    }
    if (editingId.value) {
      await updateEntity(editingId.value, {
        name: formName.value.trim(),
        description: formDescription.value.trim() || null,
        meta,
      })
    } else {
      await createEntity({
        entity_type: activeType.value,
        name: formName.value.trim(),
        description: formDescription.value.trim() || null,
        meta,
      })
    }
    resetForm()
    await fetchEntities()
  } catch (err: unknown) {
    submitError.value = getReadableErrorMessage(err, 'Не удалось сохранить сущность')
  } finally {
    submitting.value = false
  }
}

const handleDelete = async (e: AgentKgEntity) => {
  if (!confirm(`Удалить «${e.name}»?`)) return
  try {
    await deleteEntity(e.id)
    if (editingId.value === e.id) resetForm()
    await fetchEntities()
  } catch (err: unknown) {
    submitError.value = getReadableErrorMessage(err, 'Не удалось удалить')
  }
}

watch(activeType, () => resetForm())

onMounted(() => {
  fetchEntities()
})
</script>
