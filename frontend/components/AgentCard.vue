<template>
  <NuxtLink
    :to="`/agents/${agent.id}/prompt`"
    class="group relative block cursor-pointer overflow-hidden rounded-3xl border border-slate-100 bg-white p-5 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-all duration-500 hover:-translate-y-1 hover:shadow-[0_20px_40px_-12px_rgba(0,0,0,0.08)]"
  >
    <div class="absolute -right-8 -top-8 h-24 w-24 rounded-full bg-primary/5 transition-transform duration-700 group-hover:scale-150" />
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
          :class="agent.is_disabled
            ? 'bg-amber-50 text-amber-700'
            : agent.status === 'published'
            ? 'bg-green-50 text-green-700'
            : 'bg-amber-50 text-amber-700'"
        >
          <span
            class="w-1.5 h-1.5 rounded-full"
            :class="agent.is_disabled ? 'bg-amber-500' : (agent.status === 'published' ? 'bg-green-500' : 'bg-amber-500')"
          />
          {{ agent.is_disabled ? 'Отключен' : (agent.status === 'published' ? 'Активен' : 'Черновик') }}
        </span>
      </div>
    </div>

    <!-- Stats: colored pills -->
    <div class="grid grid-cols-2 gap-3">
      <div class="rounded-2xl bg-sky-50/60 px-3 py-2.5">
        <p class="text-[9px] font-black uppercase tracking-wider text-sky-600">Модель</p>
        <p class="text-sm font-semibold text-sky-900 truncate mt-0.5">{{ modelName }}</p>
      </div>
      <div class="rounded-2xl bg-violet-50/60 px-3 py-2.5">
        <p class="text-[9px] font-black uppercase tracking-wider text-violet-600">Версия</p>
        <p class="text-sm font-semibold text-violet-900 mt-0.5">v{{ agent.version }}</p>
      </div>
      <div class="rounded-2xl bg-amber-50/60 px-3 py-2.5">
        <p class="text-[9px] font-black uppercase tracking-wider text-amber-600">Обновлён</p>
        <p class="text-sm font-semibold text-amber-900 mt-0.5">{{ updatedAt }}</p>
      </div>
      <div class="rounded-2xl bg-emerald-50/60 px-3 py-2.5">
        <p class="text-[9px] font-black uppercase tracking-wider text-emerald-600">USD</p>
        <p class="text-sm font-semibold text-emerald-900 mt-0.5">{{ costUsd }}</p>
      </div>
      <div class="col-span-2 rounded-2xl bg-rose-50/60 px-3 py-2.5">
        <p class="text-[9px] font-black uppercase tracking-wider text-rose-600">RUB</p>
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
