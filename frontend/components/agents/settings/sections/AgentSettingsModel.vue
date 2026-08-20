<template>
  <div class="flex flex-col gap-5">
    <!-- Header -->
    <div class="flex items-center justify-between gap-3 border-b border-slate-100 pb-4">
      <div class="flex items-center gap-2.5">
        <div class="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <Sun class="h-4 w-4" />
        </div>
        <h1 class="text-lg font-semibold text-slate-900">Параметры модели</h1>
      </div>
      <button
        type="button"
        class="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:border-primary/40 hover:text-primary transition-colors"
        @click="helpOpen = !helpOpen"
      >
        <BookOpen class="h-3.5 w-3.5" />
        Помощь по разделу
      </button>
    </div>

    <div
      v-if="helpOpen"
      class="rounded-2xl border border-slate-100 bg-slate-100 p-5 text-sm leading-relaxed text-slate-700"
    >
      <p class="mb-2 font-medium text-slate-900">Как выбрать модель</p>
      <p>
        Пресеты «Качество / Баланс / Минимальная стоимость» — быстрый способ подобрать
        модель для типового сценария. Если знаете, какая именно модель нужна, откройте
        «Список моделей». Температура управляет разбросом ответов: 0 — детерминированно,
        1 — балансно, 2 — креативно.
      </p>
    </div>

    <!-- Языковая модель: пресеты качества -->
    <div class="space-y-4 rounded-2xl bg-slate-100 p-5">
      <div class="flex items-center gap-2">
        <span class="text-sm font-semibold text-slate-900">Языковая модель</span>
        <span class="text-slate-300">·</span>
        <span class="text-xs text-slate-500">Три пресета для типовых сценариев</span>
      </div>

      <p class="text-sm text-slate-600">
        Мы собрали три готовых режима для типовых сценариев. Нажмите подходящий вариант, а если нужна конкретная модель — откройте полный список.
      </p>

      <div class="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <button
          v-for="preset in qualityPresets"
          :key="preset.id"
          type="button"
          :disabled="!canEditAgents"
          class="group flex items-center gap-3 rounded-2xl border p-3 text-left transition-all duration-300 disabled:cursor-not-allowed disabled:opacity-60"
          :class="isPresetActive(preset)
            ? 'border-primary/40 bg-primary/[0.06] shadow-[0_2px_12px_-4px_rgba(59,130,246,0.15)]'
            : 'border-slate-200 bg-white hover:-translate-y-0.5 hover:border-primary/30 hover:shadow-[0_10px_24px_-14px_rgba(0,0,0,0.08)]'"
          @click="applyPreset(preset)"
        >
          <div
            class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl transition-colors"
            :class="isPresetActive(preset) ? 'bg-primary/15 text-primary' : 'bg-slate-100 text-slate-500 group-hover:bg-primary/10 group-hover:text-primary'"
          >
            <component :is="preset.icon" class="h-4 w-4" />
          </div>
          <div class="min-w-0">
            <div class="text-sm font-semibold" :class="isPresetActive(preset) ? 'text-primary' : 'text-slate-900'">{{ preset.label }}</div>
            <div class="mt-0.5 text-xs text-slate-500">{{ preset.sub }}</div>
          </div>
        </button>
      </div>

      <div v-if="activePreset" class="space-y-1.5 rounded-xl border border-slate-200 bg-white/70 px-4 py-3 text-sm">
        <div><span class="font-medium text-slate-900">Хорошо подходит:</span> <span class="text-slate-700">{{ activePreset.good }}</span></div>
        <div><span class="font-medium text-slate-900">Не подходит:</span> <span class="text-slate-700">{{ activePreset.bad }}</span></div>
      </div>
    </div>

    <!-- Выбранная модель -->
    <div class="rounded-2xl border border-slate-100 bg-white p-5 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
      <div class="flex items-start justify-between gap-3">
        <div class="text-[9px] font-black uppercase tracking-wider text-slate-400">Выбранная модель</div>
        <button
          type="button"
          :disabled="!canEditAgents"
          class="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:border-primary/40 hover:text-primary transition-colors disabled:cursor-not-allowed disabled:opacity-60"
          @click="isModelListOpen = !isModelListOpen"
        >
          {{ isModelListOpen ? 'Скрыть список' : 'Список моделей' }}
        </button>
      </div>

      <div class="mt-2 flex items-start gap-3">
        <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <Sparkles class="h-4 w-4" />
        </div>
        <div class="min-w-0 flex-1">
          <div class="flex items-baseline gap-2">
            <div class="text-lg font-bold text-primary">{{ currentModelLabel }}</div>
            <span v-if="currentProviderLabel" class="text-xs font-medium text-slate-400">{{ currentProviderLabel }}</span>
          </div>
          <p class="mt-1 text-sm text-slate-600">{{ currentModelDescription }}</p>
        </div>
      </div>

      <div class="mt-3 flex flex-wrap gap-2">
        <span
          v-for="badge in currentModelBadges"
          :key="badge.label"
          class="inline-flex items-center gap-1 rounded-lg bg-slate-50 px-2 py-1 text-[11px] font-medium text-slate-600"
        >
          <component :is="badge.icon" class="h-3 w-3 text-slate-400" />
          {{ badge.label }}
        </span>
      </div>

      <div v-if="isModelListOpen" class="mt-4 space-y-3 border-t border-slate-100 pt-4">
        <div v-if="activeModelsError" class="rounded-xl border border-red-100 bg-red-50/60 px-3 py-2 text-xs text-red-700">
          {{ activeModelsError }}
        </div>
        <div v-else-if="isLoadingActiveModels && !modelGroups.length" class="flex items-center gap-2 text-xs text-slate-500">
          <Loader2 class="h-3.5 w-3.5 animate-spin" />
          Загрузка списка моделей…
        </div>
        <div v-for="group in modelGroups" :key="group.group" class="space-y-1.5">
          <div class="text-[9px] font-black uppercase tracking-wider text-slate-400">{{ group.group }}</div>
          <div class="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
            <button
              v-for="option in group.options"
              :key="option.value"
              type="button"
              :disabled="!canEditAgents"
              class="flex items-center justify-between gap-2 rounded-xl border px-3 py-2 text-left text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-60"
              :class="option.value === form.model
                ? 'border-primary/40 bg-primary/[0.06] text-primary'
                : 'border-slate-100 bg-white text-slate-700 hover:border-primary/30 hover:text-primary'"
              @click="selectModel(option.value)"
            >
              <span class="truncate">{{ option.label }}</span>
              <Check v-if="option.value === form.model" class="h-3.5 w-3.5 shrink-0" />
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Уровень рассуждений (только для reasoning-моделей) -->
    <div class="space-y-3 rounded-2xl bg-slate-100 p-5">
      <div class="flex items-center justify-between gap-3">
        <div class="flex items-center gap-2">
          <span class="text-sm font-semibold text-slate-900">Уровень рассуждений</span>
          <span class="text-xs text-slate-500">Глубина внутренних размышлений модели</span>
        </div>
        <span
          v-if="!isReasoningModel"
          class="rounded-full bg-slate-200/70 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-slate-500"
        >Модель не поддерживает</span>
      </div>

      <div v-if="!isReasoningModel" class="rounded-xl border border-dashed border-slate-200 bg-white/60 px-4 py-3 text-xs text-slate-500">
        Текущая модель <span class="font-mono text-slate-700">{{ form.model }}</span> не поддерживает управление глубиной рассуждений. Выберите одну из моделей семейства <span class="font-medium">GPT-5 / o3 / o4-mini</span>, чтобы активировать этот параметр.
      </div>

      <div v-else class="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <button
          v-for="opt in reasoningOptions"
          :key="opt.value === null ? 'none' : opt.value"
          type="button"
          :disabled="!canEditAgents"
          class="group flex items-start gap-2 rounded-xl border p-3 text-left transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-60"
          :class="isReasoningActive(opt.value)
            ? 'border-primary/40 bg-primary/[0.06] shadow-[0_2px_10px_-4px_rgba(59,130,246,0.15)]'
            : 'border-slate-200 bg-white hover:border-primary/30 hover:bg-slate-50'"
          @click="applyReasoning(opt.value)"
        >
          <span
            class="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border"
            :class="isReasoningActive(opt.value) ? 'border-primary bg-primary' : 'border-slate-300 bg-white'"
          >
            <span v-if="isReasoningActive(opt.value)" class="h-1.5 w-1.5 rounded-full bg-white" />
          </span>
          <div class="min-w-0">
            <div class="text-sm font-semibold" :class="isReasoningActive(opt.value) ? 'text-primary' : 'text-slate-900'">{{ opt.label }}</div>
            <div class="mt-0.5 text-xs leading-tight text-slate-500">{{ opt.hint }}</div>
          </div>
        </button>
      </div>
    </div>

    <!-- Подробность ответа — заглушка (нет в Chat API) -->
    <div class="space-y-2 rounded-2xl border border-dashed border-slate-200 bg-slate-100 p-4">
      <div class="flex items-center gap-2">
        <span class="text-sm font-semibold text-slate-700">Подробность ответа</span>
        <span class="rounded-full bg-slate-200/70 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-slate-500">Скоро</span>
      </div>
      <p class="text-xs text-slate-500">Параметр verbosity доступен только через Responses API. Требует перехода бэка на OpenAIResponsesModel — в отдельном релизе.</p>
    </div>

    <!-- Температура -->
    <div class="space-y-3 rounded-2xl bg-slate-100 p-5">
      <div class="flex items-center justify-between gap-3">
        <div class="flex items-center gap-2">
          <span class="text-sm font-semibold text-slate-900">Температура</span>
          <span class="text-xs text-slate-500">Разброс ответов модели</span>
        </div>
        <div class="text-sm font-bold text-primary">{{ temperaturePercent }}%</div>
      </div>
      <input
        v-model.number="temperatureModel"
        :disabled="!canEditAgents"
        type="range"
        min="0"
        max="2"
        step="0.05"
        class="w-full accent-primary disabled:cursor-not-allowed disabled:opacity-60"
      />
      <div class="flex justify-between text-[10px] font-medium text-slate-400">
        <span>0%</span><span>25%</span><span>50%</span><span>75%</span><span>100%</span>
      </div>
      <div class="rounded-xl border border-primary/20 bg-primary/[0.04] px-4 py-2.5 text-sm text-slate-700">
        <span class="font-semibold text-primary">{{ temperatureLabel }}.</span>
        {{ temperatureDescription }}
      </div>
    </div>

    <!-- Время ожидания ответа -->
    <div class="space-y-3 rounded-2xl bg-slate-100 p-5">
      <div class="flex items-center gap-2">
        <span class="text-sm font-semibold text-slate-900">Время ожидания ответа</span>
        <span class="text-xs text-slate-500">Буфер для объединения быстрых сообщений</span>
      </div>
      <div class="grid gap-3 sm:grid-cols-[220px_1fr]">
        <div class="space-y-1.5">
          <label class="text-xs font-semibold text-slate-700">Буфер сообщений (секунды)</label>
          <input
            v-model.number="form.debounce_delay_seconds"
            :disabled="!canEditAgents"
            type="number"
            min="0"
            max="30"
            step="1"
            class="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-primary/30 disabled:cursor-not-allowed disabled:opacity-60"
          />
        </div>
        <p class="self-end text-xs text-slate-500">Бот дождётся указанного времени и объединит несколько сообщений подряд в один ответ. 0 — отвечать сразу.</p>
      </div>
    </div>

    <!-- Максимальная длина ответа -->
    <div class="space-y-3 rounded-2xl bg-slate-100 p-5">
      <div class="flex items-center gap-2">
        <span class="text-sm font-semibold text-slate-900">Максимальная длина ответа</span>
        <span class="text-xs text-slate-500">Лимит токенов на один ответ модели</span>
      </div>
      <div class="grid gap-3 sm:grid-cols-[220px_1fr]">
        <div class="space-y-1.5">
          <label class="text-xs font-semibold text-slate-700">Макс. токенов ответа</label>
          <input
            v-model.number="form.llm_params.max_tokens"
            :disabled="!canEditAgents"
            type="number"
            min="1"
            max="8000"
            step="50"
            class="w-full rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-primary/30 disabled:cursor-not-allowed disabled:opacity-60"
          />
        </div>
        <p class="self-end text-xs text-slate-500">
          Определяет максимальную длину ответа. Слишком маленькое значение обрежет ответ, слишком большое — увеличит стоимость.
        </p>
      </div>
    </div>

    <div class="flex items-center justify-end text-xs text-slate-500">
      <span v-if="store.isAutoSaving" class="inline-flex items-center gap-1.5">
        <Loader2 class="h-3 w-3 animate-spin" />
        Сохранение…
      </span>
      <span v-else-if="store.lastAutoSavedAt" class="inline-flex items-center gap-1.5 text-emerald-600">
        <Check class="h-3 w-3" />
        Сохранено
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import {
  Sun,
  Sparkles,
  Star,
  SlidersHorizontal,
  DollarSign,
  BookOpen,
  Loader2,
  Check,
  Calendar,
  Braces,
  Cpu,
} from 'lucide-vue-next'
import { useAgentEditorStore } from '~/composables/useAgentEditorStore'
import { usePermissions } from '~/composables/usePermissions'
import { useActiveModels } from '~/composables/useActiveModels'

