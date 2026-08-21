<template>
  <AgentPageShell title="Эксперт" :hide-actions="true" :contained="true">
    <div class="max-w-full space-y-4">
      <!-- Шапка: статус стиль-слоя -->
      <div class="flex flex-wrap items-center justify-between gap-3">
        <p class="text-sm text-muted-foreground">
          Стиль, фразы и опыт — всё, чему вы научили агента
        </p>
        <span
          v-if="library"
          class="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] font-medium"
          :class="library.style_layer_enabled && library.in_style_layer_count > 0
            ? 'bg-green-50 text-green-700'
            : 'bg-amber-50 text-amber-700'"
        >
          <span
            class="h-1.5 w-1.5 rounded-full"
            :class="library.style_layer_enabled && library.in_style_layer_count > 0 ? 'bg-green-500' : 'bg-amber-500'"
          />
          {{ library.style_layer_enabled && library.in_style_layer_count > 0
            ? `голос эксперта звучит: ${library.in_style_layer_count} карточек в каждом ответе`
            : 'стиль-слой пока пуст — опубликуйте навык' }}
        </span>
      </div>

      <!-- Вкладки -->
      <div class="flex flex-wrap gap-1.5">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          type="button"
          class="rounded-xl px-3.5 py-1.5 text-sm transition-colors"
          :class="activeTab === tab.id
            ? 'bg-primary font-semibold text-primary-foreground'
            : 'border border-slate-100 bg-white text-slate-600 hover:bg-slate-50'"
          @click="activeTab = tab.id"
        >
          {{ tab.label }}
          <span
            v-if="tab.id === 'library' && library"
            class="ml-1 rounded-full px-1.5 text-xs"
            :class="activeTab === 'library' ? 'bg-white/20' : 'bg-slate-100 text-slate-500'"
          >{{ library.cards.length }}</span>
        </button>
      </div>

      <!-- Loading -->
      <div v-if="isLoading" class="flex justify-center py-12">
        <Loader2 class="h-8 w-8 animate-spin text-primary" />
      </div>

      <!-- Error -->
      <div
        v-else-if="error"
        class="flex items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
      >
        <span>{{ error }}</span>
        <button type="button" class="font-semibold underline" @click="loadAll">Повторить</button>
      </div>

      <template v-else>
        <!-- ═══ Библиотека ═══ -->
        <template v-if="activeTab === 'library'">
          <div
            v-if="!library || library.cards.length === 0"
            class="rounded-3xl border-2 border-dashed border-slate-100 bg-white p-12 text-center"
          >
            <div class="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-primary/5">
              <Quote class="h-8 w-8 text-primary/40" />
            </div>
            <h3 class="text-lg font-bold text-slate-900">Библиотека пуста</h3>
            <p class="mx-auto mt-2 max-w-md text-slate-500">
              Фразы и запреты появятся здесь из опубликованных навыков — наполните
              навык в чате с ассистентом и опубликуйте его.
            </p>
          </div>

          <template v-else>
            <div class="flex flex-wrap gap-1.5">
              <button
                v-for="chip in kindChips"
                :key="chip.id"
                type="button"
                class="rounded-full border px-3 py-1 text-xs transition-colors"
                :class="kindFilter === chip.id
                  ? 'border-slate-300 bg-white font-semibold text-slate-900'
                  : 'border-slate-100 bg-white text-slate-500 hover:bg-slate-50'"
                @click="kindFilter = chip.id"
              >
                {{ chip.label }} · {{ chip.count }}
              </button>
            </div>

            <div class="space-y-2">
              <div
                v-for="(card, i) in filteredCards"
                :key="i"
                class="rounded-2xl border border-slate-100 bg-white px-4 py-3 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]"
              >
                <div class="mb-1 flex flex-wrap items-center gap-2">
                  <span
                    class="rounded-md px-1.5 py-0.5 text-[9px] font-black uppercase tracking-wider"
                    :class="kindBadgeClass(card.kind)"
                  >{{ card.kind }}</span>
                  <span v-if="card.trigger" class="truncate text-[11px] text-slate-400">{{ card.trigger }}</span>
                  <span
                    class="ml-auto inline-flex shrink-0 items-center gap-1 text-[11px]"
                    :class="card.in_style_layer ? 'text-green-700' : 'text-slate-400'"
                  >
                    <Check v-if="card.in_style_layer" class="h-3 w-3" />
                    {{ card.in_style_layer ? 'звучит в ответах' : 'в справочнике (use_expert_skill)' }}
                  </span>
                </div>
                <p class="text-sm text-foreground">{{ card.kind === 'запрет' ? card.text : `«${card.text}»` }}</p>
              </div>
            </div>
          </template>
        </template>

        <!-- ═══ Проверка ═══ -->
        <template v-else-if="activeTab === 'review'">
          <div class="rounded-3xl border border-slate-100 bg-white p-5 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
            <h3 class="text-sm font-semibold text-foreground">Проверка ответов агента</h3>
            <p class="mt-1 text-xs text-muted-foreground">
              Эксперт смотрит реальные ответы и отмечает «так можно / так нельзя» с исправлением.
              Проверка живёт внутри навыка — выберите, по какому пройтись:
            </p>
            <div class="mt-3 space-y-2">
              <NuxtLink
                v-for="skill in publishedSkills"
                :key="skill.id"
                :to="`/agents/${agentId}/skills/${skill.id}/review`"
                class="flex items-center gap-3 rounded-2xl border border-slate-100 px-4 py-3 transition-colors hover:bg-slate-50"
              >
                <GraduationCap class="h-4 w-4 shrink-0 text-primary" />
                <span class="min-w-0 flex-1 truncate text-sm font-medium text-foreground">{{ skill.name || 'Навык' }}</span>
                <ChevronRight class="h-4 w-4 shrink-0 text-slate-300" />
              </NuxtLink>
              <p v-if="publishedSkills.length === 0" class="py-4 text-center text-sm text-slate-400">
                Опубликованных навыков нет — проверять пока нечего
              </p>
            </div>
          </div>
        </template>

        <!-- ═══ Журнал ═══ -->
        <template v-else-if="activeTab === 'log'">
          <div class="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div class="rounded-2xl bg-sky-50/60 px-4 py-3">
              <p class="text-[9px] font-black uppercase tracking-wider text-sky-600">В каждом ответе</p>
              <p class="mt-1 text-2xl font-black text-slate-900">{{ library?.in_style_layer_count ?? 0 }}</p>
              <p class="text-xs text-slate-500">фраз и запретов эксперта</p>
            </div>
            <div class="rounded-2xl bg-violet-50/60 px-4 py-3">
              <p class="text-[9px] font-black uppercase tracking-wider text-violet-600">Всего в библиотеке</p>
              <p class="mt-1 text-2xl font-black text-slate-900">{{ library?.cards.length ?? 0 }}</p>
              <p class="text-xs text-slate-500">из {{ library?.skills_published ?? 0 }} опубликованных навыков</p>
            </div>
            <div class="rounded-2xl bg-emerald-50/60 px-4 py-3">
              <p class="text-[9px] font-black uppercase tracking-wider text-emerald-600">Объём стиль-слоя</p>
              <p class="mt-1 text-2xl font-black text-slate-900">{{ digestKilochars }}</p>
              <p class="text-xs text-slate-500">тыс. символов в промпте</p>
            </div>
          </div>
          <div class="rounded-3xl border border-slate-100 bg-white p-5 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
            <h3 class="text-sm font-semibold text-foreground">Как это работает</h3>
            <p class="mt-2 text-sm text-muted-foreground">
              Обязательные фразы и запреты из опубликованных навыков автоматически
              попадают в каждый ответ агента (стиль-слой). Образцы интонации агент
              подтягивает сам через справочник навыков, когда ситуация совпадает.
              Каждое изменение материала проверяется на тестовых диалогах — качество
              записи не должно проседать.
            </p>
          </div>
        </template>

        <!-- ═══ Обучение (тизер) ═══ -->
        <template v-else>
          <div class="rounded-3xl border border-slate-100 bg-white p-8 text-center shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
            <div class="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-primary/5">
              <UploadCloud class="h-7 w-7 text-primary/50" />
            </div>
            <h3 class="text-lg font-bold text-slate-900">Загрузка ваших диалогов — скоро</h3>
            <p class="mx-auto mt-2 max-w-lg text-sm text-slate-500">
              Здесь появится мастер: загрузите экспорт переписки (WhatsApp, Telegram),
              отметьте удачные ответы — и система превратит их в правила и фразы
              для библиотеки. Пока наполняйте навык в чате с ассистентом:
            </p>
            <NuxtLink
              :to="`/agents/${agentId}/skills`"
              class="mt-5 inline-flex items-center gap-1.5 rounded-xl bg-primary px-4 py-1.5 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
            >
              Открыть навыки
              <ChevronRight class="h-4 w-4" />
            </NuxtLink>
          </div>
        </template>
      </template>
    </div>
  </AgentPageShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  Check,
  ChevronRight,
  UploadCloud,
  GraduationCap,
  Loader2,
  Quote,
} from 'lucide-vue-next'
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import { useApiFetch } from '~/composables/useApiFetch'
import { useAuth } from '~/composables/useAuth'
import { getReadableErrorMessage } from '~/utils/api-errors'
import type { ExpertSkill } from '~/types/scriptFlow'

