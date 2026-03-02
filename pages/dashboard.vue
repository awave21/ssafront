<template>
  <div class="w-full px-5 py-5 flex flex-col gap-5">
    <!-- Auth Status Banner -->
    <div v-if="!isAuthenticated" class="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
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
                  class="px-4 py-2 bg-yellow-600 text-white text-sm font-medium rounded-lg hover:bg-yellow-700 transition-colors"
                >
                  Войти
                </button>
              </div>
            </div>
          </div>


    <!-- Metrics Cards -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 lg:gap-5">
            <MetricCard
              title="Всего агентов"
              :value="String(agents.length)"
              description="Все зарегистрированные агенты"
              :trend="agents.filter(a => a.status === 'published').length + ' активных'"
              type="info"
              icon="BarChart2"
            />
            <MetricCard
              title="Активных агентов"
              :value="String(agents.filter(a => a.status === 'published').length)"
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
    </div>

    <!-- Agents Section -->
    <div>
      <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-4 lg:mb-6 gap-3 sm:gap-0">
        <h2 class="text-lg sm:text-xl font-bold text-foreground">
                Подключенные агенты
        </h2>
        <NuxtLink
          to="/agents"
          class="flex items-center justify-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90 transition-colors text-sm sm:text-base"
        >
          Все агенты
        </NuxtLink>
      </div>

      <!-- Loading State -->
      <div v-if="agentsLoading" class="flex justify-center py-8">
        <Loader2 class="h-8 w-8 text-primary animate-spin" />
      </div>

      <!-- Empty State -->
      <div v-else-if="agents.length === 0" class="bg-background rounded-xl border border-border p-12 text-center">
        <Bot class="h-12 w-12 text-muted-foreground mx-auto mb-4" />
        <h3 class="text-lg font-medium text-foreground mb-2">Нет агентов</h3>
        <p class="text-muted-foreground text-sm mb-4">Создайте своего первого AI-агента</p>
        <NuxtLink
          to="/agents"
          class="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors text-sm"
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
      <h2 class="text-lg sm:text-xl font-bold text-foreground mb-4 lg:mb-6">
        Недавняя активность
      </h2>
      <div class="bg-background rounded-xl border border-border overflow-hidden">
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
          class="w-full px-4 py-3 text-sm font-medium text-primary hover:bg-muted/50 transition-colors border-t border-border"
        >
          Показать ещё {{ recentActivities.length - 3 }}
        </button>
        <button
          v-else-if="isActivitiesExpanded && recentActivities.length > 3"
          @click="isActivitiesExpanded = false"
          class="w-full px-4 py-3 text-sm font-medium text-primary hover:bg-muted/50 transition-colors border-t border-border"
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
import { CalendarIcon, ChevronDownIcon, AlertCircle, Bot, Loader2 } from 'lucide-vue-next'
import { useDashboardData } from '../composables/useDashboardData'
import { useAuth } from '../composables/useAuth'
import { useAgents } from '../composables/useAgents'
import { useApiFetch } from '../composables/useApiFetch'
import type { Dialog } from '../types/dialogs'

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


// Composables
const { data: dashboardData } = await useDashboardData()

// Agents data (real)
const { agents, fetchAgents, isLoading: agentsLoading } = useAgents()

const loadAgents = () => {
  if (isAuthenticated.value) {
    fetchAgents()
  }
}

onMounted(() => {
  pageTitle.value = 'Панель управления'
  loadAgents()
})

watch(isAuthenticated, (val) => {
  if (val) loadAgents()
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