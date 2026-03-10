<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { Menu, Check, Play, Trash2, Copy } from 'lucide-vue-next'
import { navigateTo } from '#app'
import DashboardSidebar from '~/components/DashboardSidebar.vue'
import DashboardTopBar from '~/components/DashboardTopBar.vue'
import Switch from '~/components/ui/switch/Switch.vue'
import { useLayoutState } from '~/composables/useLayoutState'

const {
  initSidebarState,
  isCollapsed,
  toggleSidebar,
  breadcrumbTitle,
  breadcrumbAgentName,
  breadcrumbBackPath,
  functionsRunAction,
  functionsDeleteAction,
  functionsDuplicateAction,
  functionsToggleStatusAction,
  functionsSaveAction,
  functionsSelectedFunction,
  functionsTesting,
  functionsCanSave,
  functionsCreateAction
} = useLayoutState()
const isPromptFullscreen = useState<boolean>('prompt-fullscreen', () => false)
const isMobileSidebarOpen = ref(false)
const functionsCreateLabel = computed(() =>
  breadcrumbTitle.value === 'Webhook' ? 'Создать webhook' : 'Создать функцию',
)
const handleBreadcrumbBack = () => {
  if (!breadcrumbBackPath.value) return
  navigateTo(breadcrumbBackPath.value)
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
            <button
              v-if="breadcrumbBackPath"
              @click="handleBreadcrumbBack"
              class="text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              ←
            </button>
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
          <template
            v-if="functionsRunAction || functionsSaveAction || functionsDeleteAction || functionsDuplicateAction || functionsToggleStatusAction || functionsCreateAction"
          >
            <button
              v-if="functionsCreateAction"
              @click="functionsCreateAction"
              class="px-4 py-1.5 bg-indigo-600 text-white rounded-md text-sm font-medium hover:bg-indigo-700 transition-colors"
            >
              {{ functionsCreateLabel }}
            </button>
            <button
              v-if="functionsRunAction"
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
        </template>
      </DashboardTopBar>

      <!-- Прокручиваемый контент -->
      <main class="flex-1 overflow-y-auto bg-muted">
        <slot />
      </main>
    </div>
  </div>
</template>