definePageMeta({
  middleware: 'auth',
})

type StyleCard = {
  kind: string
  trigger: string
  text: string
  skill_name: string
  in_style_layer: boolean
}

type StyleLibrary = {
  style_layer_enabled: boolean
  skills_published: number
  digest_chars: number
  in_style_layer_count: number
  counts: Record<string, number>
  cards: StyleCard[]
}

const route = useRoute()
const agentId = computed(() => route.params.id as string)
const apiFetch = useApiFetch()
const { token } = useAuth()
const authHeaders = () => ({ Authorization: `Bearer ${token.value}` })

const tabs = [
  { id: 'library', label: 'Библиотека' },
  { id: 'review', label: 'Проверка' },
  { id: 'log', label: 'Журнал' },
  { id: 'training', label: 'Обучение' },
] as const
type TabId = (typeof tabs)[number]['id']
const activeTab = ref<TabId>('library')

const library = ref<StyleLibrary | null>(null)
const skills = ref<ExpertSkill[]>([])
const isLoading = ref(false)
const error = ref<string | null>(null)

const loadAll = async () => {
  isLoading.value = true
  error.value = null
  try {
    const [lib, skillList] = await Promise.all([
      apiFetch<StyleLibrary>(`/agents/${agentId.value}/expert-skills/style-library`, { headers: authHeaders() }),
      apiFetch<ExpertSkill[]>(`/agents/${agentId.value}/expert-skills`, { headers: authHeaders() }),
    ])
    library.value = lib
    skills.value = skillList || []
  } catch (err: unknown) {
    error.value = getReadableErrorMessage(err, 'Не удалось загрузить данные эксперта')
  } finally {
    isLoading.value = false
  }
}

