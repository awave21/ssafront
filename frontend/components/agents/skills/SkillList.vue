<template>
  <div class="max-w-full space-y-6">
    <!-- Header: create + import + trash + stats/search -->
    <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
      <div class="flex flex-wrap items-center gap-2">
        <button
          type="button"
          class="inline-flex h-10 shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-xl bg-primary px-4 text-sm font-bold text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
          :disabled="creating"
          @click="handleCreate"
        >
          <Plus class="h-4 w-4" />
          {{ creating ? 'Создаём…' : 'Создать навык' }}
        </button>
        <button
          type="button"
          class="inline-flex h-10 shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-xl border border-slate-200 bg-white px-3 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50 disabled:opacity-50"
          :disabled="importing"
          title="Создать навык из .md-файла — содержимое разберётся в опыт эксперта"
          @click="mdInput?.click()"
        >
          <UploadCloud class="h-4 w-4" />
          {{ importing ? 'Импорт…' : 'Импорт .md' }}
        </button>
        <input ref="mdInput" type="file" accept=".md,.markdown,.txt" class="hidden" @change="handleImportMd">
        <button
          type="button"
          class="inline-flex h-10 shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-xl border border-slate-200 bg-white px-3 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50"
          @click="openTrash"
        >
          <Trash2 class="h-4 w-4" />
          Корзина
          <span v-if="trashCount > 0" class="rounded-full bg-slate-100 px-1.5 text-xs font-bold text-slate-500">{{ trashCount }}</span>
        </button>
      </div>

      <div v-if="skills.length > 0" class="flex w-full flex-wrap items-center gap-2 lg:w-auto lg:justify-end">
        <div class="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600">
          <span class="font-medium text-slate-900">Навыков:</span>
          <span>{{ skills.length }}</span>
        </div>
        <div class="inline-flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
          <span class="font-medium">Опубликовано:</span>
          <span>{{ publishedCount }}</span>
        </div>
        <div class="relative min-w-0 grow sm:grow-0">
          <Search class="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Поиск по навыку или услуге…"
            class="h-10 w-full min-w-0 rounded-xl border border-slate-200 bg-slate-50 py-2 pl-9 pr-4 text-sm outline-none transition-all duration-300 focus:border-primary focus:bg-white focus:ring-4 focus:ring-primary/10 sm:w-80"
          >
        </div>
      </div>
    </div>

    <!-- Как создать навык -->
    <div class="overflow-hidden rounded-2xl border border-primary/15 bg-primary/5">
      <button
        type="button"
        class="flex w-full items-center gap-3 px-4 py-3 text-left text-sm text-slate-700"
        @click="showGuide = !showGuide"
      >
        <Sparkles class="h-4 w-4 shrink-0 text-primary" />
        <span class="flex-1">
          <b>Навык — продолжение эксперта</b> на тему: как вести пациента и какими словами.
          Создайте его в любой модели (ChatGPT, Claude…) и загрузите файлом.
        </span>
        <component :is="showGuide ? ChevronsDownUp : ChevronsUpDown" class="h-4 w-4 shrink-0 text-primary/60" />
      </button>

      <div v-if="showGuide" class="border-t border-primary/15 px-4 py-4">
        <div class="grid gap-3 sm:grid-cols-3">
          <div class="rounded-xl bg-white px-3 py-2.5">
            <div class="text-[9px] font-black uppercase tracking-wider text-primary">Шаг 1</div>
            <p class="mt-1 text-xs text-slate-600">Скопируйте подсказку ниже, вставьте в любую модель вместе со своими примерами ответов.</p>
          </div>
          <div class="rounded-xl bg-white px-3 py-2.5">
            <div class="text-[9px] font-black uppercase tracking-wider text-primary">Шаг 2</div>
            <p class="mt-1 text-xs text-slate-600">Модель вернёт текст навыка — сохраните его как файл <b>.md</b>.</p>
          </div>
          <div class="rounded-xl bg-white px-3 py-2.5">
            <div class="text-[9px] font-black uppercase tracking-wider text-primary">Шаг 3</div>
            <p class="mt-1 text-xs text-slate-600">Нажмите <b>«Импорт .md»</b> вверху — навык появится черновиком, проверьте и опубликуйте.</p>
          </div>
        </div>

        <div class="mt-3 overflow-hidden rounded-xl border border-slate-200 bg-white">
          <div class="flex items-center justify-between border-b border-slate-100 bg-slate-50 px-3 py-2">
            <span class="text-[11px] font-bold text-slate-600">Подсказка для модели — скопируйте</span>
            <button
              type="button"
              class="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-600 hover:bg-slate-50"
              @click="copyGuidePrompt"
            >
              <component :is="guideCopied ? Check : Copy" class="h-3.5 w-3.5" />
              {{ guideCopied ? 'Скопировано' : 'Копировать' }}
            </button>
          </div>
          <pre class="max-h-64 overflow-auto whitespace-pre-wrap px-3 py-3 text-[11px] leading-relaxed text-slate-700">{{ skillPrompt }}</pre>
        </div>

        <p class="mt-2 flex items-start gap-1.5 text-[11px] leading-relaxed text-amber-700">
          <ShieldAlert class="mt-0.5 h-3.5 w-3.5 shrink-0" />
          Не вписывайте в навык точные цены, имена врачей и даты — они меняются, агент берёт их из системы. Навык — про манеру и порядок разговора.
        </p>
      </div>
    </div>

    <!-- Error -->
    <div
      v-if="error"
      class="flex items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
    >
      <span>{{ error }}</span>
      <button type="button" class="font-semibold underline" @click="fetchSkills">Повторить</button>
    </div>

    <!-- Loading -->
    <div v-if="isLoading && !skills.length" class="flex justify-center py-12">
      <Loader2 class="h-8 w-8 animate-spin text-primary" />
    </div>

    <!-- Empty state -->
    <div
      v-else-if="skills.length === 0"
      class="rounded-3xl border-2 border-dashed border-slate-100 bg-white p-12 text-center"
    >
      <div class="mx-auto max-w-md">
        <div class="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-primary/5">
          <Sparkles class="h-8 w-8 text-primary/40" />
        </div>
        <h3 class="text-lg font-bold text-slate-900">Навыков пока нет</h3>
        <p class="mb-6 mt-2 text-slate-500">
          Создайте первый навык, привяжите его к услуге и наполните опытом эксперта —
          ситуациями, фразами и обработками возражений.
        </p>
        <button
          type="button"
          class="rounded-xl bg-primary px-6 py-3 text-sm font-bold text-primary-foreground transition-colors hover:bg-primary/90"
          :disabled="creating"
          @click="handleCreate"
        >
          Создать первый навык
        </button>
      </div>
    </div>

    <!-- No results -->
    <div
      v-else-if="filteredCards.length === 0"
      class="rounded-3xl border border-slate-100 bg-white p-8 text-center"
    >
      <p class="text-slate-500">Ничего не найдено по запросу «{{ searchQuery }}»</p>
    </div>

    <!-- Cards grid -->
    <div v-else class="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <div
        v-for="card in filteredCards"
        :key="card.skill.id"
        class="group relative min-w-0 cursor-pointer overflow-hidden rounded-3xl border border-slate-100 bg-white p-5 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-shadow duration-500 hover:shadow-[0_20px_40px_-12px_rgba(0,0,0,0.08)]"
        @click="openSkill(card.skill.id)"
      >
        <div
          class="pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full bg-primary/5 transition-transform duration-700 group-hover:scale-150"
        />

        <!-- Head -->
        <div class="flex items-start justify-between gap-3">
          <div class="flex min-w-0 flex-1 items-start gap-3">
            <div class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-primary/5 transition-colors group-hover:bg-primary/10">
              <Sparkles class="h-5 w-5 text-primary" />
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2">
                <h4 class="truncate text-base font-bold text-slate-900">{{ card.skill.name }}</h4>
                <span
                  class="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold"
                  :class="card.skill.status === 'published'
                    ? 'border border-emerald-200 bg-emerald-50 text-emerald-700'
                    : 'border border-slate-200 bg-slate-100 text-slate-600'"
                >
                  {{ card.skill.status === 'published' ? 'Опубликован' : 'Черновик' }}
                </span>
              </div>

              <!-- linked services -->
              <div class="mt-1.5 flex flex-wrap items-center gap-1">
                <span
                  v-for="name in card.serviceNames.slice(0, 3)"
                  :key="name"
                  class="inline-flex max-w-[180px] items-center gap-1 rounded-2xl bg-primary/5 px-2 py-0.5 text-[11px] font-medium text-primary"
                >
                  <Stethoscope class="h-3 w-3 shrink-0" />
                  <span class="truncate">{{ name }}</span>
                </span>
                <span
                  v-if="card.serviceNames.length > 3"
                  class="text-[11px] text-slate-400"
                >+{{ card.serviceNames.length - 3 }}</span>
                <button
                  v-if="card.serviceNames.length === 0"
                  type="button"
                  class="inline-flex items-center gap-1 rounded-2xl border border-dashed border-amber-300 bg-amber-50/60 px-2 py-0.5 text-[11px] font-medium text-amber-700 transition-colors hover:bg-amber-100"
                  @click.stop="openPicker(card.skill)"
                >
                  <AlertTriangle class="h-3 w-3" />
                  Услуга не привязана
                </button>
              </div>
            </div>
          </div>

          <!-- actions -->
          <div class="relative z-20 flex shrink-0 items-center gap-1.5" @click.stop>
            <button
              type="button"
              class="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-900"
              title="Привязать услуги"
              @click="openPicker(card.skill)"
            >
              <Stethoscope class="h-3.5 w-3.5" />
            </button>
            <button
              v-if="card.skill.status !== 'published' && publishingId !== card.skill.id"
              type="button"
              class="inline-flex h-8 items-center gap-1 rounded-lg border border-emerald-200 bg-emerald-50 px-2.5 text-xs font-medium text-emerald-700 transition-colors hover:bg-emerald-100 disabled:opacity-50"
              title="Опубликовать навык — рантайм начнёт его использовать"
              :disabled="!card.skillReady"
              @click="handlePublish(card.skill)"
            >
              <UploadCloud class="h-3.5 w-3.5" />
              Опубликовать
            </button>
            <button
              v-else-if="card.skill.status === 'published' && publishingId !== card.skill.id"
              type="button"
              class="inline-flex h-8 items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-50"
              title="Снять с публикации"
              @click="handleUnpublish(card.skill)"
            >
              <CloudOff class="h-3.5 w-3.5" />
              Снять
            </button>
            <span
              v-else
              class="inline-flex h-8 items-center gap-1 rounded-lg border border-emerald-200 bg-emerald-50 px-2.5 text-xs font-medium text-emerald-700 opacity-60"
            >
              <Loader2 class="h-3.5 w-3.5 animate-spin" />
            </span>
            <button
              type="button"
              class="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-red-200 bg-white text-red-600 transition-colors hover:bg-red-50"
              title="Удалить навык (в корзину)"
              @click="handleDelete(card.skill)"
            >
              <Trash2 class="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        <!-- Metrics -->
        <div class="mt-4 grid grid-cols-3 gap-2">
          <div class="rounded-2xl bg-emerald-50/60 px-3 py-2.5">
            <div class="text-[9px] font-black uppercase tracking-wider text-emerald-600/80">Обработок</div>
            <div class="mt-0.5 text-lg font-bold text-emerald-700">{{ card.objections }}</div>
          </div>
          <div
            class="rounded-2xl px-3 py-2.5"
            :class="card.gaps > 0 ? 'bg-amber-50/60' : 'bg-slate-50'"
          >
            <div
              class="text-[9px] font-black uppercase tracking-wider"
              :class="card.gaps > 0 ? 'text-amber-600/80' : 'text-slate-400'"
            >Пробелов</div>
            <div
              class="mt-0.5 text-lg font-bold"
              :class="card.gaps > 0 ? 'text-amber-700' : 'text-slate-500'"
            >{{ card.gaps }}</div>
          </div>
          <div class="rounded-2xl bg-primary/5 px-3 py-2.5">
            <div class="text-[9px] font-black uppercase tracking-wider text-primary/70">Покрытие</div>
            <div class="mt-0.5 text-lg font-bold text-primary">
              {{ card.skillReady ? `${card.coverage}%` : '—' }}
            </div>
          </div>
        </div>

        <p v-if="!card.skillReady" class="mt-3 text-[11px] text-slate-400">
          Навык ещё пустой — откройте и наполните в чате или импортируйте из потока.
        </p>
      </div>
    </div>

    <SkillServicePicker
      :open="pickerOpen"
      :agent-id="agentId"
      :model-value="pickerTarget?.service_external_ids || []"
      :saving="savingLink"
      @update:open="pickerOpen = $event"
      @save="handleSaveLink"
    />

    <!-- Корзина навыков -->
    <div
      v-if="trashOpen"
      class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
      @click.self="trashOpen = false"
    >
      <div class="max-h-[80vh] w-full max-w-lg overflow-hidden rounded-3xl border border-slate-100 bg-white shadow-2xl">
        <div class="flex items-center justify-between border-b border-slate-100 px-5 py-4">
          <h3 class="flex items-center gap-2 text-base font-bold text-slate-900">
            <Trash2 class="h-4 w-4 text-slate-400" /> Корзина навыков
          </h3>
          <button type="button" class="rounded-lg p-1 text-slate-400 hover:bg-slate-100" @click="trashOpen = false">
            <X class="h-4 w-4" />
          </button>
        </div>
        <div class="max-h-[60vh] overflow-y-auto p-4">
          <p v-if="!trashItems.length" class="py-8 text-center text-sm text-slate-400">Корзина пуста</p>
          <div v-else class="space-y-2">
            <div
              v-for="t in trashItems"
              :key="t.id"
              class="flex items-center justify-between gap-3 rounded-2xl border border-slate-100 bg-slate-50/60 px-4 py-3"
            >
              <div class="min-w-0">
                <div class="truncate text-sm font-semibold text-slate-800">{{ t.name }}</div>
                <div class="text-[11px] text-slate-400">
                  удалён {{ t.deleted_at ? new Date(t.deleted_at).toLocaleString('ru-RU') : '' }}
                </div>
              </div>
              <button
                type="button"
                class="inline-flex shrink-0 items-center gap-1 rounded-lg border border-primary/20 bg-primary/5 px-2.5 py-1.5 text-xs font-medium text-primary transition-colors hover:bg-primary/10"
                @click="handleRestore(t)"
              >
                <RotateCcw class="h-3.5 w-3.5" /> Восстановить
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { navigateTo } from '#app'
import {
  AlertTriangle,
  Check,
  ChevronsDownUp,
  ChevronsUpDown,
  CloudOff,
  Copy,
  Loader2,
  Plus,
  RotateCcw,
  Search,
  ShieldAlert,
  Sparkles,
  Stethoscope,
  Trash2,
  UploadCloud,
  X,
} from 'lucide-vue-next'
import SkillServicePicker from '~/components/agents/skills/SkillServicePicker.vue'
import { useAgents } from '~/composables/useAgents'
import { useExpertSkills } from '~/composables/useExpertSkills'
import { useToast } from '~/composables/useToast'
import type { ExpertSkill, SkillDoc } from '~/types/scriptFlow'

