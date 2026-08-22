<template>
  <div class="w-full">
    <!-- Секции: заголовок + короткое описание зоны, ниже компактные плитки в 3 колонки.
         Переключатель «Новый интерфейс / Классический» вынесен в топбар. -->
    <div class="space-y-5">
      <section v-for="section in layout" :key="section.type">
        <template v-if="section.title">
          <div class="mb-1.5 flex flex-wrap items-center gap-x-2.5 gap-y-1.5">
            <span class="h-2 w-2 shrink-0 rounded-full" :class="section.dot" />
            <h3 class="text-sm font-semibold text-slate-900">{{ section.title }}</h3>
            <span
              class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider"
              :class="section.tagClass"
            >
              <component :is="section.tagIcon" class="h-3 w-3" />
              {{ section.tagLabel }}
            </span>
          </div>
          <p class="mb-3 max-w-3xl text-xs leading-relaxed text-slate-500">
            {{ section.desc }}
          </p>
        </template>

        <div class="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
          <button
            v-for="tile in section.tiles"
            :key="tile.id"
            type="button"
            class="group relative flex w-full cursor-pointer items-center gap-3 overflow-hidden rounded-2xl border border-slate-100 bg-white p-3 text-left shadow-[0_1px_3px_-1px_rgba(0,0,0,0.04)] transition-all duration-300 hover:border-primary/30 hover:shadow-[0_6px_20px_-8px_rgba(0,0,0,0.08)]"
            :class="tile.dimmed ? 'opacity-60' : ''"
            @click="onTile(tile)"
          >
            <div
              class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl transition-colors"
              :class="accents[tile.accent].chip"
            >
              <component :is="tile.icon" class="h-4 w-4" :class="accents[tile.accent].icon" />
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex items-baseline justify-between gap-1.5">
                <span class="truncate text-xs font-medium text-slate-600 transition-colors group-hover:text-primary">
                  {{ tile.title }}
                </span>
                <span class="shrink-0 text-lg font-bold leading-none text-slate-900">{{ tile.count }}</span>
              </div>
              <p v-if="tile.sub" class="mt-0.5 truncate text-[11px] text-slate-500">
                {{ tile.sub }}
              </p>
            </div>
            <ChevronRight
              class="h-3.5 w-3.5 shrink-0 text-slate-300 transition-all duration-200 group-hover:translate-x-0.5 group-hover:text-primary"
            />
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { navigateTo } from '#app'
import {
  BookOpen, ChevronRight, Database, FileText, GitBranch, Lightbulb, MessageSquare, Quote, ShieldCheck, Table2,
} from 'lucide-vue-next'
import { useScriptFlows } from '~/composables/useScriptFlows'
import { useLayoutState } from '~/composables/useLayoutState'
import type { Directory } from '~/types/directories'
import type { DirectQuestion, KnowledgeFileItem } from '~/types/knowledge'
import type { SqnsTool } from '~/composables/useAgents'
import type { TableItem } from '~/types/tables'

const props = defineProps<{
  directQuestions: DirectQuestion[]
  directories: Directory[]
  tables: TableItem[]
  files: KnowledgeFileItem[]
  sqnsTools: SqnsTool[]
  isSqnsEnabled: boolean
}>()

const emit = defineEmits<{
  (e: 'select', tab: string): void
}>()

// «Новый интерфейс» — глобальный режим (общий стейт). Кнопка-переключатель живёт в топбаре;
// persist самого режима — в сайдбаре (он смонтирован всегда). Здесь только сообщаем топбару,
// что открыт дашборд знаний (чтобы показать кнопку), и читаем режим для раскладки.
const { knowledgeDashboardActive } = useLayoutState()

onMounted(() => {
  knowledgeDashboardActive.value = true
})
onUnmounted(() => {
  knowledgeDashboardActive.value = false
})

const route = useRoute()
const agentId = computed(() => (route.params.id as string) || '')

// Потоки эксперта живут на отдельной странице — тянем их счётчик, чтобы плитка была живой.
const scriptFlowsApi = agentId.value ? useScriptFlows(agentId.value) : null
const scriptFlowsCount = computed(() => scriptFlowsApi?.flows.value.length ?? 0)
const publishedScriptFlows = computed(
  () => (scriptFlowsApi?.flows.value ?? []).filter((f) => f.flow_status === 'published').length,
)
onMounted(() => {
  scriptFlowsApi?.fetchFlows().catch(() => {})
})

const activeDirectQuestions = computed(() => props.directQuestions.filter((q) => q.is_enabled).length)
const totalDirectoryItems = computed(() => props.directories.reduce((acc, d) => acc + (d.items_count ?? 0), 0))
const totalTableItems = computed(() => props.tables.reduce((acc, d) => acc + (d.records_count ?? 0), 0))
const uploadedFiles = computed(() => props.files.filter((f) => f.type === 'file'))
const indexedFiles = computed(() => uploadedFiles.value.filter((f) => f.vector_status === 'indexed').length)

const itemsLabel = (count: number) => {
  if (count % 10 === 1 && count % 100 !== 11) return 'запись'
  if (count % 10 >= 2 && count % 10 <= 4 && (count % 100 < 10 || count % 100 >= 20)) return 'записи'
  return 'записей'
}

