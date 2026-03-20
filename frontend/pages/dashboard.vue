<template>
  <div class="w-full px-5 py-5 flex flex-col gap-6">
    <!-- Auth Status Banner -->
    <div v-if="!isAuthenticated" class="rounded-3xl border border-yellow-200 bg-yellow-50 p-5">
            <div class="flex items-center justify-between">
              <div class="flex items-center">
                <AlertCircle class="h-5 w-5 text-yellow-400 mr-3" />
                <div>
                  <h3 class="text-sm font-medium text-yellow-800">
                    Требуется аутентификация
                  </h3>
                  <p class="text-sm text-yellow-700 mt-1">
                    Зарегистрируйтесь или войдите в систему
                  </p>
                </div>
              </div>
              <div class="flex gap-2">
                <button
                  @click="showAuthModal = true"
                  class="rounded-xl bg-yellow-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-yellow-700"
                >
                  Войти
                </button>
              </div>
            </div>
          </div>


    <!-- Metrics Cards -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 lg:gap-5">
            <MetricCard
              title="Всего агентов"
              :value="String(agents.length)"
              description="Все зарегистрированные агенты"
              :trend="activeAgentsCount + ' активных'"
              type="info"
              icon="BarChart2"
            />
            <MetricCard
              title="Активных агентов"
              :value="String(activeAgentsCount)"
              description="Опубликованные и работающие"
              trend="Все системы в норме"
              type="positive"
              icon="Target"
            />
            <MetricCard
              title="Черновики"
              :value="String(agents.filter(a => a.status === 'draft').length)"
              description="Агенты в разработке"
              trend="Ожидают публикации"
              type="warning"
              icon="FileText"
            />
            <div class="bg-white rounded-2xl border border-slate-200 p-5 sm:p-6 shadow-sm">
              <div class="flex items-center justify-between mb-4">
                <p class="text-xs sm:text-sm font-normal text-slate-600">
                  Остаток баланса (RUB)
                </p>
                <div class="flex items-center justify-center w-9 h-9 sm:w-10 sm:h-10 rounded-lg bg-emerald-50">
                  <Wallet class="h-4 w-4 sm:h-5 sm:w-5 text-emerald-600" />
                </div>
              </div>

              <div v-if="isBalanceLoading" class="space-y-3">
                <Skeleton class="h-10 w-40 rounded-md" />
                <Skeleton class="h-4 w-56 rounded-md" />
              </div>

              <div v-else-if="balanceError" class="space-y-3">
                <p class="text-sm text-red-500">
                  {{ balanceError }}
                </p>
                <button
                  class="inline-flex items-center rounded-lg border border-border px-3 py-1.5 text-xs font-semibold text-foreground transition-colors hover:bg-muted"
                  @click="loadBalance"
                >
                  Повторить
                </button>
              </div>

              <div v-else>
                <p class="text-3xl sm:text-4xl font-bold mb-2" :class="remainingUsdValue < 0 ? 'text-red-600' : 'text-slate-900'">
                  {{ formatRubAmountFromUsd(tenantBalance.remaining_usd, 2, 2) }}
                </p>
                <p class="text-xs sm:text-sm text-slate-500 mb-3">
                  Общий остаток организации
                </p>
                <p class="text-xs sm:text-sm font-medium text-slate-600">
                  Потрачено: {{ formatRubAmountFromUsd(spentUsdValue, 2, 2) }}
                </p>
              </div>
            </div>
    </div>

    <!-- Agents Section -->
    <div>
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-4 lg:mb-6 gap-3 sm:gap-0">
        <h2 class="text-lg sm:text-xl font-bold text-slate-900">
                Подключенные агенты
        </h2>
        <NuxtLink
          to="/agents"
          class="flex items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90 sm:text-base"
        >
          Все агенты
        </NuxtLink>
      </div>

      <!-- Loading State -->
      <div v-if="agentsLoading" class="flex justify-center py-8">
        <Loader2 class="h-8 w-8 text-primary animate-spin" />
      </div>

      <!-- Empty State -->
      <div v-else-if="agents.length === 0" class="rounded-3xl border-2 border-dashed border-slate-100 bg-white p-12 text-center">
        <Bot class="h-12 w-12 text-muted-foreground mx-auto mb-4" />
        <h3 class="mb-2 text-lg font-bold text-slate-900">Нет агентов</h3>
        <p class="text-muted-foreground text-sm mb-4">Создайте своего первого AI-агента</p>
        <NuxtLink
          to="/agents"
          class="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
        >
          Все агенты
        </NuxtLink>
      </div>

      <!-- Agents Grid -->
      <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 lg:gap-5">
        <AgentCard
          v-for="agent in agents"
          :key="agent.id"
          :agent="agent"
        />
      </div>
    </div>

    <!-- Recent Activity -->
    <div>
      <h2 class="text-lg sm:text-xl font-bold text-slate-900 mb-4 lg:mb-6">
        Недавняя активность
      </h2>
      <div class="overflow-hidden rounded-3xl border border-slate-100 bg-white shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
        <div v-if="isLoadingActivities" class="flex justify-center py-8">
          <Loader2 class="h-6 w-6 text-primary animate-spin" />
        </div>
        <div v-else-if="recentActivities.length === 0" class="px-6 py-8 text-center text-sm text-muted-foreground">
          Нет активности
        </div>
        <div v-else class="divide-y divide-border">
          <ActivityItem
            v-for="activity in visibleActivities"
            :key="activity.id"
            :activity="activity"
          />
        </div>
        <button
          v-if="recentActivities.length > 3 && !isActivitiesExpanded"
          @click="isActivitiesExpanded = true"
          class="w-full border-t border-slate-100 px-4 py-3 text-sm font-semibold text-primary transition-colors hover:bg-slate-50"
        >
          Показать ещё {{ recentActivities.length - 3 }}
        </button>
        <button
          v-else-if="isActivitiesExpanded && recentActivities.length > 3"
          @click="isActivitiesExpanded = false"
          class="w-full border-t border-slate-100 px-4 py-3 text-sm font-semibold text-primary transition-colors hover:bg-slate-50"
        >
          Свернуть
        </button>
      </div>
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
// Page meta
definePageMeta({
  middleware: 'auth'
})