const props = defineProps<{ agentId: string }>()
const agentId = props.agentId

const {
  skills,
  isLoading,
  error,
  fetchSkills,
  importFromMarkdown,
  fetchTrash,
  createSkill,
  updateSkill,
  deleteSkill,
  restoreSkill,
  publishSkill,
  unpublishSkill,
} = useExpertSkills(agentId)
const { fetchSqnsServicesCached } = useAgents()
const { success: toastSuccess, error: toastError } = useToast()

const showGuide = ref(false)
const guideCopied = ref(false)

const skillPrompt = `Ты помогаешь оформить НАВЫК общения для администратора клиники.
Я дам примеры того, как я отвечаю пациентам. Собери из них навык в формате markdown.

Структура файла:

# Навык: <тема, например «Биоревитализация»>

Контекст: <1–2 предложения — о каких услугах и запросах этот навык, чтобы система понимала, когда его подключать>

## Ситуация: <короткое название>
Когда срабатывает: <слова пациента, по которым видно эту ситуацию>
Как отвечаю:
- <фраза 1 — как я реально говорю>
- <фраза 2>
Избегать: <обороты, которых тут быть не должно>

(повтори блок «## Ситуация» для каждой типовой ситуации: приветствие, вопрос о цене, возражение «дорого», страх процедуры, «я подумаю», запись)

Правила:
- Пиши моими словами, живо, как в примерах. Не выдумывай «фирменных» фраз, которых я не говорила.
- НЕ вставляй точные цены, имена врачей и даты — вместо них пиши «актуально из системы». Эти факты подставит платформа.
- Один вопрос в одном сообщении. Коротко, тепло, по делу.

Мои примеры:
<вставьте сюда свои ответы пациентам>`

