<template>
  <TooltipProvider :delay-duration="0">
  <aside
    v-bind="$attrs"
    class="bg-sidebar border-r border-border h-screen lg:h-full lg:relative fixed inset-y-0 left-0 z-50 transition-all duration-300 ease-in-out flex flex-col overflow-hidden"
    :class="[isCollapsed ? 'w-16' : 'w-64']"
  >
    <!-- Top Section — бренд (глобально) / переключатель агента (в контексте агента) -->
    <div class="shrink-0 border-b border-border">
      <!-- Свёрнутый вид: иконка-бот (в агенте) / логотип (глобально) -->
      <button
        v-if="isCollapsed && isAgentDetail"
        @click="goToCurrentAgent"
        class="mx-auto my-3 flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary transition-colors hover:bg-primary/15"
        title="Текущий агент"
      >
        <Bot class="h-4 w-4" />
      </button>
      <div v-else-if="isCollapsed" class="flex h-[60px] items-center justify-center">
        <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-sidebar-primary">
          <span class="text-xs font-bold text-sidebar-primary-foreground">CM</span>
        </div>
      </div>

      <!-- Развёрнутый вид, контекст агента: AgentPicker -->
      <div v-else-if="isAgentDetail" class="relative px-3 pb-2.5 pt-3.5">
        <DropdownMenuRoot>
          <DropdownMenuTrigger as-child>
            <button
              class="flex w-full items-center gap-2.5 rounded-xl bg-primary/10 p-2.5 text-left outline outline-1 -outline-offset-1 outline-primary/20 transition-colors hover:bg-primary/15 focus:outline-primary/40"
            >
              <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white">
                <Bot class="h-4 w-4 text-primary" />
              </div>
              <div class="flex min-w-0 flex-1 flex-col gap-0.5">
                <span class="truncate text-[13px] font-semibold leading-[17px] text-primary">
                  {{ currentAgent?.name || 'Выберите агента' }}
                </span>
                <span class="flex items-center gap-1.5">
                  <span class="h-1.5 w-1.5 shrink-0 rounded-full" :class="statusDotClass" />
                  <span class="truncate text-[11px] text-muted-foreground">{{ statusLabel }}</span>
                </span>
              </div>
              <ChevronsUpDown class="h-3.5 w-3.5 shrink-0 text-primary" />
            </button>
          </DropdownMenuTrigger>

          <DropdownMenuPortal>
            <DropdownMenuContent
              side="bottom"
              align="start"
              :side-offset="6"
              class="z-[9999] max-h-80 min-w-[232px] overflow-y-auto rounded-xl border border-border bg-background p-1 shadow-lg"
            >
              <DropdownMenuItem
                v-for="agent in agents"
                :key="agent.id"
                class="flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 outline-none transition-colors hover:bg-muted focus:bg-muted"
                @select="selectAgent(agent.id)"
              >
                <div class="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                  <Bot class="h-3.5 w-3.5 text-primary" />
                </div>
                <span class="min-w-0 flex-1 truncate text-sm text-foreground">{{ agent.name }}</span>
                <Check v-if="agent.id === currentAgentId" class="h-4 w-4 shrink-0 text-primary" />
              </DropdownMenuItem>

              <div v-if="!agents.length" class="px-3 py-3 text-center text-sm text-muted-foreground">
                Нет доступных агентов
              </div>

              <DropdownMenuSeparator class="my-1 h-px bg-border" />
              <DropdownMenuItem
                class="flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 text-sm text-foreground outline-none transition-colors hover:bg-muted focus:bg-muted"
                @select="router.push('/agents')"
              >
                <Bot class="h-4 w-4 text-muted-foreground" />
                Все агенты
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenuPortal>
        </DropdownMenuRoot>

        <!-- Mobile close button -->
        <button
          @click="emit('close')"
          class="absolute right-4 top-1 rounded-lg p-1.5 text-foreground hover:bg-muted lg:hidden"
        >
          <X class="h-5 w-5" />
        </button>
      </div>

      <!-- Развёрнутый вид, глобально: бренд ChatMedBot -->
      <div v-else class="relative flex h-[60px] items-center gap-3 px-3">
        <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-sidebar-primary">
          <span class="text-xs font-bold text-sidebar-primary-foreground">CM</span>
        </div>
        <span class="truncate text-lg font-bold text-foreground">ChatMedBot</span>
        <button
          @click="emit('close')"
          class="ml-auto rounded-lg p-2 text-foreground hover:bg-muted lg:hidden"
        >
          <X class="h-5 w-5" />
        </button>
      </div>
    </div>

    <!-- Middle Section (Scrollable Navigation) -->
    <nav class="flex-1 p-3 overflow-y-auto min-h-0">
      <ul class="flex flex-col gap-2">
        <li v-for="item in currentMenuItems" :key="item.id || item.name || item.path">
          <TooltipRoot :disabled="!isCollapsed">
            <TooltipTrigger as-child>
              <NuxtLink
                :to="item.path"
                @click="emit('close')"
                class="flex items-center text-sm font-medium rounded-md transition-colors"
                :class="[
                  isMenuItemActive(item.path)
                    ? 'bg-sidebar-primary text-sidebar-primary-foreground'
                    : 'text-sidebar-foreground hover:bg-muted',
                  isCollapsed ? 'w-10 h-10 justify-center' : 'px-3 py-2 gap-3'
                ]"
              >
                <component :is="item.icon" class="w-5 h-5 shrink-0" />
                <span v-show="!isCollapsed" class="whitespace-nowrap">{{ item.name }}</span>
              </NuxtLink>
            </TooltipTrigger>
            <TooltipPortal>
              <TooltipContent side="right" :side-offset="12" class="z-[9999] rounded-md bg-foreground px-2.5 py-1.5 text-xs text-background shadow-md">
                {{ item.name }}
              </TooltipContent>
            </TooltipPortal>
          </TooltipRoot>
        </li>
      </ul>
    </nav>

    <!-- Bottom Section (User Info with Dropdown) -->
    <div class="mt-auto border-t border-border bg-sidebar shrink-0 p-3">
      <DropdownMenuRoot>
        <DropdownMenuTrigger as-child>
          <button
            class="w-full flex items-center gap-3 rounded-lg p-2 text-left transition-colors hover:bg-muted focus:outline-none"
            :class="[isCollapsed ? 'justify-center' : '']"
          >
            <div class="w-9 h-9 bg-sidebar-primary rounded-lg flex items-center justify-center shrink-0">
              <span class="text-sidebar-primary-foreground font-bold text-xs">
                {{ user?.full_name ? user.full_name.split(' ').map(n => n.charAt(0)).join('').toUpperCase() : user?.email?.charAt(0).toUpperCase() || 'U' }}
              </span>
            </div>
            <div v-show="!isCollapsed" class="min-w-0 flex-1">
              <p class="text-sm font-semibold text-foreground truncate leading-tight">{{ user?.full_name || 'Пользователь' }}</p>
              <p class="text-xs text-muted-foreground truncate leading-tight">{{ user?.email || 'Email не указан' }}</p>
            </div>
            <ChevronsUpDown v-show="!isCollapsed" class="h-4 w-4 text-muted-foreground shrink-0" />
          </button>
        </DropdownMenuTrigger>

        <DropdownMenuPortal>
          <DropdownMenuContent
            :side="isCollapsed ? 'right' : 'top'"
            :side-offset="8"
            :align="isCollapsed ? 'end' : 'start'"
            class="z-[9999] min-w-56 rounded-xl bg-background border border-border shadow-lg p-1"
          >
            <!-- User info header -->
            <div class="flex items-center gap-3 px-3 py-2.5">
              <div class="w-9 h-9 bg-sidebar-primary rounded-lg flex items-center justify-center shrink-0">
                <span class="text-sidebar-primary-foreground font-bold text-xs">
                  {{ user?.full_name ? user.full_name.split(' ').map(n => n.charAt(0)).join('').toUpperCase() : user?.email?.charAt(0).toUpperCase() || 'U' }}
                </span>
              </div>
              <div class="min-w-0 flex-1">
                <p class="text-sm font-semibold text-foreground truncate">{{ user?.full_name || 'Пользователь' }}</p>
                <p class="text-xs text-muted-foreground truncate">{{ user?.email || 'Email не указан' }}</p>
                <p class="text-xs text-primary font-medium mt-0.5">{{ user?.role ? getRoleDisplayName(user.role) : 'Роль не указана' }}</p>
              </div>
            </div>

            <template v-if="hasScope('settings:write')">
              <DropdownMenuSeparator class="h-px bg-border my-1" />
              <DropdownMenuItem
                class="flex items-center gap-2 px-3 py-2 text-sm text-foreground rounded-lg cursor-pointer outline-none hover:bg-muted focus:bg-muted transition-colors"
                @select="router.push('/settings')"
              >
                <Settings class="h-4 w-4 text-muted-foreground" />
                Настройки
              </DropdownMenuItem>
            </template>

            <DropdownMenuSeparator class="h-px bg-border my-1" />

            <DropdownMenuItem
              class="flex items-center gap-2 px-3 py-2 text-sm text-red-600 rounded-lg cursor-pointer outline-none hover:bg-red-50 focus:bg-red-50 transition-colors"
              @select="handleLogout"
            >
              <LogOut class="h-4 w-4" />
              Выйти
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenuPortal>
      </DropdownMenuRoot>
    </div>
  </aside>
  </TooltipProvider>
