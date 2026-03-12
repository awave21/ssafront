<template>
  <div
    class="flex flex-col lg:flex-row gap-4 transition-all duration-300"
    :class="isPromptFullscreen
      ? 'fixed inset-0 z-[100] bg-slate-50 p-4 lg:p-6'
      : 'flex-1 min-h-0'"
  >
    <div class="flex-1 flex flex-col bg-background rounded-md border border-border overflow-hidden min-w-0 min-h-0 order-2 lg:order-1">
      <div class="flex items-center justify-between px-3 lg:px-4 py-3 border-b border-border bg-background gap-2">
        <div class="flex items-center gap-2 overflow-x-auto">
          <button
            type="button"
            disabled
            class="inline-flex items-center justify-center gap-2 px-2 lg:px-3 py-1.5 bg-primary/10 text-primary rounded-md text-xs font-medium opacity-50 cursor-not-allowed shrink-0"
          >
            <Sparkles class="h-3.5 w-3.5" />
            <span class="hidden sm:inline">Улучшить с AI</span>
          </button>
          <button
            type="button"
            disabled
            class="inline-flex items-center justify-center gap-2 px-2 lg:px-3 py-1.5 bg-background border border-border text-muted-foreground rounded-md text-xs font-medium opacity-50 cursor-not-allowed shrink-0"
          >
            <LayoutTemplate class="h-3.5 w-3.5" />
            <span class="hidden sm:inline">Шаблоны</span>
          </button>
        </div>
        <div class="flex items-center gap-1">
          <button
            type="button"
            @click="store.resetPrompt()"
            class="inline-flex items-center justify-center gap-1.5 lg:gap-2 px-2 lg:px-3 py-2 lg:py-1.5 text-muted-foreground hover:text-foreground hover:bg-accent rounded-md text-xs font-medium transition-colors min-h-[44px] lg:min-h-[auto]"
            title="Сбросить"
          >
            <RotateCcw class="h-4 w-4 lg:h-3.5 lg:w-3.5" />
            <span class="hidden sm:inline">Сбросить</span>
          </button>
          <button
            type="button"
            @click="isPromptFullscreen = !isPromptFullscreen"
            class="inline-flex items-center justify-center p-2 lg:p-1.5 text-muted-foreground hover:text-foreground hover:bg-accent rounded-md transition-colors min-h-[44px] lg:min-h-[auto]"
            :title="isPromptFullscreen ? 'Свернуть' : 'Развернуть'"
          >
            <Minimize2 v-if="isPromptFullscreen" class="h-4 w-4 lg:h-3.5 lg:w-3.5" />
            <Maximize2 v-else class="h-4 w-4 lg:h-3.5 lg:w-3.5" />
          </button>
          <button
            type="button"
            @click="isRightSidebarCollapsed = !isRightSidebarCollapsed"
            class="inline-flex items-center justify-center p-2 lg:p-1.5 text-muted-foreground hover:text-foreground hover:bg-accent rounded-md transition-colors min-h-[44px] lg:min-h-[auto]"
            :title="isRightSidebarCollapsed ? 'Показать панель' : 'Скрыть панель'"
          >
            <PanelRightOpen v-if="isRightSidebarCollapsed" class="h-4 w-4 lg:h-3.5 lg:w-3.5" />
            <PanelRightClose v-else class="h-4 w-4 lg:h-3.5 lg:w-3.5" />
          </button>
        </div>
      </div>

      <div class="px-6 py-2 bg-muted/50 border-b border-border flex justify-between items-center">
        <span class="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Редактор подсказок</span>
        <div class="flex items-center gap-3">
          <!-- Auto-save indicator -->
          <span v-if="store.isAutoSaving" class="flex items-center gap-1.5 text-[10px] text-blue-600">
            <Loader2 class="h-3 w-3 animate-spin" />
            Сохранение...
          </span>
          <span v-else-if="hasUnsavedChanges" class="flex items-center gap-1.5 text-[10px] text-amber-600">
            <div class="h-1.5 w-1.5 bg-amber-400 rounded-full animate-pulse" />
            Несохранено
          </span>
          <span v-else-if="store.lastAutoSavedAt" class="flex items-center gap-1.5 text-[10px] text-green-600">
            <Check class="h-3 w-3" />
            Сохранено
          </span>
          <span class="text-[10px] text-muted-foreground font-mono">~{{ estimatedTokens }} токенов</span>
        </div>
      </div>

      <div class="border-b border-border">
        <button
          @click="isTagsPanelOpen = !isTagsPanelOpen"
          class="w-full flex items-center justify-between px-4 py-2 bg-muted/20 hover:bg-muted/30 transition-colors"
        >
          <span class="flex items-center gap-1.5 text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
            <Tag class="w-3 h-3" />
            Быстрые теги
          </span>
          <ChevronDown
            class="w-3.5 h-3.5 text-muted-foreground transition-transform duration-200"
            :class="{ 'rotate-180': isTagsPanelOpen }"
          />
        </button>
        <div
          class="grid transition-all duration-300 ease-in-out"
          :class="isTagsPanelOpen ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'"
        >
          <div :class="isTagsOverflowVisible ? 'overflow-visible' : 'overflow-hidden'">
            <div class="px-4 py-3 bg-muted/10 space-y-2.5">
              <div v-for="(group, groupIndex) in tagGroups" :key="groupIndex" class="flex items-start gap-2">
                <span
                  class="shrink-0 mt-0.5 text-[9px] font-semibold uppercase tracking-wider w-[70px] text-right"
                  :class="{
                    'text-blue-500': (group as any).color === 'blue',
                    'text-violet-500': (group as any).color === 'violet',
                    'text-emerald-500': (group as any).color === 'emerald',
                    'text-muted-foreground': (group as any).color === 'neutral'
                  }"
                >{{ (group as any).label }}</span>
                <div class="flex flex-wrap gap-1">
                  <div
                    v-for="(tag, tagIndex) in (group as any).tags"
                    :key="tagIndex"
                    class="relative group/tag"
                  >
                    <button
                      @click="addTagToPrompt(tag)"
                      class="inline-flex items-center gap-1 px-2 py-0.5 rounded border text-[10px] font-medium transition-colors"
                      :class="{
                        'border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-300 dark:hover:bg-blue-900': (group as any).color === 'blue',
                        'border-violet-200 bg-violet-50 text-violet-700 hover:bg-violet-100 dark:border-violet-800 dark:bg-violet-950 dark:text-violet-300 dark:hover:bg-violet-900': (group as any).color === 'violet',
                        'border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 dark:hover:bg-emerald-900': (group as any).color === 'emerald',
                      'border-border bg-background text-muted-foreground hover:bg-accent hover:text-accent-foreground': (group as any).color === 'neutral'
                    }"
                  >
                    <Hash v-if="(group as any).color === 'blue'" class="w-2.5 h-2.5" />
                    <Code2 v-else-if="(group as any).color === 'violet' || (group as any).color === 'emerald'" class="w-2.5 h-2.5" />
                    <Braces v-else class="w-2.5 h-2.5" />
                    {{ (tag as any).label }}
                  </button>
                    <div
                      v-if="(tag as any).hint"
                      class="absolute top-full left-1/2 -translate-x-1/2 mt-1.5 px-2.5 py-1 bg-white border border-slate-200 text-slate-600 text-[10px] rounded-md shadow-md whitespace-nowrap opacity-0 invisible group-hover/tag:opacity-100 group-hover/tag:visible transition-all duration-150 pointer-events-none z-50"
                    >
                      {{ (tag as any).hint }}
                      <div class="absolute bottom-full left-1/2 -translate-x-1/2 border-4 border-transparent border-b-white drop-shadow-sm"></div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="flex-1 relative bg-background min-h-[calc(100vh-120px)] lg:min-h-0">
        <textarea
          v-model="form.system_prompt"
          :disabled="!canEditAgents"
          @focus="handlePromptFocus"
          @blur="handlePromptBlur"
          class="absolute inset-0 p-4 lg:p-6 text-base lg:text-sm text-foreground leading-relaxed resize-none focus:outline-none focus:ring-0 border-0 bg-transparent font-mono placeholder:text-muted-foreground"
          placeholder="Ты — дружелюбный и профессиональный ассистент клиники..."
          spellcheck="false"
        ></textarea>
      </div>

      <div v-if="isPromptFullscreen && canEditAgents" class="flex flex-col sm:flex-row items-center justify-between gap-2 px-3 lg:px-4 py-2 border-t border-border bg-background">
        <span class="text-xs text-muted-foreground order-2 sm:order-1 text-center sm:text-left">{{ agent?.name }}</span>
        <div class="flex items-center gap-2 order-1 sm:order-2">
          <button
            @click="isPromptFullscreen = false"
            class="px-4 py-2 sm:py-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors min-h-[44px] sm:min-h-[auto]"
          >
            Свернуть
          </button>
          <button
            @click="store.saveAgent()"
            :disabled="store.isSaving"
            class="px-5 py-2 sm:py-1.5 bg-indigo-600 text-white rounded-md text-xs font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors flex items-center gap-1.5 min-h-[44px] sm:min-h-[auto]"
          >
            <Loader2 v-if="store.isSaving" class="h-3 w-3 animate-spin" />
            <Check v-else class="h-3 w-3" />
            Сохранить
          </button>
        </div>
      </div>
    </div>

    <div
      class="transition-all duration-300 ease-out shrink-0 overflow-hidden order-1 lg:order-2"
      :class="isRightSidebarCollapsed
        ? 'w-0 max-h-0 lg:max-h-none opacity-0'
        : 'w-full lg:w-80 opacity-100 max-h-[2000px] lg:max-h-none'"
    >
      <div class="w-full lg:h-full overflow-hidden">
        <div class="w-full bg-card rounded-md border border-border text-card-foreground flex flex-col overflow-hidden lg:h-full">
          <div class="flex-1 overflow-y-auto flex flex-col">
            <div class="border-b border-border">
              <button
                @click="toggleAccordion('variables')"
                class="w-full flex items-center justify-between p-4 bg-muted/30 hover:bg-muted/50 transition-colors"
              >
                <h3 class="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Переменные</h3>
                <ChevronDown
                  class="w-4 h-4 text-muted-foreground transition-transform duration-200"
                  :class="{ 'rotate-180': activeAccordions.includes('variables') }"
                />
              </button>

              <div
                class="grid transition-all duration-300 ease-in-out"
                :class="activeAccordions.includes('variables') ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'"
              >
                <div class="overflow-hidden">
                  <div class="p-4 pt-0 bg-muted/30">
                    <div class="space-y-1">
                      <button
                        v-for="(v, vIndex) in variables"
                        :key="vIndex"
                        @click="insertTextAtCursor((v as any).name)"
                        class="w-full flex items-center justify-between px-2 py-1.5 rounded hover:bg-background group transition-colors text-left"
                      >
                        <code class="text-xs text-primary font-medium bg-primary/10 px-1.5 py-0.5 rounded">{{ (v as any).name }}</code>
                        <span class="text-[10px] text-muted-foreground">{{ (v as any).description }}</span>
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="promptSidebarToolGroups.length" class="border-b border-border">
              <button
                @click="toggleAccordion('functions')"
                class="w-full flex items-center justify-between p-4 bg-muted/30 hover:bg-muted/50 transition-colors"
              >
                <h3 class="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Функции</h3>
                <ChevronDown
                  class="w-4 h-4 text-muted-foreground transition-transform duration-200"
                  :class="{ 'rotate-180': activeAccordions.includes('functions') }"
                />
              </button>

              <div
                class="grid transition-all duration-300 ease-in-out"
                :class="activeAccordions.includes('functions') ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'"
              >
                <div class="overflow-hidden">
                  <div class="p-4 pt-0 bg-muted/30">
                    <TooltipProvider :delay-duration="120">
                      <div class="space-y-3">
                        <div
                          v-for="group in promptSidebarToolGroups"
                          :key="group.id"
                          class="space-y-1.5"
                        >
                          <div class="px-2 pt-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                            {{ group.label }}
                          </div>

                          <template v-for="(tool, toolIndex) in group.tools" :key="`${group.id}-${tool.name}-${toolIndex}`">
                            <Tooltip>
                              <TooltipTrigger as-child>
                                <button
                                  @click="addToolToPrompt((tool as any).name, (tool as any).description)"
                                  class="w-full flex items-center justify-between px-2 py-1.5 rounded hover:bg-background group transition-colors text-left"
                                >
                                  <code class="text-xs text-emerald-600 font-medium bg-emerald-500/10 px-1.5 py-0.5 rounded">{{ (tool as any).name }}()</code>
                                  <span class="text-[10px] text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity">+ вставить</span>
                                </button>
                              </TooltipTrigger>
                              <TooltipContent side="left" :side-offset="8" class="max-w-[260px] text-xs leading-relaxed break-words">
                                {{ getToolTooltipText(tool) }}
                              </TooltipContent>
                            </Tooltip>
                          </template>
                        </div>
                      </div>
                    </TooltipProvider>
                  </div>
                </div>
              </div>
            </div>

            <SystemPromptHistorySection
              :is-open="activeAccordions.includes('history')"
              :versions="historyVersions"
              :is-loading="historyLoading"
              :is-loading-more="historyLoadingMore"
              :is-activating="historyActivating"
              :has-more="historyHasMore"
              @toggle="handleOpenHistory"
              @preview="handlePreviewVersion"
              @activate="handleActivateVersion"
              @load-more="handleLoadMoreHistory"
            />

            <SystemPromptVersionPreview
              v-model:open="showVersionPreview"
              :version="previewVersion"
              :active-prompt="agent?.system_prompt ?? ''"
              :is-loading="isLoadingPreview"
              :is-activating="historyActivating"
              :can-activate="canEditAgents"
              @activate="handleActivateFromPreview"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import {
  Braces,
  Check,
  ChevronDown,
  Code2,
  Hash,
  LayoutTemplate,
  Loader2,
  Maximize2,
  Minimize2,
  PanelRightClose,
  PanelRightOpen,
  RotateCcw,
  Sparkles,
  Tag
} from 'lucide-vue-next'
import { useToast } from '~/composables/useToast'
import { usePermissions } from '~/composables/usePermissions'
import { useAgentEditorStore } from '~/composables/useAgentEditorStore'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '~/components/ui/tooltip'
import { SystemPromptHistorySection, SystemPromptVersionPreview } from '~/components/prompt'
import type { SystemPromptVersionListItem, SystemPromptVersionRead } from '~/types/systemPromptHistory'

