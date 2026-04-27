<template>
  <TooltipProvider :delay-duration="0">
  <aside
    v-bind="$attrs"
    class="bg-sidebar border-r border-border h-screen lg:h-full lg:relative fixed inset-y-0 left-0 z-50 transition-all duration-300 ease-in-out flex flex-col overflow-hidden"
    :class="[isCollapsed ? 'w-16' : 'w-64']"
  >
    <!-- Top Section (Logo) — h-[60px] совпадает с DashboardTopBar -->
    <div class="h-[60px] px-3 border-b border-border shrink-0 flex items-center">
      <div class="flex items-center" :class="[isCollapsed ? 'justify-center' : 'gap-3']">
        <div class="w-8 h-8 bg-sidebar-primary rounded-lg flex items-center justify-center shrink-0">
          <span class="text-sidebar-primary-foreground font-bold text-xs">
            {{ tenant?.name ? tenant.name.split(' ').map(word => word.charAt(0)).join('').toUpperCase().slice(0, 2) : 'ОР' }}
          </span>
        </div>
        <span
          v-show="!isCollapsed"
          class="text-foreground font-bold text-lg whitespace-nowrap truncate"
        >
          {{ tenant?.name || '' }}
        </span>
        <!-- Mobile close button -->
        <button
          @click="emit('close')"
          class="lg:hidden ml-auto p-2 rounded-lg text-foreground hover:bg-muted"
        >
          <X class="h-5 w-5" />
        </button>
      </div>
    </div>

    <!-- Middle Section (Scrollable Navigation) -->
    <nav class="flex-1 p-3 overflow-y-auto min-h-0">
      <ul class="flex flex-col gap-2">
        <!-- Back Button for Agent Detail -->
        <li v-if="isAgentDetail">
          <TooltipRoot :disabled="!isCollapsed">
            <TooltipTrigger as-child>
              <button
                @click="handleBackToAgents"
                class="flex items-center text-sm font-medium rounded-md transition-colors text-sidebar-foreground hover:bg-muted"
                :class="[isCollapsed ? 'w-10 h-10 justify-center' : 'w-full px-3 py-2 gap-3']"
              >
                <ArrowLeft class="w-5 h-5 shrink-0" />
                <span v-show="!isCollapsed" class="whitespace-nowrap">Назад к агентам</span>
              </button>
            </TooltipTrigger>
            <TooltipPortal>
              <TooltipContent side="right" :side-offset="12" class="z-[9999] rounded-md bg-foreground px-2.5 py-1.5 text-xs text-background shadow-md">
                Назад к агентам
              </TooltipContent>
            </TooltipPortal>
          </TooltipRoot>
        </li>

        <li v-for="item in currentMenuItems" :key="item.name">
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

import { computed } from 'vue'
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
  ArrowLeft,
  Sparkles,
  Radio,
  Link,
  Database,
  Cpu,
  Code,
  Webhook,
  KeyRound,
  GraduationCap,
  ChevronsUpDown,
  UsersRound,
  ListTree,
  GitBranch,
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
import { useAuth } from '../composables/useAuth'
import { usePermissions } from '~/composables/usePermissions'
import { useLayoutState } from '~/composables/useLayoutState'

// Auth composable
const { user, tenant, logout } = useAuth()
const route = useRoute()
const router = useRouter()

// Use shared layout state
const { isCollapsed } = useLayoutState()
const { hasScope } = usePermissions()

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

const isMenuItemActive = (path: string) => {
  if (route.path === path) return true
  if (path !== '/' && route.path.startsWith(path + '/')) return true
  return false
}

const isAgentDetail = computed(() => {
  return route.name?.toString().startsWith('agents-id')
})

const handleBackToAgents = () => {
  router.push('/agents')
}

const menuItems = [
  {
    name: 'Панель управления',
    path: '/dashboard',
    icon: LayoutDashboard
  },
  {
    name: 'Мои агенты',
    path: '/agents',
    icon: Bot
  },
  {
    name: 'Диалоги',
    path: '/dialogs',
    icon: MessageSquare
  },
  {
    name: 'Пациенты',
    path: '/patients',
    icon: UsersRound
  },
  {
    name: 'Аналитика',
    path: '/analytics',
    icon: Activity
  },
  {
    name: 'История',
    path: '/tool-calls-history',
    icon: History
  },
  {
    name: 'Платежи',
    path: '/billing',
    icon: CreditCard
  },
  {
    name: 'Учётные данные',
    path: '/credentials',
    icon: Shield,
    requiresScope: 'agents:write',
  },
  {
    name: 'Настройки',
    path: '/settings',
    icon: Settings,
    requiresScope: 'settings:write',
  }
]

const agentMenuItems = [
  { id: 'prompt', name: 'Системный промпт', icon: Sparkles, path: (id: string) => `/agents/${id}/prompt` },
  { id: 'prompt-training', name: 'Обучение промпта', icon: GraduationCap, path: (id: string) => `/agents/${id}/prompt-training` },
  { id: 'channels', name: 'Каналы', icon: Radio, path: (id: string) => `/agents/${id}/channels` },
  { id: 'connections', name: 'Интеграции', icon: Link, path: (id: string) => `/agents/${id}/connections` },
  { id: 'knowledge', name: 'База знаний', icon: Database, path: (id: string) => `/agents/${id}/knowledge` },
  { id: 'scenarios', name: 'Сценарии', icon: ListTree, path: (id: string) => `/agents/${id}/scenarios` },
  { id: 'script-flows', name: 'Потоки эксперта', icon: GitBranch, path: (id: string) => `/agents/${id}/scripts` },
  { id: 'functions', name: 'Функции', icon: Code, path: (id: string) => `/agents/${id}/functions` },
  { id: 'webhook', name: 'Webhook', icon: Webhook, path: (id: string) => `/agents/${id}/webhook` },
  { id: 'model', name: 'Модель', icon: Cpu, path: (id: string) => `/agents/${id}/model` },
  { id: 'analysis', name: 'Анализ', icon: Activity, path: (id: string) => `/agents/${id}/analysis` },
  { id: 'chat', name: 'Чат', icon: MessageSquare, path: (id: string) => `/agents/${id}/chat` },
  { id: 'api-keys', name: 'API-ключи', icon: KeyRound, path: (id: string) => `/agents/${id}/api-keys`, requiresScope: 'settings:write' },
  {
    id: 'settings',
    name: 'Настройки',
    icon: Settings,
    path: (id: string) => `/agents/${id}/settings`,
    requiresScope: 'agents:write',
  },
]

const currentMenuItems = computed(() => {
  if (isAgentDetail.value) {
    const agentId = route.params.id as string
    return agentMenuItems
      .filter(item => !item.requiresScope || hasScope(item.requiresScope))
      .map(item => ({
        ...item,
        path: item.path(agentId)
      }))
  }
  return menuItems.filter(
    item => !('requiresScope' in item && item.requiresScope) || hasScope(item.requiresScope),
  )
})
</script>