import { ref, computed, onMounted, watch } from 'vue'
import { CalendarIcon, ChevronDownIcon, AlertCircle, Bot, Loader2, Wallet } from 'lucide-vue-next'
import { useAuth } from '../composables/useAuth'
import { useAgents } from '../composables/useAgents'
import { useApiFetch } from '../composables/useApiFetch'
import { formatRubAmountFromUsd, useTenantBalance } from '../composables/useTenantBalance'
import type { Dialog } from '../types/dialogs'
import Skeleton from '~/components/ui/skeleton/Skeleton.vue'

// Layout state
const { pageTitle } = useLayoutState()

// Auth state
const { isAuthenticated, user } = useAuth()
const showAuthModal = ref(false)

// Auth handler
const handleAuthenticated = () => {
  showAuthModal.value = false
  // Можно обновить данные после аутентификации
}


// Agents data (real)
const { agents, fetchAgents, isLoading: agentsLoading } = useAgents()
const {
  balance: tenantBalance,
  error: balanceError,
  isLoading: isBalanceLoading,
  fetchBalance,
  remainingUsdValue,
  spentUsdValue,
} = useTenantBalance()

const loadAgents = () => {
  if (isAuthenticated.value) {
    fetchAgents()
  }
}

const activeAgentsCount = computed(() =>
  agents.value.filter((agent) => agent.status === 'published' && !agent.is_disabled).length,
)

const loadBalance = async () => {
  if (!isAuthenticated.value) return
  try {
    await fetchBalance()
  } catch {
    // Отображаем локальную ошибку в карточке.
  }
}