// Литеральные классы (чтобы Tailwind их не вырезал при сборке).
const accents: Record<string, { circle: string; chip: string; icon: string }> = {
  indigo: { circle: 'bg-indigo-500/5', chip: 'bg-indigo-50 group-hover:bg-indigo-100', icon: 'text-indigo-600' },
  emerald: { circle: 'bg-emerald-500/5', chip: 'bg-emerald-50 group-hover:bg-emerald-100', icon: 'text-emerald-600' },
  cyan: { circle: 'bg-cyan-500/5', chip: 'bg-cyan-50 group-hover:bg-cyan-100', icon: 'text-cyan-600' },
  violet: { circle: 'bg-violet-500/5', chip: 'bg-violet-50 group-hover:bg-violet-100', icon: 'text-violet-600' },
  amber: { circle: 'bg-amber-500/5', chip: 'bg-amber-50 group-hover:bg-amber-100', icon: 'text-amber-600' },
  purple: { circle: 'bg-purple-500/5', chip: 'bg-purple-50 group-hover:bg-purple-100', icon: 'text-purple-600' },
}

type TileKind = 'tab' | 'route'
type KnowledgeTile = {
  id: string
  kind: TileKind
  type: 'operational' | 'reference' | 'dialogue'
  title: string
  icon: unknown
  accent: string
  count: number
  sub: string
  desc: string
  dimmed?: boolean
}

const tiles = computed<KnowledgeTile[]>(() => [
  {
    id: 'sqns', kind: 'tab', type: 'operational', title: 'SQNS', icon: Database, accent: 'amber',
    count: props.sqnsTools.length,
    sub: props.isSqnsEnabled ? 'подключено' : 'не подключено',
    desc: 'Услуги, цены, специалисты, расписание и записи — синхронизируются из МИС.',
    dimmed: !props.isSqnsEnabled,
  },
  {
    id: 'direct_questions', kind: 'tab', type: 'reference', title: 'Прямые вопросы', icon: MessageSquare, accent: 'indigo',
    count: props.directQuestions.length,
    sub: `${activeDirectQuestions.value} активных`,
    desc: 'Частые вопросы с фоллоуапами — автоотправка сообщения, если пользователь не ответил.',
  },
  {
    id: 'directories', kind: 'tab', type: 'reference', title: 'Справочники', icon: BookOpen, accent: 'emerald',
    count: props.directories.length,
    sub: `${totalDirectoryItems.value} ${itemsLabel(totalDirectoryItems.value)}`,
    desc: 'Ответы в формате «вопрос / ответ», разбитые по категориям.',
  },
  {
    id: 'tables', kind: 'tab', type: 'reference', title: 'Таблицы', icon: Table2, accent: 'cyan',
    count: props.tables.length,
    sub: `${totalTableItems.value} ${itemsLabel(totalTableItems.value)}`,
    desc: 'Структурированные записи с атрибутами для поиска и обновления данных.',
  },
  {
    id: 'file_uploads', kind: 'tab', type: 'reference', title: 'Загрузка файлов', icon: FileText, accent: 'violet',
    count: uploadedFiles.value.length,
    sub: `${indexedFiles.value} проиндексировано`,
    desc: 'Регламенты, подготовка к визиту, PDF и другие документы.',
  },
  {
    id: 'script_flows', kind: 'route', type: 'dialogue', title: 'Потоки эксперта', icon: GitBranch, accent: 'purple',
    count: scriptFlowsCount.value,
    sub: `${publishedScriptFlows.value} опубликовано`,
    desc: 'Тактики, работа с возражениями и тон диалога на визуальной схеме.',
  },
])

type Section = {
  type: string
  title?: string
  dot?: string
  tagClass?: string
  tagIcon?: unknown
  tagLabel?: string
  desc?: string
  tiles: KnowledgeTile[]
}

// Каждая зона описана через «контракт» — как агент относится к её содержимому.
// Это и есть граница, которую админ должен понимать: где истина, а где лишь ориентир.
const SECTION_META = [
  {
    type: 'operational', title: 'Факты клиники', dot: 'bg-amber-500',
    tagClass: 'bg-amber-50 text-amber-700', tagIcon: ShieldCheck, tagLabel: 'истина для агента',
    desc: 'Точные данные клиники — цены, врачи, свободное время. Агент берёт их как истину, дословно и ничего не выдумывает. Приходят из вашей CRM (SQNS), здесь не редактируются.',
  },
  {
    type: 'reference', title: 'Справочные материалы', dot: 'bg-emerald-500',
    tagClass: 'bg-emerald-50 text-emerald-700', tagIcon: Quote, tagLabel: 'источник ответов',
    desc: 'Регламенты, правила и готовые ответы. Агент отвечает пациенту строго по этим материалам. Если ответа здесь нет — честно скажет, что уточнит у администратора.',
  },
  {
    type: 'dialogue', title: 'Сценарии и тактики', dot: 'bg-purple-500',
    tagClass: 'bg-purple-50 text-purple-700', tagIcon: Lightbulb, tagLabel: 'ориентир, не истина',
    desc: 'Манера общения: как объяснить процедуру, снять сомнение, ответить на «дорого». Здесь можно писать примеры фраз — но агент НЕ принимает их за истину и не цитирует дословно, а использует как ориентир.',
  },
]

const layout = computed<Section[]>(() =>
  SECTION_META
    .map((s) => ({ ...s, tiles: tiles.value.filter((t) => t.type === s.type) }))
    .filter((s) => s.tiles.length > 0),
)

const onTile = (tile: KnowledgeTile) => {
  if (tile.kind === 'route') {
    if (agentId.value) navigateTo(`/agents/${agentId.value}/scripts`)
    return
  }
  emit('select', tile.id)
}
</script>
