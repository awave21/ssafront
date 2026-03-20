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
            @click="handleOpenPromptTraining"
            class="inline-flex items-center justify-center gap-2 px-2 lg:px-3 py-1.5 bg-primary/10 text-primary rounded-md text-xs font-medium hover:bg-primary/15 transition-colors shrink-0"
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
        </div>
      </div>

      <div class="px-6 py-2 bg-muted/50 border-b border-border flex justify-between items-center">
        <span class="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">Редактор подсказок</span>
        <div class="flex items-center gap-3">
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

      <div class="border-b border-border bg-background">
        <div class="flex items-center justify-between px-4 py-2.5 border-b border-border/60">
          <div class="flex items-center gap-2">
            <Menubar class="border-0 bg-transparent p-0">
              <MenubarMenu>
                <MenubarTrigger>Теги</MenubarTrigger>
                <MenubarContent class="w-56">
                  <MenubarSub v-for="group in tagGroups" :key="`tag-group-${group.id}`">
                    <MenubarSubTrigger>{{ group.label }}</MenubarSubTrigger>
                    <MenubarSubContent class="w-72 max-h-[320px] overflow-y-auto">
                      <MenubarItem
                        v-for="(tag, tagIndex) in group.tags"
                        :key="`tag-${group.id}-${tagIndex}`"
                        @click="addTagToPrompt(tag)"
                      >
                        <div class="flex flex-col">
                          <span class="text-[11px] font-medium">{{ tag.label }}</span>
                          <span v-if="tag.hint" class="text-[10px] text-muted-foreground line-clamp-2">{{ tag.hint }}</span>
                        </div>
                      </MenubarItem>
                    </MenubarSubContent>
                  </MenubarSub>
                </MenubarContent>
              </MenubarMenu>

              <MenubarMenu>
                <MenubarTrigger>Инструменты</MenubarTrigger>
                <MenubarContent class="w-56">
                  <MenubarSub>
                    <MenubarSubTrigger>Переменные</MenubarSubTrigger>
                    <MenubarSubContent class="w-72 max-h-[320px] overflow-y-auto">
                      <MenubarItem
                        v-for="variable in variableMenuItems"
                        :key="`var-${variable.name}`"
                        @click="insertTextAtCursor(variable.name)"
                      >
                        <div class="flex flex-col">
                          <span class="font-mono text-[11px]">{{ variable.name }}</span>
                          <span class="text-[10px] text-muted-foreground line-clamp-1">{{ variable.description }}</span>
                        </div>
                      </MenubarItem>
                      <MenubarItem v-if="!variableMenuItems.length" disabled>
                        <span class="text-[10px] text-muted-foreground">Нет переменных</span>
                      </MenubarItem>
                    </MenubarSubContent>
                  </MenubarSub>

                  <MenubarSub>
                    <MenubarSubTrigger>База знаний</MenubarSubTrigger>
                    <MenubarSubContent class="w-72 max-h-[320px] overflow-y-auto">
                      <MenubarItem
                        v-for="tool in knowledgeToolMenuItems"
                        :key="`knowledge-${tool.name}`"
                        :disabled="tool.isEnabled === false"
                        @click="tool.isEnabled !== false && addToolToPrompt(tool.name, tool.description)"
                      >
                        <div class="flex flex-col">
                          <span class="font-mono text-[11px]">{{ tool.name }}()</span>
                          <span v-if="tool.isEnabled" class="text-[10px] text-muted-foreground line-clamp-1">{{ tool.description || 'Без описания' }}</span>
                          <span v-else class="text-[9px] font-semibold uppercase text-slate-400">Выкл</span>
                        </div>
                      </MenubarItem>
                      <MenubarItem v-if="!knowledgeToolMenuItems.length" disabled>
                        <span class="text-[10px] text-muted-foreground">Нет инструментов</span>
                      </MenubarItem>
                    </MenubarSubContent>
                  </MenubarSub>

                  <MenubarSub>
                    <MenubarSubTrigger>Функции</MenubarSubTrigger>
                    <MenubarSubContent class="w-72 max-h-[320px] overflow-y-auto">
                      <MenubarItem
                        v-for="tool in functionToolMenuItems"
                        :key="`function-${tool.name}`"
                        :disabled="tool.isEnabled === false"
                        @click="tool.isEnabled !== false && addToolToPrompt(tool.name, tool.description)"
                      >
                        <div class="flex flex-col">
                          <span class="font-mono text-[11px]">{{ tool.name }}()</span>
                          <span v-if="tool.isEnabled" class="text-[10px] text-muted-foreground line-clamp-1">{{ tool.description || 'Без описания' }}</span>
                          <span v-else class="text-[9px] font-semibold uppercase text-slate-400">Выкл</span>
                        </div>
                      </MenubarItem>
                      <MenubarItem v-if="!functionToolMenuItems.length" disabled>
                        <span class="text-[10px] text-muted-foreground">Нет функций</span>
                      </MenubarItem>
                    </MenubarSubContent>
                  </MenubarSub>

                  <MenubarSub>
                    <MenubarSubTrigger>Webhook</MenubarSubTrigger>
                    <MenubarSubContent class="w-72 max-h-[320px] overflow-y-auto">
                      <MenubarItem
                        v-for="tool in webhookToolMenuItems"
                        :key="`webhook-${tool.name}`"
                        :disabled="tool.isEnabled === false"
                        @click="tool.isEnabled !== false && addToolToPrompt(tool.name, tool.description)"
                      >
                        <div class="flex flex-col">
                          <span class="font-mono text-[11px]">{{ tool.name }}()</span>
                          <span v-if="tool.isEnabled" class="text-[10px] text-muted-foreground line-clamp-1">{{ tool.description || 'Без описания' }}</span>
                          <span v-else class="text-[9px] font-semibold uppercase text-slate-400">Выкл</span>
                        </div>
                      </MenubarItem>
                      <MenubarItem v-if="!webhookToolMenuItems.length" disabled>
                        <span class="text-[10px] text-muted-foreground">Нет webhook-инструментов</span>
                      </MenubarItem>
                    </MenubarSubContent>
                  </MenubarSub>
                </MenubarContent>
              </MenubarMenu>
            </Menubar>
          </div>

          <div class="flex items-center gap-2">
            <Popover v-model:open="isQuickInsertOpen">
              <PopoverTrigger as-child>
                <button
                  type="button"
                  class="flex items-center gap-1.5 px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors"
                >
                  Быстрый поиск
                  <span class="text-[9px] font-mono text-muted-foreground/70">Ctrl+K</span>
                </button>
              </PopoverTrigger>
              <PopoverContent align="end" class="w-[360px] p-0">
                <Command>
                  <CommandInput placeholder="Найти тег, переменную, инструмент..." />
                  <CommandList>
                    <CommandEmpty>Ничего не найдено</CommandEmpty>
                    <CommandGroup heading="Теги">
                      <CommandItem
                        v-for="tag in quickTagItems"
                        :key="`quick-tag-${tag.key}`"
                        :value="`${tag.label} ${tag.groupLabel} ${tag.hint || ''}`"
                        @select="handleQuickInsertTag({ label: tag.label, value: tag.value, cursorOffset: tag.cursorOffset })"
                      >
                        <div class="flex w-full items-center justify-between gap-2">
                          <span class="text-xs">{{ tag.label }}</span>
                          <span class="text-[10px] text-muted-foreground">{{ tag.groupLabel }}</span>
                        </div>
                      </CommandItem>
                    </CommandGroup>
                    <CommandGroup heading="Переменные">
                      <CommandItem
                        v-for="variable in variableMenuItems"
                        :key="`quick-variable-${variable.name}`"
                        :value="`${variable.name} ${variable.description}`"
                        @select="handleQuickInsertVariable(variable)"
                      >
                        <div class="flex w-full items-center justify-between gap-2">
                          <span class="font-mono text-xs">{{ variable.name }}</span>
                          <span class="text-[10px] text-muted-foreground line-clamp-1">{{ variable.description }}</span>
                        </div>
                      </CommandItem>
                    </CommandGroup>
                    <CommandGroup heading="Инструменты">
                      <CommandItem
                        v-for="tool in quickInsertEnabledToolItems"
                        :key="`quick-tool-${tool.groupId}-${tool.name}`"
                        :value="`${tool.name} ${tool.description || ''} ${tool.groupLabel}`"
                        @select="handleQuickInsertTool(tool)"
                      >
                        <div class="flex w-full items-center justify-between gap-2">
                          <span class="font-mono text-xs">{{ tool.name }}()</span>
                          <span class="text-[10px] text-muted-foreground">{{ tool.groupLabel }}</span>
                        </div>
                      </CommandItem>
                    </CommandGroup>
                  </CommandList>
                </Command>
              </PopoverContent>
            </Popover>
            <button
              type="button"
              @click="isHistoryOpen = true"
              class="flex items-center gap-1.5 px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors"
            >
              <History class="w-3.5 h-3.5" />
              История
            </button>
            <div class="w-px h-4 bg-border mx-1" />
            <button
              type="button"
              @click="isToolbarCollapsed = !isToolbarCollapsed"
              class="p-1 text-muted-foreground hover:text-foreground transition-colors"
            >
              <ChevronDown class="w-3.5 h-3.5 transition-transform duration-200" :class="{ 'rotate-180': !isToolbarCollapsed }" />
            </button>
          </div>
        </div>

        <div
          class="grid transition-all duration-300 ease-out"
          :class="isToolbarCollapsed ? 'grid-rows-[0fr] opacity-0' : 'grid-rows-[1fr] opacity-100'"
        >
          <div class="overflow-hidden">
            <div class="bg-muted/5 px-4 py-2 text-[10px] text-muted-foreground">
              Используйте выпадающие меню «Теги» и «Инструменты» для вставки в промпт.
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
          class="absolute inset-0 p-4 lg:p-6 text-sm lg:text-[13px] text-foreground leading-relaxed resize-none focus:outline-none focus:ring-0 border-0 bg-transparent font-mono placeholder:text-muted-foreground"
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

    <!-- Right Sidebar for History -->
    <div
      v-if="isHistoryOpen"
      class="w-full lg:w-80 shrink-0 flex flex-col bg-card rounded-md border border-border overflow-hidden order-1 lg:order-2"
    >
      <div class="flex items-center justify-between px-4 py-3 border-b border-border bg-muted/30">
        <h3 class="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">История промптов</h3>
        <button @click="isHistoryOpen = false" class="p-1 text-muted-foreground hover:text-foreground transition-colors">
          <PanelRightClose class="w-4 h-4" />
        </button>
      </div>
      <div class="flex-1 overflow-y-auto custom-scrollbar">
        <SystemPromptHistorySection
          :is-open="true"
          :versions="historyVersions"
          :is-loading="historyLoading"
          :is-loading-more="historyLoadingMore"
          :is-activating="historyActivating"
          :has-more="historyHasMore"
          hide-header
          @preview="handlePreviewVersion"
          @activate="handleActivateVersion"
          @load-more="handleLoadMoreHistory"
        />
      </div>
    </div>
    
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
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import {
  Check,
  ChevronDown,
  History,
  LayoutTemplate,
  Loader2,
  Maximize2,
  Minimize2,
  PanelRightClose,
  RotateCcw,
  Sparkles
} from 'lucide-vue-next'
import { useToast } from '~/composables/useToast'
import { usePermissions } from '~/composables/usePermissions'
import { useAgentEditorStore } from '~/composables/useAgentEditorStore'
import { SystemPromptHistorySection, SystemPromptVersionPreview } from '~/components/prompt'
import type { SystemPromptVersionListItem } from '~/types/systemPromptHistory'
import {
  Menubar,
  MenubarContent,
  MenubarItem,
  MenubarMenu,
  MenubarSub,
  MenubarSubContent,
  MenubarSubTrigger,
  MenubarTrigger
} from '~/components/ui/menubar'
import { Popover, PopoverContent, PopoverTrigger } from '~/components/ui/popover'
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '~/components/ui/command'

