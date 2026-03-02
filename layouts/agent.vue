<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { Menu, Check, Loader2, Play, Trash2, Copy } from 'lucide-vue-next'
import { navigateTo } from '#app'
import DashboardSidebar from '~/components/DashboardSidebar.vue'
import DashboardTopBar from '~/components/DashboardTopBar.vue'
import Switch from '~/components/ui/switch/Switch.vue'
import { useAgentEditorStore } from '~/composables/useAgentEditorStore'
import { usePermissions } from '~/composables/usePermissions'
import { useLayoutState } from '~/composables/useLayoutState'

const {
  initSidebarState,
  isCollapsed,
  toggleSidebar,
  breadcrumbTitle,
  breadcrumbAgentName,
  hideTopBarActions,
  functionsRunAction,
  functionsDeleteAction,
  functionsDuplicateAction,
  functionsToggleStatusAction,
  functionsSaveAction,
  functionsSelectedFunction,
  functionsTesting,
  functionsCanSave
} = useLayoutState()
const store = useAgentEditorStore()
const { isPromptFullscreen, isSaving } = storeToRefs(store)
const { canEditAgents } = usePermissions()
const isMobileSidebarOpen = ref(false)

const handleSave = async () => {
  await store.saveAgent()
}

const handleCancel = () => {
  navigateTo('/agents')
}

onMounted(() => {
  initSidebarState()
})
</script>

<template>
  <div class="h-screen flex overflow-hidden bg-muted">
    <!-- Sidebar управляется состоянием сворачивания -->
    <DashboardSidebar
      v-if="!isPromptFullscreen"
      :class="isCollapsed ? 'hidden lg:flex lg:w-16' : 'hidden lg:flex lg:w-64'"
    />
    
    <!-- Mobile Sidebar Overlay -->
    <Teleport to="body">
      <Transition
        enter-active-class="transition-opacity duration-300"
        enter-from-class="opacity-0"
        enter-to-class="opacity-100"
        leave-active-class="transition-opacity duration-200"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
      >
        <div
          v-if="isMobileSidebarOpen"
          class="lg:hidden fixed inset-0 z-40 bg-black/50"
          @click="isMobileSidebarOpen = false"
        />
      </Transition>

      <Transition
        enter-active-class="transition-transform duration-300 ease-out"
        enter-from-class="-translate-x-full"
        enter-to-class="translate-x-0"
        leave-active-class="transition-transform duration-200 ease-in"
        leave-from-class="translate-x-0"
        leave-to-class="-translate-x-full"
      >
        <DashboardSidebar
          v-if="isMobileSidebarOpen"
          class="lg:hidden fixed inset-y-0 left-0 z-50"
          @close="isMobileSidebarOpen = false"
        />
      </Transition>
    </Teleport>

    <!-- Основная область -->
    <div class="flex-1 flex flex-col min-w-0 overflow-hidden">
      <!-- TopBar скрывается в fullscreen режиме -->
      <DashboardTopBar v-if="!isPromptFullscreen">
        <template #left>
          <!-- Хлебные крошки агента -->
          <template v-if="breadcrumbTitle">
            <span class="text-sm text-muted-foreground font-normal">{{ breadcrumbTitle }}</span>
            <span v-if="breadcrumbAgentName" class="text-sm text-border">/</span>
            <span v-if="breadcrumbAgentName" class="text-sm text-foreground font-medium">{{ breadcrumbAgentName }}</span>
          </template>
        </template>
        <template #right>
          <!-- Кнопка мобильного меню (только на планшете/мобиле) -->
          <button
            class="lg:hidden p-2 rounded-lg text-foreground hover:bg-muted"
            @click="isMobileSidebarOpen = true"
          >
            <Menu class="w-5 h-5" />
          </button>
          <!-- Functions page: show Run, Save, Delete, Status toggle -->
          <template v-if="functionsRunAction">
            <button
              @click="functionsRunAction"
              :disabled="functionsTesting || !functionsSelectedFunction"
              class="px-4 py-1.5 bg-indigo-600 text-white rounded-md text-sm font-medium hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5"
            >
              <Play class="h-3.5 w-3.5" />
              {{ functionsTesting ? 'Выполняется...' : 'Запустить' }}
            </button>
            <button
              v-if="functionsSaveAction"
              @click="functionsSaveAction"
              :disabled="!functionsCanSave"
              class="p-1.5 rounded-md transition-colors"
              :class="functionsCanSave ? 'text-indigo-600 hover:text-indigo-700 hover:bg-indigo-50' : 'text-slate-300 cursor-not-allowed'"
              title="Сохранить"
            >
              <Check class="h-4 w-4" />
            </button>
            <button
              v-if="functionsDuplicateAction && functionsSelectedFunction"
              @click="functionsDuplicateAction"
              class="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-md transition-colors"
              title="Дублировать функцию"
            >
              <Copy class="h-4 w-4" />
            </button>
            <button
              v-if="functionsDeleteAction && functionsSelectedFunction"
              @click="functionsDeleteAction"
              class="p-1.5 text-red-400 hover:text-red-600 hover:bg-red-50 rounded-md transition-colors"
              title="Удалить функцию"
            >
              <Trash2 class="h-4 w-4" />
            </button>
            <div v-if="functionsToggleStatusAction && functionsSelectedFunction" class="flex items-center gap-2 ml-2">
              <span class="text-xs font-medium text-muted-foreground">
                {{ functionsSelectedFunction.status === 'active' ? 'Активна' : 'Неактивна' }}
              </span>
              <Switch 
                :model-value="functionsSelectedFunction.status === 'active'" 
                @update:model-value="functionsToggleStatusAction" 
              />
            </div>
          </template>
          <!-- Other pages: show Save/Cancel (hidden for auto-saving pages) -->
          <template v-else-if="canEditAgents && breadcrumbTitle && !functionsRunAction && !hideTopBarActions">
            <button
              @click="handleCancel"
              class="px-4 py-1.5 text-sm text-muted-foreground font-medium hover:text-foreground transition-colors"
            >
              Отменить
            </button>
            <button
              @click="handleSave"
              :disabled="isSaving"
              class="px-4 py-1.5 bg-primary text-primary-foreground rounded-md text-sm font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5"
            >
              <Loader2 v-if="isSaving" class="h-3.5 w-3.5 animate-spin" />
              <Check v-else class="h-3.5 w-3.5" />
              Сохранить
            </button>
          </template>
        </template>
      </DashboardTopBar>

      <!-- Прокручиваемый контент -->
      <main class="flex-1 overflow-y-auto bg-muted">
        <slot />
      </main>
    </div>
  </div>
</template>
