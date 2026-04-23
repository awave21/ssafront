<template>
  <div class="w-full px-5 py-5 flex flex-col gap-5">
      <!-- Auth Status Banner -->
      <div v-if="!isAuthenticated" class="mb-6 bg-yellow-50 border border-yellow-200 rounded-lg p-4">
        <div class="flex items-center justify-between">
          <div class="flex items-center">
            <AlertCircle class="h-5 w-5 text-yellow-400 mr-3" />
            <div>
              <h3 class="text-sm font-medium text-yellow-800">
                Требуется аутентификация
              </h3>
              <p class="text-sm text-yellow-700 mt-1">
                Войдите в систему для создания агента
              </p>
            </div>
          </div>
          <button
            @click="showAuthModal = true"
            class="px-4 py-2 bg-yellow-600 text-white text-sm font-medium rounded-lg hover:bg-yellow-700 transition-colors"
          >
            Войти
          </button>
        </div>
      </div>

      <!-- TopBar Actions (teleported into layout header) -->
      <Teleport v-if="isMounted" to="#topbar-actions">
        <button
          @click="handleCancel"
          class="px-4 py-1.5 text-sm text-muted-foreground font-medium hover:text-foreground transition-colors"
        >
          Отменить
        </button>
        <button
          @click="handleCreate"
          :disabled="creating || !isValid"
          class="px-4 py-1.5 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5"
        >
          <Loader2 v-if="creating" class="h-3.5 w-3.5 animate-spin" />
          <Check v-else class="h-3.5 w-3.5" />
          {{ createButtonLabel }}
        </button>
      </Teleport>

      <!-- Content Card -->
          <div class="bg-background rounded-xl border border-border p-6">
            <form @submit.prevent="handleCreate" class="space-y-8">
              <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
                <div>
                  <label class="block text-sm font-bold text-slate-900 mb-2">Название агента *</label>
                  <input
                    v-model="form.name"
                    type="text"
                    required
                    placeholder="Например: Агент поддержки"
                    class="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all"
                  />
                </div>
                <div>
                  <label class="block text-sm font-bold text-slate-900 mb-2">Модель ИИ *</label>
                  <select
                    v-model="form.model"
                    required
                    class="w-full px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-all"
                  >
                    <option value="">Выберите модель</option>
                    <option v-if="isLoadingModels && !modelGroups.length" value="" disabled>
                      Загрузка моделей...
                    </option>
                    <option v-else-if="modelsError && !modelGroups.length" value="" disabled>
                      Не удалось загрузить модели
                    </option>
                    <option v-else-if="!modelGroups.length" value="" disabled>
                      Нет доступных моделей
                    </option>

                    <optgroup
                      v-for="group in modelGroups"
                      :key="group.group"
                      :label="group.group"
                    >
                      <option
                        v-for="option in group.options"
                        :key="option.value"
                        :value="option.value"
                      >
                        {{ option.label }}
                      </option>
                    </optgroup>
                  </select>
                  <p v-if="modelsError" class="mt-2 text-xs text-rose-600">
                    {{ modelsError }}
                  </p>
                </div>
              </div>

              <div>
                <label class="block text-sm font-bold text-slate-900 mb-2">Часовой пояс</label>
                <Popover v-model:open="tzOpen">
                  <PopoverTrigger as-child>
                    <button
                      type="button"
                      role="combobox"
                      :aria-expanded="tzOpen"
                      class="w-full flex items-center justify-between px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm transition-all hover:bg-white"
                    >
                      <span :class="form.timezone ? 'text-slate-900' : 'text-slate-400'">
                        {{ selectedTimezoneLabel }}
                      </span>
                      <ChevronsUpDown class="ml-2 h-4 w-4 shrink-0 opacity-50" />
                    </button>
                  </PopoverTrigger>
                  <PopoverContent class="w-[--reka-popper-anchor-width] p-0" align="start">
                    <Command v-model="form.timezone" @update:model-value="tzOpen = false">
                      <CommandInput placeholder="Поиск часового пояса..." />
                      <CommandEmpty>Часовой пояс не найден</CommandEmpty>
                      <CommandList>
                        <CommandGroup>
                          <CommandItem
                            v-for="tz in timezoneOptions"
                            :key="tz.value"
                            :value="tz.value"
                          >
                            <Check
                              class="mr-2 h-4 w-4"
                              :class="form.timezone === tz.value ? 'opacity-100' : 'opacity-0'"
                            />
                            {{ tz.label }}
                          </CommandItem>
                        </CommandGroup>
                      </CommandList>
                    </Command>
                  </PopoverContent>
                </Popover>
                <p class="mt-1.5 text-xs text-slate-400">Часовой пояс используется агентом при работе с датами и временем</p>
              </div>

              <div>
                <div class="mb-4">
                  <h3 class="text-sm font-bold text-slate-900">Системный промпт *</h3>
                  <p class="text-xs text-slate-500 mt-1">
                    Опишите роль и правила агента. Можно сохранить как есть или улучшить через обучение.
                  </p>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
                  <button
                    type="button"
                    @click="creationMode = 'manual'"
                    class="text-left p-4 rounded-xl border-2 transition-all hover:shadow-sm"
                    :class="[
                      creationMode === 'manual'
                        ? 'border-indigo-500 bg-indigo-50'
                        : 'border-slate-200 bg-white hover:border-slate-300'
                    ]"
                  >
                    <div class="flex items-start gap-3">
                      <div class="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
                        :class="[creationMode === 'manual' ? 'bg-indigo-600' : 'bg-slate-100']">
                        <Check class="h-5 w-5" :class="[creationMode === 'manual' ? 'text-white' : 'text-slate-400']" />
                      </div>
                      <div class="flex-1 min-w-0">
                        <h4 class="text-sm font-semibold mb-1"
                          :class="[creationMode === 'manual' ? 'text-indigo-900' : 'text-slate-900']">
                          Сохранить как введено
                        </h4>
                        <p class="text-xs text-slate-500">
                          Быстрое создание. Ваш текст сохраняется без изменений.
                        </p>
                      </div>
                    </div>
                  </button>
                  <button
                    type="button"
                    @click="creationMode = 'enhanced'"
                    class="text-left p-4 rounded-xl border-2 transition-all hover:shadow-sm"
                    :class="[
                      creationMode === 'enhanced'
                        ? 'border-indigo-500 bg-indigo-50'
                        : 'border-slate-200 bg-white hover:border-slate-300'
                    ]"
                  >
                    <div class="flex items-start gap-3">
                      <div class="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
                        :class="[creationMode === 'enhanced' ? 'bg-indigo-600' : 'bg-slate-100']">
                        <Sparkles class="h-5 w-5" :class="[creationMode === 'enhanced' ? 'text-white' : 'text-slate-400']" />
                      </div>
                      <div class="flex-1 min-w-0">
                        <h4 class="text-sm font-semibold mb-1"
                          :class="[creationMode === 'enhanced' ? 'text-indigo-900' : 'text-slate-900']">
                          Улучшить через обучение
                        </h4>
                        <p class="text-xs text-slate-500">
                          Дольше (обычно 10-20 сек), но итоговый промпт оптимизируется автоматически.
                        </p>
                      </div>
                    </div>
                  </button>
                </div>

                <!-- Prompt Text Area -->
                <div class="relative">
                  <textarea
                    v-model="form.system_prompt"
                    required
                    rows="12"
                    placeholder="Опишите роль, задачи, ограничения и стиль ответов агента..."
                    class="w-full px-5 py-4 text-slate-700 bg-slate-50 border border-slate-200 rounded-xl focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 focus:bg-white transition-all resize-none leading-relaxed"
                  ></textarea>
                </div>

                <div
                  v-if="creating && creationMode === 'enhanced'"
                  class="mt-4 rounded-xl border border-indigo-200 bg-indigo-50 p-4"
                >
                  <div class="flex items-center gap-2 text-indigo-900 text-sm font-medium">
                    <Loader2 class="h-4 w-4 animate-spin" />
                    {{ progressStepLabel }}
                  </div>
                  <p class="text-xs text-indigo-700 mt-1">
                    Обычно занимает 10-20 секунд. Прошло: {{ elapsedSeconds }} сек.
                  </p>
                </div>
              </div>

              <div class="pt-4 flex items-center justify-end border-t border-border">
                <p class="text-xs text-muted-foreground">* Обязательные поля для заполнения</p>
              </div>
            </form>
          </div>

    <!-- Auth Modal -->
    <AuthModal
      :is-open="showAuthModal"
      @close="showAuthModal = false"
      @authenticated="handleAuthenticated"
    />
  </div>
