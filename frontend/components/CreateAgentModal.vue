<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity duration-300"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-opacity duration-300"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="isOpen"
        class="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50"
        @click="$emit('close')"
      >
        <Transition
          enter-active-class="transition-all duration-300"
          enter-from-class="opacity-0 scale-95 translate-y-4"
          enter-to-class="opacity-100 scale-100 translate-y-0"
          leave-active-class="transition-all duration-300"
          leave-from-class="opacity-100 scale-100 translate-y-0"
          leave-to-class="opacity-0 scale-95 translate-y-4"
        >
          <div
            v-if="isOpen"
            class="bg-white rounded-xl shadow-xl max-w-lg w-full mx-4 max-h-[90vh] overflow-y-auto"
            @click.stop
          >
            <div class="p-6">
              <div class="flex items-center justify-between mb-6">
                <h2 class="text-xl font-bold text-slate-900">
                  Создать нового агента
                </h2>
                <button
                  @click="$emit('close')"
                  class="p-2 text-slate-400 hover:text-slate-600 transition-colors"
                >
                  <X class="h-5 w-5" />
                </button>
              </div>

              <form @submit.prevent="handleSubmit" class="space-y-6">
                <!-- Название агента -->
                <div>
                  <label class="block text-sm font-medium text-slate-700 mb-2">
                    Название агента *
                  </label>
                  <input
                    v-model="form.name"
                    type="text"
                    required
                    class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    placeholder="Например: Агент поддержки клиентов"
                  />
                </div>

                <!-- Системный промпт -->
                <div>
                  <label class="block text-sm font-medium text-slate-700 mb-2">
                    Системный промпт *
                  </label>
                  <textarea
                    v-model="form.system_prompt"
                    required
                    rows="4"
                    class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 resize-none"
                    placeholder="Опишите роль и поведение агента..."
                  />
                </div>

                <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  <button
                    type="button"
                    @click="creationMode = 'manual'"
                    class="rounded-lg border px-3 py-2 text-left text-sm transition-colors"
                    :class="creationMode === 'manual' ? 'border-indigo-500 bg-indigo-50 text-indigo-900' : 'border-slate-300 bg-white text-slate-700'"
                  >
                    Сохранить как введено
                  </button>
                  <button
                    type="button"
                    @click="creationMode = 'enhanced'"
                    class="rounded-lg border px-3 py-2 text-left text-sm transition-colors"
                    :class="creationMode === 'enhanced' ? 'border-indigo-500 bg-indigo-50 text-indigo-900' : 'border-slate-300 bg-white text-slate-700'"
                  >
                    Улучшить через обучение
                  </button>
                </div>

                <div
                  v-if="isSubmitting && creationMode === 'enhanced'"
                  class="rounded-lg border border-indigo-200 bg-indigo-50 px-3 py-2"
                >
                  <p class="text-sm font-medium text-indigo-900">
                    {{ progressStepLabel }}
                  </p>
                  <p class="text-xs text-indigo-700 mt-0.5">
                    Обычно 10-20 секунд. Прошло: {{ elapsedSeconds }} сек.
                  </p>
                </div>

                <!-- Модель -->
                <div>
                  <label class="block text-sm font-medium text-slate-700 mb-2">
                    Модель ИИ *
                  </label>
                  <select
                    v-model="form.model"
                    required
                    class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
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

                <!-- Параметры LLM -->
                <div class="grid grid-cols-2 gap-4">
                  <div>
                    <label class="block text-sm font-medium text-slate-700 mb-2">
                      Температура
                    </label>
                    <input
                      v-model.number="form.llm_params.temperature"
                      type="number"
                      min="0"
                      max="2"
                      step="0.1"
                      class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                      placeholder="0.7"
                    />
                  </div>

                  <div>
                    <label class="block text-sm font-medium text-slate-700 mb-2">
                      Макс. токенов
                    </label>
                    <input
                      v-model.number="form.llm_params.max_tokens"
                      type="number"
                      min="1"
                      max="4000"
                      class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                      placeholder="1000"
                    />
                  </div>
                </div>

                <!-- Кнопки -->
                <div class="flex gap-3 pt-4">
                  <button
                    type="button"
                    @click="$emit('close')"
                    class="flex-1 px-4 py-2 text-slate-700 bg-slate-100 rounded-lg hover:bg-slate-200 transition-colors"
                  >
                    Отмена
                  </button>
                  <button
                    type="submit"
                    :disabled="isBusy"
                    class="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
                  >
                    <Loader2 v-if="isBusy" class="h-4 w-4 animate-spin" />
                    {{ submitButtonLabel }}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { X, Loader2 } from 'lucide-vue-next'
import { useAgents } from '../composables/useAgents'
import { useActiveModels } from '../composables/useActiveModels'
import { useToast } from '~/composables/useToast'
import { useAgentPromptEnhancement, type PromptEnhancementStep } from '~/composables/useAgentPromptEnhancement'

interface Props {
  isOpen: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  close: []
  agentCreated: [agent: any]
}>()

const { createAgent, isLoading } = useAgents()
const { info: toastInfo, success: toastSuccess } = useToast()
const {
  modelGroups,
  isLoading: isLoadingModels,
  error: modelsError,
  fetchActiveModels,
  getFirstModelValue
} = useActiveModels()
const { enhancePrompt } = useAgentPromptEnhancement()
const creationMode = ref<'manual' | 'enhanced'>('manual')
const isSubmitting = ref(false)
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

const isBusy = computed(() => isLoading.value || isSubmitting.value)
const submitButtonLabel = computed(() => {
  if (!isBusy.value) return 'Создать агента'
  if (creationMode.value !== 'enhanced') return 'Создание...'
  return 'Создаем и улучшаем...'
})

// Форма создания агента
const form = reactive({
  name: '',
  system_prompt: '',
  model: '',
  llm_params: {
    temperature: 0.7,
    max_tokens: 1000
  }
})

const resetForm = () => {
  form.name = ''
  form.system_prompt = ''
  form.model = ''
  form.llm_params.temperature = 0.7
  form.llm_params.max_tokens = 1000
  creationMode.value = 'manual'
  setProgressStep(1, 'Подготовка')
  elapsedSeconds.value = 0
}

// Обработчик отправки формы
const handleSubmit = async () => {
  try {
    isSubmitting.value = true
    setProgressStep(1, 'Создаем агента')
    if (creationMode.value === 'enhanced') {
      startElapsedTimer()
    }

    const newAgent = await createAgent({
      ...form,
      status: 'draft' as const,
      version: 1
    })

    if (creationMode.value === 'enhanced') {
      const enhancementResult = await enhancePrompt({
        agentId: newAgent.id,
        sourcePrompt: form.system_prompt,
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

    emit('agentCreated', newAgent)
    resetForm()

    emit('close')

    // Перенаправление на страницу редактирования
    await navigateTo(`/agents/${newAgent.id}`)
  } catch (err) {
    console.error('Ошибка создания агента:', err)
  } finally {
    stopElapsedTimer()
    isSubmitting.value = false
  }
}

// Сброс формы при закрытии
watch(() => props.isOpen, async (isOpen) => {
  if (isOpen) {
    await fetchActiveModels()
    if (!form.model) {
      form.model = getFirstModelValue()
    }
    return
  }

  resetForm()
})

onBeforeUnmount(() => {
  stopElapsedTimer()
})
</script>