const store = useAgentEditorStore()
const { form, agent, isPromptFullscreen, promptSidebarToolGroups, promptHistory } = storeToRefs(store)
const { canEditAgents } = usePermissions()
const { success: toastSuccess, error: toastError } = useToast()

// Toolbar state
const isToolbarCollapsed = ref(false)
const isHistoryOpen = ref(false)
const isQuickInsertOpen = ref(false)

type ToolMenuItem = {
  name: string
  description?: string
  isEnabled?: boolean
  groupId: string
  groupLabel: string
}

const resolveToolFamily = (groupId: string, groupLabel: string): 'knowledge' | 'webhook' | 'tools' | 'sqns' => {
  const raw = `${groupId} ${groupLabel}`.toLowerCase()
  if (raw.includes('knowledge') || raw.includes('база')) return 'knowledge'
  if (raw.includes('webhook') || raw.includes('вебхук')) return 'webhook'
  if (raw.includes('sqns')) return 'sqns'
  return 'tools'
}

const variableMenuItems = computed(() => variables)

const quickTagItems = computed(() =>
  tagGroups.flatMap(group =>
    group.tags.map(tag => ({
      key: `${group.id}-${tag.label}`,
      groupLabel: group.label,
      label: tag.label,
      hint: tag.hint,
      value: tag.value,
      cursorOffset: tag.cursorOffset
    }))
  )
)