const store = useAgentEditorStore()
const { form } = storeToRefs(store)
const { canEditAgents } = usePermissions()
const {
  modelGroups,
  isLoading: isLoadingActiveModels,
  error: activeModelsError,
  fetchActiveModels,
} = useActiveModels()

const helpOpen = ref(false)
const isModelListOpen = ref(false)

type QualityPreset = {
  id: 'max' | 'balance' | 'cheap'
  label: string
  sub: string
  model: string
  good: string
  bad: string
  icon: unknown
}

const qualityPresets: QualityPreset[] = [
  {
    id: 'max',
    label: 'Максимальное качество',
    sub: 'Точная и дорогая',
    model: 'openai:gpt-5.2-pro',
    good: 'Экспертные сценарии, работа с редкими и сложными случаями, важные бизнес-решения.',
    bad: 'Массовые типовые запросы, где качества «Баланса» уже достаточно, а цена важна.',
    icon: Star,
  },
  {
    id: 'balance',
    label: 'Баланс',
    sub: 'Надёжная и доступная',
    model: 'openai:gpt-4.1',
    good: 'Основной рабочий агент для поддержки, заявок, консультаций, записи клиентов и сценариев, где нужна стабильность без максимальной цены.',
    bad: 'Очень простые потоковые задачи, где важна только минимальная цена, или критические экспертные решения, где нужна самая сильная модель.',
    icon: SlidersHorizontal,
  },
  {
    id: 'cheap',
    label: 'Минимальная стоимость',
    sub: 'Лучшая из дешёвых',
    model: 'openai:gpt-4.1-nano',
    good: 'Массовые короткие ответы, автоответы, простые FAQ. Максимум запросов на рубль.',
    bad: 'Сложные диалоги с многошаговыми рассуждениями или частыми вызовами инструментов.',
    icon: DollarSign,
  },
]