</template>

<script setup lang="ts">
definePageMeta({
  middleware: 'auth'
})

import { ref, computed, onBeforeUnmount, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  AlertCircle,
  Loader2,
  Sparkles,
  Check,
  ChevronsUpDown
} from 'lucide-vue-next'
import { Popover, PopoverContent, PopoverTrigger } from '~/components/ui/popover'
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '~/components/ui/command'
import { useAgents } from '../../composables/useAgents'
import { useAuth } from '../../composables/useAuth'
import { useActiveModels } from '~/composables/useActiveModels'
import { useToast } from '~/composables/useToast'
import { useAgentPromptEnhancement, type PromptEnhancementStep } from '~/composables/useAgentPromptEnhancement'

// Auth and Router
const { isAuthenticated } = useAuth()
const router = useRouter()
const { createAgent, fetchDefaultSystemPrompt } = useAgents()
const { info: toastInfo, success: toastSuccess } = useToast()
const {
  modelGroups,
  isLoading: isLoadingModels,
  error: modelsError,
  fetchActiveModels,
  getFirstModelValue
} = useActiveModels()
const { enhancePrompt } = useAgentPromptEnhancement()

// State
const showAuthModal = ref(false)
const creating = ref(false)
const isMounted = ref(false)
const creationMode = ref<'manual' | 'enhanced'>('manual')
const progressStepLabel = ref('Подготовка')
const progressStepNumber = ref(1)
const elapsedSeconds = ref(0)
let elapsedTimer: ReturnType<typeof setInterval> | null = null