const copyGuidePrompt = async () => {
  try {
    await navigator.clipboard.writeText(skillPrompt)
    guideCopied.value = true
    setTimeout(() => { guideCopied.value = false }, 2000)
  } catch {
    toastError('Не удалось скопировать — выделите текст вручную')
  }
}

const creating = ref(false)
const publishingId = ref<string | null>(null)
const searchQuery = ref('')

// external_id → человекочитаемое имя услуги (для чипов)
const serviceNameById = ref<Record<string, string>>({})

const stripCode = (name: string) =>
  name.replace(/^[A-Za-zА-Яа-я]?\d{2}\.\d{2}\.\d{2,3}\s*/u, '').trim() || name

const loadServiceNames = async () => {
  try {
    const map: Record<string, string> = {}
    let offset = 0
    for (let page = 0; page < 5; page++) {
      const res = await fetchSqnsServicesCached(agentId, { limit: 1000, offset })
      const batch = (res?.services ?? []) as Array<{ external_id: number; name: string }>
      for (const s of batch) map[String(s.external_id)] = stripCode(s.name)
      if (batch.length < 1000) break
      offset += 1000
    }
    serviceNameById.value = map
  } catch {
    // имена не критичны — чипы просто покажут #id
  }
}

const publishedCount = computed(() => skills.value.filter((s) => s.status === 'published').length)