</template>

<script setup lang="ts">
defineOptions({
  inheritAttrs: false
})

import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  LayoutDashboard,
  Bot,
  MessageSquare,
  Activity,
  History,
  CreditCard,
  Shield,
  Settings,
  X,
  LogOut,
  ChevronsUpDown,
  Check,
  UsersRound,
  Award,
} from 'lucide-vue-next'
import {
  TooltipRoot,
  TooltipTrigger,
  TooltipContent,
  TooltipPortal,
  TooltipProvider,
  DropdownMenuRoot,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuPortal,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from 'radix-vue'
import { useLocalStorage } from '@vueuse/core'
import { useAuth } from '../composables/useAuth'
import { useAgents } from '../composables/useAgents'
import { usePermissions } from '~/composables/usePermissions'
import { useLayoutState } from '~/composables/useLayoutState'

// Auth composable
const { user, logout } = useAuth()
const route = useRoute()
const router = useRouter()

// Use shared layout state
const { isCollapsed } = useLayoutState()
const { hasScope } = usePermissions()

// Список агентов для переключателя
const { agents, fetchAgents } = useAgents()
onMounted(() => {
  if (!agents.value.length) fetchAgents().catch(() => {})
})

const emit = defineEmits<{
  close: []
}>()

// Функция для преобразования ролей в русские названия
const getRoleDisplayName = (role: string): string => {
  const roleMap: Record<string, string> = {
    'owner': 'Владелец',
    'admin': 'Администратор',
    'manager': 'Менеджер',
    'user': 'Пользователь',
    'viewer': 'Наблюдатель'
  }
  return roleMap[role] || role
}

const handleLogout = () => {
  logout()
  // Перенаправление происходит внутри logout()
}

const isAgentDetail = computed(() => {
  return route.name?.toString().startsWith('agents-id')
})

// --- Текущий агент (для переключателя и агентских пунктов) ---
// В детальном виде агента источник истины — id из роута; иначе — последний выбранный.
const persistedAgentId = useLocalStorage<string>('sidebar-current-agent-id', '')
const routeAgentId = computed(() => (isAgentDetail.value ? String(route.params.id || '') : ''))
watch(routeAgentId, (id) => { if (id) persistedAgentId.value = id }, { immediate: true })

const currentAgentId = computed(() => routeAgentId.value || persistedAgentId.value || '')
const currentAgent = computed(() => agents.value.find(a => a.id === currentAgentId.value) || null)

const statusLabel = computed(() => {
  const agent = currentAgent.value
  if (!agent) return 'Не выбран'
  if (agent.is_disabled) return 'Отключён'
  return agent.status === 'published' ? 'Отвечает сам' : 'Черновик'
})
const statusDotClass = computed(() => {
  const agent = currentAgent.value
  if (!agent) return 'bg-slate-300'
  if (agent.is_disabled) return 'bg-slate-400'
  return agent.status === 'published' ? 'bg-green-500' : 'bg-amber-500'
})

const goToCurrentAgent = () => {
  router.push(currentAgentId.value ? `/agents/${currentAgentId.value}` : '/agents')
}

const selectAgent = (id: string) => {
  persistedAgentId.value = id
  if (isAgentDetail.value) {
    // остаёмся в том же подразделе, меняя id агента
    const newPath = route.path.replace(/\/agents\/[^/]+/, `/agents/${id}`)
    router.push(newPath)
  } else {
    router.push(`/agents/${id}`)
  }
  emit('close')
}

// Глобальные пункты меню — видны всегда, в т.ч. внутри агента.
const menuItems = [
  { name: 'Панель управления', path: '/dashboard', icon: LayoutDashboard },
  { name: 'Мои агенты', path: '/agents', icon: Bot },
  { name: 'Диалоги', path: '/dialogs', icon: MessageSquare },
  { name: 'Пациенты', path: '/patients', icon: UsersRound },
  { name: 'Аналитика', path: '/analytics', icon: Activity },
  { name: 'Мотивация', path: '/motivation', icon: Award },
  { name: 'История', path: '/tool-calls-history', icon: History },
  { name: 'Платежи', path: '/billing', icon: CreditCard },
  { name: 'Учётные данные', path: '/credentials', icon: Shield, requiresScope: 'agents:write' },
  { name: 'Настройки', path: '/settings', icon: Settings, requiresScope: 'settings:write' },
]

// Пункты меню всегда глобальные — внутри агента не подменяются.
const currentMenuItems = computed<any[]>(() =>
  menuItems
    .filter(item => !('requiresScope' in item && item.requiresScope) || hasScope(item.requiresScope))
    .map(item => ({ ...item, id: item.path }))
)

const activeMenuPath = computed(() => {
  const currentPath = route.path || ''
  const candidates = currentMenuItems.value
    .map(item => item.path)
    .filter((path): path is string => typeof path === 'string')
    .filter(path => currentPath === path || (path !== '/' && currentPath.startsWith(path + '/')))
  if (!candidates.length) return ''
  return candidates.sort((a, b) => b.length - a.length)[0]
})

const isMenuItemActive = (path: string) => activeMenuPath.value === path
</script>
