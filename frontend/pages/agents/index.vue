<template>
  <div class="w-full px-5 py-5 flex flex-col gap-6">
    <!-- TopBar: Создать агента -->
    <Teleport v-if="isMounted" to="#topbar-actions">
      <NuxtLink
        v-if="isAuthenticated && canEditAgents"
        to="/agents/new"
        class="inline-flex items-center gap-1.5 rounded-xl bg-primary px-4 py-1.5 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
      >
        <PlusIcon class="h-3.5 w-3.5" />
        Создать агента
      </NuxtLink>
    </Teleport>

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
              Войдите в систему, чтобы получить доступ к управлению агентами
            </p>
          </div>
        </div>
        <button
          @click="showAuthModal = true"
          class="rounded-xl bg-yellow-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-yellow-700"
        >
          Войти
        </button>
      </div>
    </div>

    <!-- Stats Row -->
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
      <div class="rounded-3xl border border-slate-100 bg-white p-5 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
        <p class="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-1">Активные</p>
        <p class="text-3xl font-black text-emerald-600">{{ activeAgentsCount }}</p>
      </div>
      <div class="rounded-3xl border border-slate-100 bg-white p-5 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
        <p class="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-1">Всего агентов</p>
        <p class="text-3xl font-black text-slate-900">{{ totalAgentsCount }}</p>
      </div>
      <div class="rounded-3xl border border-slate-100 bg-white p-5 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
        <p class="text-[10px] font-black uppercase tracking-widest text-slate-400 mb-1">Черновики</p>
        <p class="text-3xl font-black text-primary">{{ draftAgentsCount }}</p>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="agentsLoading" class="flex justify-center py-8">
      <Loader2 class="h-8 w-8 text-primary animate-spin" />
    </div>

    <!-- Empty State -->
    <div v-else-if="agents.length === 0" class="rounded-3xl border-2 border-dashed border-slate-100 bg-white p-12 text-center">
      <Bot class="h-12 w-12 text-muted-foreground mx-auto mb-4" />
      <h3 class="mb-2 text-lg font-bold text-slate-900">Нет агентов</h3>
      <p class="text-muted-foreground text-sm mb-4">Создайте своего первого AI-агента</p>
      <NuxtLink
        v-if="isAuthenticated && canEditAgents"
        to="/agents/new"
        class="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
      >
        <PlusIcon class="h-4 w-4" />
        Создать агента
      </NuxtLink>
    </div>

    <!-- Agents Grid: 3 columns desktop, 1 column mobile -->
    <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      <AgentCard
        v-for="agent in agents"
        :key="agent.id"
        :agent="agent"
      />
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

import { ref, computed, onMounted, watch } from 'vue'
import { PlusIcon, AlertCircle, Bot, Loader2 } from 'lucide-vue-next'
import { useAgents } from '../../composables/useAgents'
import { useAuth } from '../../composables/useAuth'
import { usePermissions } from '../../composables/usePermissions'

const { pageTitle } = useLayoutState()
const { isAuthenticated } = useAuth()
const { canEditAgents } = usePermissions()
const { agents, fetchAgents, isLoading: agentsLoading } = useAgents()

const showAuthModal = ref(false)
const isMounted = ref(false)

const totalAgentsCount = computed(() => agents.value.length)
const activeAgentsCount = computed(() =>
  agents.value.filter((agent) => agent.status === 'published' && !agent.is_disabled).length,
)
const draftAgentsCount = computed(() =>
  agents.value.filter(a => a.status === 'draft').length
)

onMounted(async () => {
  isMounted.value = true
  pageTitle.value = 'Мои агенты'
  if (isAuthenticated.value) {
    await fetchAgents()
  }
})

watch(isAuthenticated, async (val) => {
  if (val) await fetchAgents()
})

const handleAuthenticated = () => {
  showAuthModal.value = false
}
</script>