const store = useAgentEditorStore()
const { form, agent, isPromptFullscreen, promptSidebarToolGroups, promptHistory } = storeToRefs(store)
const { canEditAgents } = usePermissions()
const { success: toastSuccess, error: toastError } = useToast()

// Auto-save state
const hasUnsavedChanges = computed(() => {
  if (!agent.value) return false
  return form.value.system_prompt !== agent.value.system_prompt
})

// Handle focus/blur for auto-save
const handlePromptFocus = () => {
  store.isPromptFocused = true
}

const handlePromptBlur = () => {
  store.isPromptFocused = false
  
  // Save on blur if there are unsaved changes
  if (hasUnsavedChanges.value && canEditAgents.value) {
    store.autoSavePrompt()
  }
}

const isTagsPanelOpen = ref(true)
const isTagsOverflowVisible = ref(true)

// On mobile: tags panel starts collapsed
if (import.meta.client && window.innerWidth < 1024) {
  isTagsPanelOpen.value = false
  isTagsOverflowVisible.value = false
}

let tagsOverflowTimer: ReturnType<typeof setTimeout> | null = null

watch(isTagsPanelOpen, (open) => {
  if (tagsOverflowTimer) clearTimeout(tagsOverflowTimer)
  if (open) {
    // Delay overflow-visible until after animation (300ms)
    tagsOverflowTimer = setTimeout(() => {
      isTagsOverflowVisible.value = true
    }, 320)
  } else {
    // Switch to overflow-hidden immediately when closing
    isTagsOverflowVisible.value = false
  }
})

