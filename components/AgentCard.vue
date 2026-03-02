<template>
  <NuxtLink
    :to="`/agents/${agent.id}/prompt`"
    class="bg-background rounded-xl border border-border p-4 sm:p-5 hover:shadow-md transition-all cursor-pointer block group"
  >
    <!-- Header: avatar + name + status badge -->
    <div class="flex items-center gap-3 mb-4">
      <div
        class="flex items-center justify-center w-10 h-10 rounded-lg bg-gradient-to-br shrink-0"
        :class="avatarColor"
      >
        <Bot class="h-5 w-5 text-white" />
      </div>
      <div class="min-w-0 flex-1">
        <h3 class="text-sm font-semibold text-foreground truncate group-hover:text-primary transition-colors">
          {{ agent.name }}
        </h3>
        <span
          class="inline-flex items-center gap-1 mt-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium"
          :class="agent.status === 'published'
            ? 'bg-green-50 text-green-700'
            : 'bg-amber-50 text-amber-700'"
        >
          <span
            class="w-1.5 h-1.5 rounded-full"
            :class="agent.status === 'published' ? 'bg-green-500' : 'bg-amber-500'"
          />
          {{ agent.status === 'published' ? 'Активен' : 'Черновик' }}
        </span>
      </div>
    </div>

    <!-- Stats: colored pills -->
    <div class="grid grid-cols-2 gap-2">
      <div class="rounded-lg bg-sky-50 px-3 py-2">
        <p class="text-[10px] font-medium text-sky-600 uppercase tracking-wide">Модель</p>
        <p class="text-sm font-semibold text-sky-900 truncate mt-0.5">{{ modelName }}</p>
      </div>
      <div class="rounded-lg bg-violet-50 px-3 py-2">
        <p class="text-[10px] font-medium text-violet-600 uppercase tracking-wide">Версия</p>
        <p class="text-sm font-semibold text-violet-900 mt-0.5">v{{ agent.version }}</p>
      </div>
      <div class="rounded-lg bg-amber-50 px-3 py-2">
        <p class="text-[10px] font-medium text-amber-600 uppercase tracking-wide">Обновлён</p>
        <p class="text-sm font-semibold text-amber-900 mt-0.5">{{ updatedAt }}</p>
      </div>
      <div class="rounded-lg bg-emerald-50 px-3 py-2">
        <p class="text-[10px] font-medium text-emerald-600 uppercase tracking-wide">USD</p>
        <p class="text-sm font-semibold text-emerald-900 mt-0.5">{{ costUsd }}</p>
      </div>
      <div class="rounded-lg bg-rose-50 px-3 py-2 col-span-2">
        <p class="text-[10px] font-medium text-rose-600 uppercase tracking-wide">RUB</p>
        <p class="text-sm font-semibold text-rose-900 mt-0.5">{{ costRub }}</p>
      </div>
    </div>
  </NuxtLink>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Bot } from 'lucide-vue-next'
import type { Agent } from '~/composables/useAgents'

type Props = {
  agent: Agent
}

const props = defineProps<Props>()

const gradients = [
  'from-sky-500 to-cyan-500',
  'from-purple-500 to-pink-500',
  'from-emerald-500 to-cyan-500',
  'from-indigo-500 to-purple-600',
  'from-amber-500 to-orange-500',
  'from-rose-500 to-pink-500',
]

const colorIndex = computed(() => {
  let hash = 0
  for (const ch of props.agent.id) hash = ((hash << 5) - hash + ch.charCodeAt(0)) | 0
  return Math.abs(hash) % gradients.length
})

const avatarColor = computed(() => gradients[colorIndex.value])

const modelName = computed(() =>
  props.agent.model?.split(':')[1] || props.agent.model || '—'
)

const updatedAt = computed(() =>
  new Date(props.agent.updated_at).toLocaleDateString('ru-RU')
)

const formatCost = (value: string | undefined, currency: 'USD' | 'RUB') => {
  const amount = Number(value ?? 0)
  const safe = Number.isFinite(amount) ? amount : 0
  const maxFrac = safe !== 0 && Math.abs(safe) < 1 ? 4 : 2
  return new Intl.NumberFormat(currency === 'USD' ? 'en-US' : 'ru-RU', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: maxFrac,
  }).format(safe)
}

const costUsd = computed(() => formatCost(props.agent.total_cost_usd, 'USD'))
const costRub = computed(() => formatCost(props.agent.total_cost_rub, 'RUB'))
</script>