type SkillCard = {
  skill: ExpertSkill
  serviceNames: string[]
  objections: number
  gaps: number
  coverage: number
  skillReady: boolean
}

const cards = computed<SkillCard[]>(() =>
  skills.value.map((skill) => {
    const doc = (skill.skill_doc || null) as SkillDoc | null
    const objections = doc?.objections?.length ?? 0
    const gaps = doc?.gaps?.length ?? 0
    const denom = objections + gaps
    const coverage = denom > 0 ? Math.round((objections / denom) * 100) : 0
    const serviceNames = (skill.service_external_ids || []).map(
      (ext) => serviceNameById.value[ext] || `#${ext}`,
    )
    return {
      skill,
      serviceNames,
      objections,
      gaps,
      coverage,
      skillReady: !!doc && (objections > 0 || gaps > 0),
    }
  }),
)

const filteredCards = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return cards.value
  return cards.value.filter(
    (c) =>
      c.skill.name.toLowerCase().includes(q) ||
      c.serviceNames.some((n) => n.toLowerCase().includes(q)),
  )
})

const openSkill = (skillId: string) => navigateTo(`/agents/${agentId}/skills/${skillId}`)

const importing = ref(false)
const mdInput = ref<HTMLInputElement | null>(null)

const handleImportMd = async (e: Event) => {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (input) input.value = ''
  if (!file || importing.value) return
  importing.value = true
  try {
    const markdown = await file.text()
    if (!markdown.trim()) {
      toastError('Файл пустой')
      return
    }
    const name = file.name.replace(/\.(md|markdown|txt)$/i, '') || 'Импортированный навык'
    const created = await importFromMarkdown({ name, markdown })
    await fetchSkills()
    toastSuccess('Навык создан из файла — проверьте и опубликуйте')
    await navigateTo(`/agents/${agentId}/skills/${created.id}`)
  } catch (err: unknown) {
    toastError(err instanceof Error ? err.message : 'Не удалось импортировать файл')
  } finally {
    importing.value = false
  }
}