// Right sidebar state with responsive behavior
const isRightSidebarCollapsed = ref(false) // Default: expanded on desktop
const isMobileInit = import.meta.client && window.innerWidth < 1024
const activeAccordions = ref(isMobileInit ? [] as string[] : ['history'])

// Handle responsive sidebar - smart defaults for mobile/desktop
const handleResize = () => {
  if (typeof window !== 'undefined') {
    const isMobile = window.innerWidth < 1024
    // On mobile: keep sidebar accessible but don't force collapse
    // Users can still toggle it manually if needed
  }
}

// Initialize responsive state
const initResponsiveState = () => {
  if (typeof window !== 'undefined') {
    const isMobile = window.innerWidth < 1024
    // On mobile: start with sidebar collapsed to show prompt editor
    // On desktop: start with sidebar expanded
    isRightSidebarCollapsed.value = isMobile
  }
}
const showVersionPreview = ref(false)
const previewVersion = ref(null)
const isLoadingPreview = ref(false)

const historyVersions = computed(() => promptHistory.value?.versions ?? [])
const historyLoading = computed(() => promptHistory.value?.isLoading ?? false)
const historyLoadingMore = computed(() => promptHistory.value?.isLoadingMore ?? false)
const historyActivating = computed(() => promptHistory.value?.isActivating ?? false)
const historyHasMore = computed(() => {
  const nextCursor = promptHistory.value?.nextCursor
  return nextCursor !== null && nextCursor !== undefined
})