const allToolMenuItems = computed<ToolMenuItem[]>(() =>
  promptSidebarToolGroups.value.flatMap(group =>
    group.tools.map(tool => ({
      name: tool.name,
      description: tool.description,
      isEnabled: tool.isEnabled,
      groupId: group.id,
      groupLabel: group.label
    }))
  )
)

const knowledgeToolMenuItems = computed(() =>
  allToolMenuItems.value.filter(tool => resolveToolFamily(tool.groupId, tool.groupLabel) === 'knowledge')
)

const webhookToolMenuItems = computed(() =>
  allToolMenuItems.value.filter(tool => resolveToolFamily(tool.groupId, tool.groupLabel) === 'webhook')
)

const functionToolMenuItems = computed(() =>
  allToolMenuItems.value.filter(tool => {
    const family = resolveToolFamily(tool.groupId, tool.groupLabel)
    return family === 'tools' || family === 'sqns'
  })
)

const quickInsertEnabledToolItems = computed(() => allToolMenuItems.value.filter(tool => tool.isEnabled !== false))

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

const handleOpenPromptTraining = () => {
  const agentId = agent.value?.id
  if (!agentId) return
  navigateTo(`/agents/${agentId}/prompt-training`)
}

// Load tool data for menu categories
watch(agent, (value) => {
  if (!value) return
  store.ensureToolsLoaded()
  store.ensureSqnsStatusLoaded()
  store.ensureDirectoriesLoaded()
}, { immediate: true })