onMounted(() => {
  pageTitle.value = 'Панель управления'
  loadAgents()
  loadBalance()
})

watch(isAuthenticated, (val) => {
  if (val) {
    loadAgents()
    loadBalance()
  }
})

// Recent activities — real data from agent dialogs
const apiFetch = useApiFetch()
const recentDialogs = ref<(Dialog & { agentName: string })[]>([])
const isLoadingActivities = ref(false)
const isActivitiesExpanded = ref(false)

const formatRelativeTime = (dateStr: string): string => {
  const now = Date.now()
  const diff = now - new Date(dateStr).getTime()
  if (diff < 0) return 'только что'

  const seconds = Math.floor(diff / 1000)
  if (seconds < 60) return 'только что'

  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes} ${pluralize(minutes, 'минуту', 'минуты', 'минут')} назад`

  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} ${pluralize(hours, 'час', 'часа', 'часов')} назад`

  const days = Math.floor(hours / 24)
  if (days < 7) return `${days} ${pluralize(days, 'день', 'дня', 'дней')} назад`

  return new Date(dateStr).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}

const pluralize = (n: number, one: string, few: string, many: string): string => {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod100 >= 11 && mod100 <= 19) return many
  if (mod10 === 1) return one
  if (mod10 >= 2 && mod10 <= 4) return few
  return many
}

const fetchRecentActivities = async () => {
  if (!agents.value.length) return
  isLoadingActivities.value = true
  try {
    const results: (Dialog & { agentName: string })[] = []
    await Promise.all(
      agents.value.map(async (agent) => {
        try {
          const response = await apiFetch<{ dialogs: Dialog[] } | Dialog[]>(
            `agents/${agent.id}/dialogs`
          )
          const dialogsList = Array.isArray(response)
            ? response
            : (response?.dialogs ?? [])
          for (const d of dialogsList) {
            results.push({ ...d, agentName: agent.name })
          }
        } catch {
          // skip agents with no dialogs
        }
      })
    )
    recentDialogs.value = results
      .filter(d => d.last_message_at)
      .sort((a, b) => new Date(b.last_message_at!).getTime() - new Date(a.last_message_at!).getTime())
      .slice(0, 10)
  } finally {
    isLoadingActivities.value = false
  }
}

const ACTIVITY_COLORS = [
  'from-sky-500 to-cyan-500',
  'from-purple-500 to-pink-500',
  'from-emerald-500 to-cyan-500',
  'from-amber-500 to-orange-500',
  'from-indigo-500 to-blue-500'
]

const recentActivities = computed(() => {
  if (!recentDialogs.value.length) {
    // Fallback: show agent update activity if no dialogs yet
    if (!agents.value.length) return []
    return [...agents.value]
      .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
      .slice(0, 5)
      .map((agent, i) => ({
        id: i,
        title: `${agent.name} — ${agent.status === 'published' ? 'опубликован' : 'черновик'}`,
        time: formatRelativeTime(agent.updated_at),
        icon: agent.status === 'published' ? 'UserCheck' : 'FileCheck',
        color: ACTIVITY_COLORS[i % ACTIVITY_COLORS.length]
      }))
  }

  return recentDialogs.value.map((d, i) => {
    const preview = d.last_message_preview
      ? (d.last_message_preview.length > 60 ? d.last_message_preview.slice(0, 60) + '…' : d.last_message_preview)
      : 'новый диалог'

    return {
      id: i,
      title: `${d.agentName}: ${preview}`,
      time: formatRelativeTime(d.last_message_at!),
      icon: d.platform === 'telegram' ? 'UserCheck' : 'Activity',
      color: ACTIVITY_COLORS[i % ACTIVITY_COLORS.length]
    }
  })
})

const visibleActivities = computed(() =>
  isActivitiesExpanded.value ? recentActivities.value : recentActivities.value.slice(0, 3)
)

watch(agents, (val) => {
  if (val.length) fetchRecentActivities()
})
</script>