type TagGroup = {
  id: string
  label: string
  color: 'blue' | 'violet' | 'emerald' | 'neutral'
  tags: Array<{
    label: string
    value: string
    hint?: string
    cursorOffset?: number
  }>
}

const tagGroups: TagGroup[] = [
  {
    id: 'markdown',
    label: 'Markdown',
    color: 'blue',
    tags: [
      { label: '# Заголовок', value: '# ', hint: 'Заголовок первого уровня' },
      { label: '## Подзаголовок', value: '## ', hint: 'Заголовок второго уровня' }
    ]
  },
  {
    id: 'structure',
    label: 'Структура',
    color: 'violet',
    tags: [
      { label: 'goal', value: '<goal>\n\n</goal>', cursorOffset: 7, hint: 'Цель и задача агента' },
      { label: 'role', value: '<role>\n\n</role>', cursorOffset: 7, hint: 'Роль и персона агента' },
      { label: 'context', value: '<context>\n\n</context>', cursorOffset: 10, hint: 'Контекст и знания' },
      { label: 'instructions', value: '<instructions>\n\n</instructions>', cursorOffset: 15, hint: 'Инструкции поведения' },
      { label: 'examples', value: '<examples>\n\n</examples>', cursorOffset: 11, hint: 'Примеры диалогов' },
      { label: 'format', value: '<output_format>\n\n</output_format>', cursorOffset: 16, hint: 'Формат ответов' }
    ]
  },
  {
    id: 'behavior',
    label: 'Поведение',
    color: 'emerald',
    tags: [
      { label: 'style', value: '<style>\n\n</style>', cursorOffset: 8, hint: 'Стиль общения' },
      { label: 'constraints', value: '<constraints>\n\n</constraints>', cursorOffset: 14, hint: 'Ограничения и запреты' },
      { label: 'flow', value: '<flow>\n\n</flow>', cursorOffset: 7, hint: 'Сценарий диалога' },
      { label: 'fallback', value: '<fallback>\n\n</fallback>', cursorOffset: 11, hint: 'Действия при ошибках' },
      { label: 'tools', value: '<tools>\n\n</tools>', cursorOffset: 8, hint: 'Описание инструментов' }
    ]
  },
  {
    id: 'custom',
    label: 'Свой',
    color: 'neutral',
    tags: [
      { label: 'Свой тег', value: '<>\n\n</>', cursorOffset: 1, hint: 'Пустой тег — впишите своё название' }
    ]
  }
]