watch(isHistoryOpen, (isOpen) => {
  if (isOpen) store.ensurePromptHistoryLoaded()
}, { immediate: true })

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

const addTagToPrompt = (tag: { label: string, value: string, cursorOffset?: number }) => {
  insertTextAtCursor(tag.value, tag.cursorOffset)
  toastSuccess('Тег добавлен', `${tag.label} вставлен`)
}

const handleQuickInsertTag = (tag: { label: string, value: string, cursorOffset?: number }) => {
  addTagToPrompt(tag)
  isQuickInsertOpen.value = false
}

const handleQuickInsertVariable = (variable: { name: string }) => {
  insertTextAtCursor(variable.name)
  isQuickInsertOpen.value = false
}

const handleQuickInsertTool = (tool: { name: string, description?: string, isEnabled?: boolean }) => {
  if (tool.isEnabled === false) return
  addToolToPrompt(tool.name, tool.description)
  isQuickInsertOpen.value = false
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
  const onQuickSearch = (e: KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault()
      isQuickInsertOpen.value = true
    }
  }
  onMounted(() => {
    window.addEventListener('keydown', onEsc)
    window.addEventListener('keydown', onQuickSearch)
  })
  onUnmounted(() => {
    window.removeEventListener('keydown', onEsc)
    window.removeEventListener('keydown', onQuickSearch)
    isPromptFullscreen.value = false
  })
}

</script>