const activePreset = computed<QualityPreset | null>(
  () => qualityPresets.find((p) => p.model === form.value.model) || null,
)

const isPresetActive = (preset: QualityPreset) => preset.model === form.value.model

const applyPreset = (preset: QualityPreset) => {
  if (!canEditAgents.value) return
  form.value.model = preset.model
}

const selectModel = (value: string) => {
  if (!canEditAgents.value) return
  form.value.model = value
}

const currentModelOption = computed(() => {
  const all = modelGroups.value.flatMap((g) => g.options)
  return all.find((o) => o.value === form.value.model) || null
})

const currentModelLabel = computed(() => {
  if (currentModelOption.value) return currentModelOption.value.label
  const raw = form.value.model || ''
  return raw.split(':')[1] || raw || '—'
})

const currentProviderLabel = computed(() => {
  const provider = currentModelOption.value?.provider || (form.value.model || '').split(':')[0]
  if (!provider) return ''
  if (provider === 'openai') return 'OpenAI'
  if (provider === 'anthropic') return 'Anthropic'
  return provider
})

const currentModelDescription = computed(() => {
  if (activePreset.value) return activePreset.value.good
  return 'Сбалансированная модель для многошаговых диалогов, функций и сложных бизнес-сценариев.'
})

const currentModelBadges = computed(() => [
  { label: 'Автосохранение включено', icon: Check },
  { label: currentProviderLabel.value || 'Провайдер', icon: Cpu },
])