onMounted(loadAll)

const publishedSkills = computed(() => skills.value.filter((s) => s.status === 'published'))

const kindFilter = ref<string>('all')
const kindChips = computed(() => {
  const counts = library.value?.counts || {}
  const chips = [{ id: 'all', label: 'Все', count: library.value?.cards.length ?? 0 }]
  for (const [kind, count] of Object.entries(counts)) {
    chips.push({ id: kind, label: kindLabel(kind), count })
  }
  return chips
})

const filteredCards = computed(() => {
  const cards = library.value?.cards || []
  if (kindFilter.value === 'all') return cards
  return cards.filter((c) => c.kind === kindFilter.value)
})

const kindLabel = (kind: string) =>
  ({ обязательно: 'Обязательные', дословно: 'Дословные', пример: 'Образцы', запрет: 'Запреты' })[kind] || kind

const kindBadgeClass = (kind: string) =>
  ({
    обязательно: 'bg-violet-50/80 text-violet-700',
    дословно: 'bg-sky-50/80 text-sky-700',
    пример: 'bg-emerald-50/80 text-emerald-700',
    запрет: 'bg-rose-50/80 text-rose-700',
  })[kind] || 'bg-slate-50 text-slate-600'

const digestKilochars = computed(() =>
  ((library.value?.digest_chars ?? 0) / 1000).toFixed(1),
)
</script>