const setProgressStep = (stepNumber: number, stepLabel: string) => {
  progressStepNumber.value = stepNumber
  progressStepLabel.value = stepLabel
}

const updateEnhancementStep = (step: PromptEnhancementStep) => {
  const stepMap: Record<PromptEnhancementStep, { number: number; label: string }> = {
    'create-session': { number: 2, label: 'Запускаем сессию обучения' },
    'submit-feedback': { number: 3, label: 'Передаем исходный промпт' },
    'generate-prompt': { number: 4, label: 'Генерируем улучшенный промпт' },
    'apply-prompt': { number: 5, label: 'Применяем результат' },
  }
  const nextStep = stepMap[step]
  setProgressStep(nextStep.number, nextStep.label)
}

const startElapsedTimer = () => {
  elapsedSeconds.value = 0
  if (elapsedTimer) clearInterval(elapsedTimer)
  elapsedTimer = setInterval(() => {
    elapsedSeconds.value += 1
  }, 1000)
}

const stopElapsedTimer = () => {
  if (!elapsedTimer) return
  clearInterval(elapsedTimer)
  elapsedTimer = null
}

const timezoneOptions = [
  { value: 'Europe/Moscow', label: 'Москва (UTC+3)' },
  { value: 'Europe/Kaliningrad', label: 'Калининград (UTC+2)' },
  { value: 'Asia/Yekaterinburg', label: 'Екатеринбург (UTC+5)' },
  { value: 'Asia/Omsk', label: 'Омск (UTC+6)' },
  { value: 'Asia/Novosibirsk', label: 'Новосибирск (UTC+7)' },
  { value: 'Asia/Krasnoyarsk', label: 'Красноярск (UTC+7)' },
  { value: 'Asia/Irkutsk', label: 'Иркутск (UTC+8)' },
  { value: 'Asia/Yakutsk', label: 'Якутск (UTC+9)' },
  { value: 'Asia/Vladivostok', label: 'Владивосток (UTC+10)' },
  { value: 'Asia/Magadan', label: 'Магадан (UTC+11)' },
  { value: 'Asia/Kamchatka', label: 'Камчатка (UTC+12)' },
  { value: 'UTC', label: 'UTC' },
  { value: 'Europe/London', label: 'Лондон (UTC+0)' },
  { value: 'Europe/Berlin', label: 'Берлин (UTC+1)' },
  { value: 'Europe/Istanbul', label: 'Стамбул (UTC+3)' },
  { value: 'Asia/Dubai', label: 'Дубай (UTC+4)' },
  { value: 'Asia/Almaty', label: 'Алматы (UTC+6)' },
  { value: 'Asia/Bangkok', label: 'Бангкок (UTC+7)' },
  { value: 'Asia/Shanghai', label: 'Шанхай (UTC+8)' },
  { value: 'Asia/Tokyo', label: 'Токио (UTC+9)' },
  { value: 'America/New_York', label: 'Нью-Йорк (UTC-5)' },
  { value: 'America/Los_Angeles', label: 'Лос-Анджелес (UTC-8)' },
]