type Variable = {
  name: string
  description: string
}

const variables: Variable[] = [
  { name: '{client_name}', description: 'Имя клиента' },
  { name: '{clinic_phone}', description: 'Телефон клиники' },
  { name: '{service_list}', description: 'Список услуг' },
  { name: '{current_date}', description: 'Текущая дата' }
]

const estimatedTokens = computed(() => {
  const text = form.value.system_prompt || ''
  if (!text) return 0
  const cyrillicChars = (text.match(/[\u0400-\u04FF]/g) || []).length
  const otherChars = text.length - cyrillicChars
  return Math.ceil(cyrillicChars / 1.5 + otherChars / 4)
})

const insertTextAtCursor = (textToInsert: string, cursorOffset?: number) => {
  const textarea = document.querySelector('textarea[placeholder="Ты — дружелюбный и профессиональный ассистент клиники..."]') as HTMLTextAreaElement

  if (textarea) {
    const start = textarea.selectionStart
    const end = textarea.selectionEnd
    const scrollTop = textarea.scrollTop
    const currentText = form.value.system_prompt

    form.value.system_prompt = currentText.substring(0, start) + textToInsert + currentText.substring(end)

    nextTick(() => {
      textarea.focus({ preventScroll: true })
      textarea.scrollTop = scrollTop
      const newCursorPos = start + (cursorOffset !== undefined ? cursorOffset : textToInsert.length)
      textarea.setSelectionRange(newCursorPos, newCursorPos)
    })
  } else {
    form.value.system_prompt += (form.value.system_prompt ? '\n' : '') + textToInsert
  }
}

