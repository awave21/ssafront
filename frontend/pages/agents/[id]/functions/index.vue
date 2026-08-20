<template>
  <AgentPageShell title="Функции" :hide-actions="true">
    <AgentFunctionsWorkspace>
      <div class="flex flex-col gap-5">
    <!-- Заголовок раздела -->
    <div class="flex items-center justify-between gap-3 border-b border-slate-100 pb-4">
      <div class="flex items-center gap-2.5">
        <div class="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <Zap class="h-4 w-4" />
        </div>
        <h1 class="text-lg font-semibold text-slate-900">Функции</h1>
      </div>
      <button
        type="button"
        class="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:border-primary/40 hover:text-primary transition-colors"
        @click="helpOpen = !helpOpen"
      >
        <BookOpen class="h-3.5 w-3.5" />
        Помощь по разделу
      </button>
    </div>

    <!-- Описание раздела -->
    <p class="text-sm leading-relaxed text-slate-600">
      Функции делают ассистента полезнее в реальных бизнес-задачах — они позволяют выполнять задачи вроде форматирования текста, расчётов, поиска, генерации списков, заполнения данных, автоматизации и вызова нужных операций по сценарию.
    </p>

    <!-- Помощь по разделу (раскрывающаяся) -->
    <div
      v-if="helpOpen"
      class="rounded-2xl border border-slate-100 bg-slate-50/60 p-5 text-sm leading-relaxed text-slate-700"
    >
      <p class="mb-2 font-medium text-slate-900">Как работают функции</p>
      <p>
        Каждая функция запускается при выполнении заданного условия: ключевое слово, фраза клиента,
        совпадение с примером или после ответа модели. При срабатывании выполняются действия — от
        передачи диалога менеджеру до отправки данных во внешний сервис.
      </p>
    </div>

    <!-- Две большие CTA-карточки -->
    <div v-if="canEditAgents" class="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <button
        type="button"
        class="group flex items-center gap-4 rounded-2xl border-2 border-dashed border-primary/40 bg-primary/[0.04] p-5 text-left transition-all duration-300 hover:-translate-y-0.5 hover:border-primary/70 hover:bg-primary/[0.08]"
        @click="openTemplatesDialog"
      >
        <div class="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-white text-primary shadow-[0_2px_8px_-2px_rgba(59,130,246,0.15)] group-hover:scale-105 transition-transform">
          <LayoutGrid class="h-5 w-5" />
        </div>
        <div class="min-w-0">
          <div class="text-sm font-semibold text-primary">+ Добавить готовую</div>
          <div class="mt-1 text-xs leading-relaxed text-slate-600">
            Выберите готовую функцию из каталога — популярные кейсы, минимум настроек
          </div>
        </div>
      </button>

      <button
        type="button"
        class="group flex items-center gap-4 rounded-2xl border-2 border-dashed border-slate-200 bg-white p-5 text-left transition-all duration-300 hover:-translate-y-0.5 hover:border-primary/40 hover:bg-slate-50"
        @click="navigateToCreate"
      >
        <div class="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-500 group-hover:bg-primary/10 group-hover:text-primary transition-colors">
          <Plus class="h-5 w-5" />
        </div>
        <div class="min-w-0">
          <div class="text-sm font-semibold text-slate-900 group-hover:text-primary transition-colors">+ Создать свою</div>
          <div class="mt-1 text-xs leading-relaxed text-slate-600">
            Добавьте свою функцию, самостоятельно настроив под ваши задачи
          </div>
        </div>
      </button>
    </div>

    <!-- Список функций / пустое состояние / загрузка -->
    <div v-if="loading" class="flex items-center justify-center py-10">
      <Loader2 class="h-6 w-6 animate-spin text-slate-400" />
    </div>

    <p v-else-if="sortedRules.length === 0" class="text-center text-sm text-slate-500">
      Функций пока нет. Нажмите «+ Добавить готовую» или «+ Создать свою».
    </p>

    <div v-else class="flex flex-col gap-3">
      <div
        v-for="rule in sortedRules"
        :key="rule.id"
        class="group relative flex cursor-pointer items-center gap-4 overflow-hidden rounded-3xl border border-slate-100 bg-white p-4 pr-5 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-all duration-500 hover:-translate-y-0.5 hover:shadow-[0_20px_40px_-12px_rgba(0,0,0,0.08)]"
        @click="navigateToEdit(rule.id)"
      >
        <!-- Декоративный круг -->
        <div class="pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full bg-primary/5 transition-transform duration-700 group-hover:scale-150" />

        <!-- Иконка функции -->
        <div class="relative z-10 flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary transition-transform duration-300 group-hover:scale-105">
          <Zap class="h-4 w-4" />
        </div>

        <!-- Название + описание условия -->
        <div class="relative z-10 min-w-0 flex-1">
          <div class="flex flex-wrap items-center gap-2">
            <span class="truncate text-sm font-semibold text-slate-900">
              {{ rule.name || 'Без названия' }}
            </span>
            <span
              class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium"
              :class="rule.enabled ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'"
            >
              <span
                class="h-1.5 w-1.5 rounded-full"
                :class="rule.enabled ? 'bg-emerald-500' : 'bg-slate-400'"
              />
              {{ rule.enabled ? 'Включена' : 'Выключена' }}
            </span>
          </div>
          <div class="mt-1 truncate text-xs text-slate-500">
            {{ getConditionDescription(rule) }}
          </div>
        </div>

        <!-- Пилл приоритета -->
        <div class="relative z-10 hidden shrink-0 rounded-2xl bg-sky-50/60 px-3 py-2 text-center sm:block">
          <div class="text-[9px] font-black uppercase tracking-wider text-sky-700/80">Приоритет</div>
          <div class="mt-0.5 text-sm font-bold text-slate-900">{{ rule.priority }}</div>
        </div>

        <!-- Действия -->
        <div class="relative z-10 flex shrink-0 items-center gap-1" @click.stop>
          <Switch
            v-if="canEditAgents"
            :model-value="rule.enabled"
            @update:model-value="toggleRuleStatus(rule.id, $event)"
          />
          <button
            v-if="canEditAgents"
            type="button"
            class="flex h-8 w-8 items-center justify-center rounded-xl text-slate-400 transition-colors hover:bg-primary/10 hover:text-primary"
            title="Редактировать"
            @click="navigateToEdit(rule.id)"
          >
            <Pencil class="h-4 w-4" />
          </button>
          <button
            v-if="canEditAgents"
            type="button"
            class="flex h-8 w-8 items-center justify-center rounded-xl text-slate-400 transition-colors hover:bg-red-50 hover:text-red-600"
            title="Удалить"
            @click="deleteRule(rule.id)"
          >
            <Trash2 class="h-4 w-4" />
          </button>
        </div>
      </div>
      </div>
      </div>
    </AgentFunctionsWorkspace>
  </AgentPageShell>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Loader2, Pencil, Trash2, Zap, BookOpen, LayoutGrid } from 'lucide-vue-next'
