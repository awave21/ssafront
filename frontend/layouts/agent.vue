<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { Menu, Check, Play, Trash2, Copy, ChevronRight } from 'lucide-vue-next'
import { navigateTo } from '#app'
import DashboardSidebar from '~/components/DashboardSidebar.vue'
import DashboardTopBar from '~/components/DashboardTopBar.vue'
import ScriptFlowHeaderToolbar from '~/components/agents/scripts/ScriptFlowHeaderToolbar.vue'
import Switch from '~/components/ui/switch/Switch.vue'
import { useLayoutState, type LayoutBreadcrumbSegment } from '~/composables/useLayoutState'

const {
  initSidebarState,
    isCollapsed,
    toggleSidebar,
    breadcrumbTitle,
    breadcrumbAgentName,
    breadcrumbBackPath,
    layoutBreadcrumbSegments,
    pendingBreadcrumbAction,
    isEditorFullscreen,
    functionsRunAction,
  functionsDeleteAction,
  functionsDuplicateAction,
  functionsToggleStatusAction,
  functionsSaveAction,
  functionsSelectedFunction,
  functionsTesting,
  functionsCanSave,
  functionsCreateAction,
  scriptFlowActionsVisible,
  scriptFlowSandboxOpen,
  scriptFlowCoverageOpen,
  scriptFlowToolbarPayload,
    knowledgeGraphRebuildAction,
    knowledgeGraphRefreshAction,
    knowledgeGraphRebuildBusy,
    knowledgeGraphRefreshBusy,
    knowledgeGraphRebuildLabel,
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

const handleBreadcrumbSegmentClick = (seg: LayoutBreadcrumbSegment) => {
  if (!seg.action) return
  if (seg.action.type === 'route') {
    navigateTo(seg.action.path)
    return
  }
  pendingBreadcrumbAction.value = seg.action
}

const onScriptFlowPublishSwitch = (next: boolean) => {
  const p = scriptFlowToolbarPayload.value
  if (!p?.flow) return
  if (next && p.flow.flow_status !== 'published')
    p.onPublish()
  else if (!next && p.flow.flow_status === 'published')
    p.onUnpublish()
}

onMounted(() => {
  initSidebarState()
})
</script>

<template>
  <div class="h-screen flex overflow-hidden bg-muted">
    <!-- Sidebar управляется состоянием сворачивания -->
    <DashboardSidebar
      v-if="!isPromptFullscreen && !isEditorFullscreen"
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
      <DashboardTopBar v-if="!isPromptFullscreen && !isEditorFullscreen">
        <template #left>
          <div class="flex min-w-0 flex-1 items-center gap-2 overflow-hidden sm:gap-3">
            <nav
              v-if="layoutBreadcrumbSegments?.length"
              class="flex min-w-0 shrink items-center gap-1 text-sm"
              aria-label="Навигация"
            >
              <template v-for="(seg, i) in layoutBreadcrumbSegments" :key="i">
                <ChevronRight v-if="i > 0" class="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                <button
                  v-if="seg.action"
                  type="button"
                  class="max-w-[9rem] shrink-0 truncate text-muted-foreground transition-colors hover:text-foreground sm:max-w-[14rem]"
                  @click="handleBreadcrumbSegmentClick(seg)"
                >
                  {{ seg.label }}
                </button>
                <span v-else class="min-w-0 truncate font-medium text-foreground">{{ seg.label }}</span>
              </template>
            </nav>
            <!-- Хлебные крошки агента (простой режим) -->
            <template v-else-if="breadcrumbTitle">
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
            <ScriptFlowHeaderToolbar
              v-if="scriptFlowToolbarPayload"
              class="min-w-0 flex-1"
              v-bind="scriptFlowToolbarPayload"
            />
          </div>
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

          <template v-if="knowledgeGraphRebuildAction || knowledgeGraphRefreshAction">
            <button
              v-if="knowledgeGraphRebuildAction"
              type="button"
              class="px-3 py-1.5 bg-indigo-600 text-white rounded-md text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors"
              :disabled="knowledgeGraphRebuildBusy"
              @click="knowledgeGraphRebuildAction"
            >
              {{ knowledgeGraphRebuildLabel }}
            </button>
            <button
              v-if="knowledgeGraphRefreshAction"
              type="button"
              class="px-3 py-1.5 border border-border bg-background rounded-md text-sm font-medium hover:bg-muted/60 disabled:opacity-50 transition-colors"
              :disabled="knowledgeGraphRefreshBusy"
              @click="knowledgeGraphRefreshAction"
            >
              {{ knowledgeGraphRefreshBusy ? 'Загрузка…' : 'Обновить отображение' }}
            </button>
          </template>

          <!-- Публикация потока — крайний правый элемент шапки -->
          <div
            v-if="scriptFlowToolbarPayload"
            class="flex shrink-0 items-center lg:ml-2"
          >
            <Switch
              :model-value="scriptFlowToolbarPayload.flow.flow_status === 'published'"
              :disabled="scriptFlowToolbarPayload.publishing"
              class-name="scale-90"
              :title="scriptFlowToolbarPayload.flow.flow_status === 'published' ? 'Снять с публикации (вернуть в черновик)' : 'Опубликовать поток'"
              @update:model-value="onScriptFlowPublishSwitch"
            />
          </div>
        </template>
      </DashboardTopBar>

      <!-- Прокручиваемый контент -->
      <main class="flex flex-1 min-h-0 flex-col overflow-y-auto bg-muted">
        <slot />
      </main>
    </div>
  </div>
</template>