const temperatureModel = computed({
  get: () => Number(form.value.llm_params?.temperature ?? 0.7),
  set: (value: number) => {
    if (!form.value.llm_params) return
    form.value.llm_params.temperature = Number(value)
  },
})

const temperaturePercent = computed(() => Math.round((temperatureModel.value / 2) * 100))

const temperatureLabel = computed(() => {
  const p = temperaturePercent.value
  if (p <= 15) return 'Точная температура'
  if (p <= 45) return 'Средняя температура'
  if (p <= 75) return 'Гибкая температура'
  return 'Креативная температура'
})

const temperatureDescription = computed(() => {
  const p = temperaturePercent.value
  if (p <= 15) return 'Ответы стабильные и предсказуемые. Хорошо для скриптов, форм и запросов, где отклонения недопустимы.'
  if (p <= 45) return 'Оптимальный баланс между точностью и гибкостью. Агент умеет придерживаться скриптов, но при необходимости может проявлять инициативу. Рекомендуется для большинства бизнес-сценариев.'
  if (p <= 75) return 'Больше вариативности в формулировках. Хорошо для консультаций и живого диалога, но с риском отклонений от скрипта.'
  return 'Максимально свободные ответы. Подходит для творческих задач, для строгих скриптов — противопоказано.'
})