import { Switch } from '~/components/ui/switch'
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import AgentFunctionsWorkspace from '~/components/agents/functions-workspace/AgentFunctionsWorkspace.vue'
import { useFunctionRules } from '~/composables/useFunctionRules'
import { usePermissions } from '~/composables/usePermissions'
import { useAgentEditorStore } from '~/composables/useAgentEditorStore'
import { useLayoutState } from '~/composables/useLayoutState'
import { getReadableErrorMessage } from '~/utils/api-errors'
import type { FunctionRule } from '~/types/functionRule'

const route = useRoute()
const router = useRouter()
let isCreateNavigating = false
const createActionOwner = 'functions-list-page'
const store = useAgentEditorStore()
const {
  breadcrumbTitle,
  breadcrumbAgentName,
  hideTopBarActions,
  setFunctionsCreateAction,
  clearFunctionsCreateAction,
  resetFunctionsTopbarState,
} = useLayoutState()
const { canEditAgents } = usePermissions()

const agentId = computed(() => (route.params.id as string) || '')
const {
  rules,
  sortedRules,
  loading,
  fetchRules,
  removeRule,
  toggleRule,
} = useFunctionRules(agentId.value)

const helpOpen = ref(false)

breadcrumbTitle.value = 'Функции'
const agentName = computed(() => store.agent?.name || '')
breadcrumbAgentName.value = agentName.value

const applyListTopbarActions = () => {
  hideTopBarActions.value = true
  setFunctionsCreateAction(createActionOwner, async () => {
    await navigateToCreate()
  })
}

const getConditionDescription = (rule: FunctionRule) => {
  const cfg = rule.condition_config as Record<string, any> | undefined
  const desc = cfg?.function_description
  if (desc) return desc
  const ct = rule.condition_type as string
  if (ct === 'keywords' || ct === 'keyword') {
    const kw = Array.isArray(cfg?.keywords) ? cfg.keywords : []
    return kw.length ? kw.slice(0, 3).join(', ') + (kw.length > 3 ? '...' : '') : '—'
  }
  if (rule.condition_type === 'regex') return cfg?.pattern || '—'
  if (rule.condition_type === 'semantic') return cfg?.intent || '—'
  return '—'
}

const navigateToCreate = async () => {
  const target = `/agents/${agentId.value}/functions/new`
  if (!agentId.value || route.path === target || isCreateNavigating) return
  isCreateNavigating = true
  try {
    await router.push(target)
  } finally {
    isCreateNavigating = false
  }
}

const openTemplatesDialog = () => {
  router.push(`/agents/${agentId.value}/functions/catalog`)
}

const navigateToEdit = (ruleId: string) => {
  router.push(`/agents/${agentId.value}/functions/${ruleId}`)
}

const toggleRuleStatus = async (ruleId: string, enabled: boolean) => {
  const rule = rules.value.find((r) => r.id === ruleId)
  if (!rule) return
  try {
    await toggleRule(rule, enabled)
  } catch (err: any) {
    alert(getReadableErrorMessage(err, 'Не удалось изменить статус'))
  }
}

const deleteRule = async (ruleId: string) => {
  if (!confirm('Удалить функцию?')) return
  try {
    await removeRule(ruleId)
  } catch (err: any) {
    alert(getReadableErrorMessage(err, 'Не удалось удалить функцию'))
  }
}

onMounted(async () => {
  resetFunctionsTopbarState()
  applyListTopbarActions()

  await store.ensureAgentLoaded(agentId.value)
  breadcrumbAgentName.value = store.agent?.name || ''
  await fetchRules()
})

onUnmounted(() => {
  hideTopBarActions.value = false
  clearFunctionsCreateAction(createActionOwner)
})

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth',
})
</script>