const addToolToPrompt = (name: string, description?: string) => {
  insertTextAtCursor(`${name}()`)
  toastSuccess('Инструмент добавлен', `Инструмент ${name}() вставлен`)
}

const getToolTooltipText = (tool: { description?: string }) => {
  const description = String(tool?.description || '').trim()
  if (description) return description
  return 'Описание инструмента не заполнено'
}

const addTagToPrompt = (tag: { label: string, value: string, cursorOffset?: number }) => {
  insertTextAtCursor(tag.value, tag.cursorOffset)
  toastSuccess('Тег добавлен', `${tag.label} вставлен`)
}

const toggleAccordion = (id: string) => {
  const index = activeAccordions.value.indexOf(id)
  if (index === -1) activeAccordions.value.push(id)
  else activeAccordions.value.splice(index, 1)

  if (id === 'functions') {
    store.ensureToolsLoaded()
    store.ensureSqnsStatusLoaded()
    store.ensureDirectoriesLoaded()
  }
}

const handleOpenHistory = () => {
  toggleAccordion('history')
  if (activeAccordions.value.includes('history')) {
    store.ensurePromptHistoryLoaded()
  }
}

const handleLoadMoreHistory = () => {
  promptHistory.value?.fetchMore()
}

const handlePreviewVersion = (item: SystemPromptVersionListItem) => {
  if (!promptHistory.value) return
  showVersionPreview.value = true
  isLoadingPreview.value = true
  previewVersion.value = null
  
  promptHistory.value.fetchVersionDetail(item.id).then(detail => {
    previewVersion.value = detail
  }).catch((err: any) => {
    toastError('Версия не найдена', err.message || '')
    showVersionPreview.value = false
  }).finally(() => {
    isLoadingPreview.value = false
  })
}

const handleActivateVersion = (item: SystemPromptVersionListItem) => {
  if (!promptHistory.value) return
  if (!confirm(`Текущий промпт будет заменён на версию #${item.version_number}. Продолжить?`)) return
  
  promptHistory.value.activateVersion(item.id).then(activated => {
    if (activated) {
      form.value.system_prompt = activated.system_prompt
      if (agent.value) agent.value.system_prompt = activated.system_prompt
      toastSuccess('Версия восстановлена', `Активирована версия #${activated.version_number}`)
    }
  }).catch((err: any) => {
    toastError('Не удалось активировать', err.message || '')
  })
}

const handleActivateFromPreview = () => {
  if (!promptHistory.value || !previewVersion.value) return
  if (!confirm(`Текущий промпт будет заменён на версию #${previewVersion.value.version_number}. Продолжить?`)) return
  
  promptHistory.value.activateVersion(previewVersion.value.id).then(activated => {
    if (activated) {
      form.value.system_prompt = activated.system_prompt
      if (agent.value) agent.value.system_prompt = activated.system_prompt
      previewVersion.value = { ...previewVersion.value, is_active: true }
      toastSuccess('Версия восстановлена', `Активирована версия #${activated.version_number}`)
    }
  }).catch((err: any) => {
    toastError('Не удалось активировать', err.message || '')
  })
}

if (typeof window !== 'undefined') {
  const onEsc = (e: KeyboardEvent) => {
    if (e.key === 'Escape' && isPromptFullscreen.value) {
      isPromptFullscreen.value = false
    }
  }
  onMounted(() => {
    window.addEventListener('keydown', onEsc)
    window.addEventListener('resize', handleResize)
    initResponsiveState()
  })
  onUnmounted(() => {
    window.removeEventListener('keydown', onEsc)
    window.removeEventListener('resize', handleResize)
    isPromptFullscreen.value = false
  })
}

watch(agent, (value) => {
  if (!value) return
  store.ensureToolsLoaded()
  store.ensureSqnsStatusLoaded()
  store.ensureDirectoriesLoaded()
  if (activeAccordions.value.includes('history')) {
    store.ensurePromptHistoryLoaded()
  }
}, { immediate: true })
</script>