const tzOpen = ref(false)

const form = ref({
  name: '',
  model: '',
  timezone: 'Europe/Moscow',
  system_prompt: ''
})

const selectedTimezoneLabel = computed(() =>
  timezoneOptions.find(tz => tz.value === form.value.timezone)?.label ?? 'Выберите часовой пояс'
)

const isValid = computed(() => {
  return form.value.name.trim() !== '' &&
         form.value.model !== '' &&
         form.value.system_prompt.trim() !== ''
})

const createButtonLabel = computed(() => {
  if (!creating.value) return 'Создать'
  if (creationMode.value !== 'enhanced') return 'Создаем...'
  return 'Создаем и улучшаем...'
})

const handleCreate = async () => {
  if (!isValid.value) return

  try {
    creating.value = true
    setProgressStep(1, 'Создаем агента')
    if (creationMode.value === 'enhanced') {
      startElapsedTimer()
    }

    const newAgent = await createAgent({
      ...form.value,
      timezone: form.value.timezone || 'Europe/Moscow',
      status: 'draft',
      version: 1,
      llm_params: {
        temperature: 0.7,
        max_tokens: 1000
      }
    })

    if (creationMode.value === 'enhanced') {
      const enhancementResult = await enhancePrompt({
        agentId: newAgent.id,
        sourcePrompt: form.value.system_prompt,
        onStepChange: updateEnhancementStep,
      })

      if (enhancementResult.ok) {
        toastSuccess('Промпт улучшен', 'Системный промпт автоматически обновлен и применен')
      } else {
        toastInfo(
          'Агент создан с исходным промптом',
          'Улучшение не выполнено, вы можете запустить обучение на странице агента'
        )
      }
    }

    router.push(`/agents/${newAgent.id}/prompt`)
  } catch (error) {
    console.error('Error creating agent:', error)
  } finally {
    stopElapsedTimer()
    creating.value = false
  }
}

const handleCancel = () => {
  router.push('/agents')
}

const handleAuthenticated = () => {
  showAuthModal.value = false
}

const { pageTitle } = useLayoutState()

onMounted(async () => {
  isMounted.value = true
  pageTitle.value = 'Создание агента'
  await fetchActiveModels()

  if (!form.value.model) {
    form.value.model = getFirstModelValue()
  }

  try {
    const def = await fetchDefaultSystemPrompt()
    if (def?.system_prompt && !form.value.system_prompt.trim()) {
      form.value.system_prompt = def.system_prompt
    }
  } catch {
    /* шаблон опционален — при пустом промпте бэкенд подставит то же при создании */
  }
})

onBeforeUnmount(() => {
  stopElapsedTimer()
})
</script>

<style scoped>
</style>
