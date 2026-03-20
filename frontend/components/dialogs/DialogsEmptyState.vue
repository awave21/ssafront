<template>
  <div class="flex-1 flex items-center justify-center p-8">
    <div class="text-center max-w-sm">
      <!-- Icon -->
      <div class="w-20 h-20 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-6">
        <component :is="icon" class="w-10 h-10 text-slate-400" />
      </div>

      <!-- Title -->
      <h3 class="text-lg font-semibold text-slate-900 mb-2">
        {{ title }}
      </h3>

      <!-- Description -->
      <p class="text-sm text-slate-500 mb-6">
        {{ description }}
      </p>

      <!-- Action Button -->
      <button
        v-if="showAction"
        @click="$emit('create')"
        class="inline-flex items-center gap-2 px-6 py-3 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-sm font-semibold transition-colors"
      >
        <Plus class="w-4 h-4" />
        {{ actionLabel }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { MessageSquare, MessageCircle, AlertCircle, Plus } from 'lucide-vue-next'

type EmptyStateType = 'no-agent' | 'no-dialog' | 'no-messages' | 'error'

const props = withDefaults(defineProps<{
  type: EmptyStateType
  errorMessage?: string
}>(), {
  type: 'no-dialog'
})

defineEmits<{
  (e: 'create'): void
  (e: 'retry'): void
}>()

const config = computed(() => {
  switch (props.type) {
    case 'no-agent':
      return {
        icon: MessageSquare,
        title: 'Выберите агента',
        description: 'Выберите агента из списка слева, чтобы начать диалог.',
        showAction: false,
        actionLabel: ''
      }
    case 'no-dialog':
      return {
        icon: MessageCircle,
        title: 'Выберите диалог',
        description: 'Выберите существующий диалог или создайте новый, чтобы начать общение с агентом.',
        showAction: true,
        actionLabel: 'Новый диалог'
      }
    case 'no-messages':
      return {
        icon: MessageSquare,
        title: 'Начните диалог',
        description: 'Напишите сообщение, чтобы начать общение с агентом.',
        showAction: false,
        actionLabel: ''
      }
    case 'error':
      return {
        icon: AlertCircle,
        title: 'Ошибка загрузки',
        description: props.errorMessage || 'Не удалось загрузить данные. Попробуйте обновить страницу.',
        showAction: true,
        actionLabel: 'Повторить'
      }
    default:
      return {
        icon: MessageSquare,
        title: 'Нет данных',
        description: 'Данные отсутствуют.',
        showAction: false,
        actionLabel: ''
      }
  }
})

const icon = computed(() => config.value.icon)
const title = computed(() => config.value.title)
const description = computed(() => config.value.description)
const showAction = computed(() => config.value.showAction)
const actionLabel = computed(() => config.value.actionLabel)
</script>