const handleCreate = async () => {
  if (creating.value) return
  creating.value = true
  try {
    const name = `Навык ${new Date().toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' })}`
    const created = await createSkill({ name })
    await fetchSkills()
    toastSuccess('Навык создан — привяжите услугу и наполните опытом эксперта')
    await navigateTo(`/agents/${agentId}/skills/${created.id}`)
  } catch (err: unknown) {
    toastError(err instanceof Error ? err.message : 'Не удалось создать навык')
  } finally {
    creating.value = false
  }
}

const handleDelete = async (skill: ExpertSkill) => {
  if (!confirm(`Удалить навык «${skill.name}»? Его можно будет восстановить из корзины.`)) return
  try {
    await deleteSkill(skill.id)
    await fetchSkills()
    await loadTrash()
    toastSuccess('Навык перемещён в корзину')
  } catch (err: unknown) {
    toastError(err instanceof Error ? err.message : 'Не удалось удалить навык')
  }
}

const handlePublish = async (skill: ExpertSkill) => {
  publishingId.value = skill.id
  try {
    await publishSkill(skill.id)
    await fetchSkills()
    toastSuccess('Навык опубликован — рантайм начнёт его использовать')
  } catch (err: unknown) {
    toastError(err instanceof Error ? err.message : 'Не удалось опубликовать навык')
  } finally {
    publishingId.value = null
  }
}