/**
 * Reasoning-модели OpenAI:
 *  - серия o (o1, o3, o3-mini, o3-pro, o4-mini)
 *  - серия GPT-5 (gpt-5, gpt-5-mini, gpt-5-nano, gpt-5.1, gpt-5.2, gpt-5.2-pro)
 * Только для них имеет смысл openai_reasoning_effort в OpenAI Chat API.
 */
const REASONING_MODEL_RE = /^openai:(o\d[\w-]*|gpt-5[\w.-]*)$/i

const isReasoningModel = computed(() => REASONING_MODEL_RE.test(form.value.model || ''))

type ReasoningOption = { value: 'low' | 'medium' | 'high' | null; label: string; hint: string }

const reasoningOptions: ReasoningOption[] = [
  { value: null, label: 'Отключено', hint: 'Быстрые ответы без рассуждений' },
  { value: 'low', label: 'Низкий', hint: 'Короткие цепочки, быстрые ответы' },
  { value: 'medium', label: 'Средний', hint: 'Баланс скорости и качества' },
  { value: 'high', label: 'Высокий', hint: 'Глубокий анализ, дольше и дороже' },
]

const currentReasoning = computed<'low' | 'medium' | 'high' | null>(
  () => (form.value.llm_params?.openai_reasoning_effort as any) ?? null,
)

const isReasoningActive = (value: 'low' | 'medium' | 'high' | null) =>
  currentReasoning.value === value

const applyReasoning = (value: 'low' | 'medium' | 'high' | null) => {
  if (!canEditAgents.value || !form.value.llm_params) return
  if (value === null) {
    // Полностью удаляем ключ, чтобы PydanticAI не отправлял пустой reasoning_effort в API.
    delete (form.value.llm_params as any).openai_reasoning_effort
  } else {
    form.value.llm_params.openai_reasoning_effort = value
  }
}

// При смене модели на не-reasoning — удаляем ключ, чтобы OpenAI не вернул ошибку
// «unknown parameter reasoning_effort» на gpt-4.1 / gpt-4o.
watch(
  () => form.value.model,
  () => {
    if (!isReasoningModel.value && form.value.llm_params?.openai_reasoning_effort) {
      delete (form.value.llm_params as any).openai_reasoning_effort
    }
  },
)

onMounted(async () => {
  await fetchActiveModels()
})
</script>