const handleUnpublish = async (skill: ExpertSkill) => {
  publishingId.value = skill.id
  try {
    await unpublishSkill(skill.id)
    await fetchSkills()
    toastSuccess('Навык снят с публикации')
  } catch (err: unknown) {
    toastError(err instanceof Error ? err.message : 'Не удалось снять навык')
  } finally {
    publishingId.value = null
  }
}

// ── Привязка услуг ────────────────────────────────────────────────────────────
const pickerOpen = ref(false)
const pickerTarget = ref<ExpertSkill | null>(null)
const savingLink = ref(false)

const openPicker = (skill: ExpertSkill) => {
  pickerTarget.value = skill
  pickerOpen.value = true
}

const handleSaveLink = async (ids: string[]) => {
  if (!pickerTarget.value) return
  savingLink.value = true
  try {
    await updateSkill(pickerTarget.value.id, { service_external_ids: ids })
    await fetchSkills()
    toastSuccess('Услуги навыка обновлены')
    pickerOpen.value = false
    pickerTarget.value = null
  } catch (err: unknown) {
    toastError(err instanceof Error ? err.message : 'Не удалось сохранить услуги')
  } finally {
    savingLink.value = false
  }
}

// ── Корзина ───────────────────────────────────────────────────────────────────
const trashOpen = ref(false)
const trashItems = ref<ExpertSkill[]>([])
const trashCount = computed(() => trashItems.value.length)

const loadTrash = async () => {
  try {
    trashItems.value = await fetchTrash()
  } catch {
    // не критично
  }
}

const openTrash = async () => {
  trashOpen.value = true
  await loadTrash()
}

const handleRestore = async (skill: ExpertSkill) => {
  try {
    await restoreSkill(skill.id)
    await loadTrash()
    await fetchSkills()
    toastSuccess('Навык восстановлен')
  } catch (err: unknown) {
    toastError(err instanceof Error ? err.message : 'Не удалось восстановить навык')
  }
}

onMounted(() => {
  fetchSkills()
  loadServiceNames()
  loadTrash()
})
</script>
