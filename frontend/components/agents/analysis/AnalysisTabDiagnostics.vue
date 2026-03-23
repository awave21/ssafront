<template>
  <div class="space-y-4">

    <!-- KPI метрики -->
    <div class="grid grid-cols-1 gap-3 sm:grid-cols-3">
      <div
        v-for="kpi in kpiCards"
        :key="kpi.label"
        class="flex flex-col gap-1.5 rounded-xl border border-border bg-card p-3 shadow-sm"
      >
        <span class="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
          {{ kpi.label }}
        </span>
        <span class="text-2xl font-bold" :class="kpi.colorClass">{{ kpi.value }}</span>
        <span class="text-[10px] text-muted-foreground">{{ kpi.description }}</span>
      </div>
    </div>

    <!-- Карточки по типу инструмента -->
    <div class="space-y-2">
      <div class="flex flex-col gap-1 px-1 sm:flex-row sm:items-end sm:justify-between">
        <h3 class="text-[11px] font-bold uppercase tracking-wider text-muted-foreground">
          Ошибки по типу инструмента
        </h3>
        <p class="text-[10px] text-muted-foreground/80 sm:max-w-[55%] sm:text-right">
          Нажмите карточку — справа откроется детализация. Сейчас показываются рекомендации анализа по категории;
          журнал каждого вызова инструмента в диалогах API не отдаёт.
        </p>
      </div>
      <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <button
          v-for="tool in toolTypeCards"
          :key="tool.id"
          type="button"
          class="flex flex-col gap-2 rounded-xl border bg-card p-3 text-left shadow-sm outline-none transition-colors hover:border-primary/40 hover:bg-muted/20 focus-visible:ring-2 focus-visible:ring-primary/30"
          :class="tool.count > 0 ? 'border-border' : 'border-border/50'"
          @click="openToolSheet(tool.id)"
        >
          <div class="flex items-center justify-between">
            <component :is="tool.icon" class="h-4 w-4 text-muted-foreground" />
            <Badge v-if="tool.count > 0" variant="secondary" class="h-4 px-1 text-[9px] font-bold">
              {{ tool.count }}
            </Badge>
          </div>
          <div>
            <p class="text-xs font-semibold text-foreground">{{ tool.label }}</p>
            <p class="mt-0.5 text-[10px] text-muted-foreground">{{ tool.description }}</p>
          </div>
          <div class="h-1 w-full overflow-hidden rounded-full bg-secondary">
            <div class="h-full transition-all" :class="tool.barClass" :style="{ width: `${tool.share}%` }" />
          </div>
        </button>
      </div>
    </div>

    <!-- Боковая панель: детали по типу инструмента -->
    <Sheet :open="toolSheetOpen" @update:open="onToolSheetOpenChange">
      <SheetContent side="right" class-name="flex w-full flex-col p-0 sm:max-w-2xl">
        <SheetHeader class-name="flex flex-row items-start justify-between gap-3 border-border bg-muted/20">
          <div class="min-w-0 flex-1 space-y-1 pr-2">
            <SheetTitle class="text-left text-base">
              {{ activeToolCard?.label || 'Инструмент' }}
            </SheetTitle>
            <SheetDescription class="text-left text-xs leading-relaxed">
              Рекомендации, которые анализатор отнёс к этому типу (по полю «категория»).
              Чтобы видеть фактические tool-calls по сообщениям, нужна доработка бэкенда.
            </SheetDescription>
          </div>
          <SheetClose class-name="shrink-0" />
        </SheetHeader>

        <div class="flex flex-1 flex-col gap-3 overflow-hidden border-t border-border p-4">
          <div
            v-if="!toolSheetRecommendations.length"
            class="rounded-lg border border-dashed border-border bg-muted/30 px-3 py-6 text-center text-xs text-muted-foreground"
          >
            Для этого типа пока нет рекомендаций на текущей странице списка.
            Перейдите на вкладку «Улучшение промта» или смените страницу пагинации рекомендаций.
          </div>
          <ScrollArea v-else class="min-h-0 flex-1 pr-3">
            <ul class="space-y-3 pb-2">
              <li
                v-for="rec in toolSheetRecommendations"
                :key="rec.id"
                class="rounded-lg border border-border bg-card p-3 text-xs shadow-sm"
              >
                <p class="font-semibold text-foreground">{{ rec.title }}</p>
                <p v-if="rec.category" class="mt-1 font-mono text-[10px] text-muted-foreground">
                  {{ rec.category }}
                </p>
                <p v-if="rec.suggestion" class="mt-2 whitespace-pre-wrap break-words italic text-muted-foreground">
                  {{ rec.suggestion }}
                </p>
                <p v-else-if="rec.reasoning" class="mt-2 whitespace-pre-wrap break-words text-muted-foreground/80">
                  {{ rec.reasoning }}
                </p>
                <div v-if="(rec.evidence_dialog_ids || []).length" class="mt-2 flex flex-wrap gap-1">
                  <span
                    v-for="dialogId in rec.evidence_dialog_ids!.slice(0, 5)"
                    :key="dialogId"
                    class="rounded border border-border/60 bg-muted px-1 py-0.5 font-mono text-[9px] text-muted-foreground"
                  >
                    #{{ dialogId.split('-')[0] }}
                  </span>
                </div>
              </li>
            </ul>
          </ScrollArea>
        </div>
      </SheetContent>
    </Sheet>

    <!-- Таблица тем -->
    <Card class="border-none shadow-sm">
      <CardHeader class="pb-3 pt-4">
        <div class="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
          <CardTitle class="text-sm font-bold">Темы диалогов</CardTitle>
          <CardDescription class="max-w-xl text-xs leading-relaxed sm:text-right">
            {{ report?.topics?.length || 0 }} тем.
            Один <span class="font-medium text-foreground">ID диалога</span> — одна сессия переписки (линия пациента/пользователя с агентом).
            После следующего запуска анализа в отчёте появятся примеры ID в колонке «Обращения».
            <NuxtLink
              v-if="agentId"
              :to="`/agents/${agentId}/chat`"
              class="ml-1 font-medium text-primary underline-offset-2 hover:underline"
            >Открыть чат</NuxtLink>
          </CardDescription>
        </div>
      </CardHeader>
      <CardContent class="p-0">
        <div
          v-if="!report?.topics?.length"
          class="py-12 text-center text-xs text-muted-foreground"
        >
          Данные появятся после завершения анализа
        </div>
        <Table v-else>
          <TableHeader class="bg-muted/30">
            <TableRow>
              <TableHead class="h-9 text-[10px] uppercase tracking-wider">Тема</TableHead>
              <TableHead class="h-9 text-[10px] uppercase tracking-wider">Доля</TableHead>
              <TableHead class="h-9 text-[10px] uppercase tracking-wider">Всего</TableHead>
              <TableHead class="h-9 min-w-[140px] text-[10px] uppercase tracking-wider">Обращения</TableHead>
              <TableHead class="h-9 text-[10px] uppercase tracking-wider">Здоровье</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow
              v-for="topic in report.topics"
              :key="topic.name"
              class="cursor-pointer transition-colors hover:bg-muted/30"
              :class="selectedTopicName === topic.name ? 'bg-primary/5' : ''"
              @click="emit('update:selectedTopicName', selectedTopicName === topic.name ? '' : topic.name)"
            >
              <TableCell class="py-2.5 text-xs font-medium">
                <div class="flex items-center gap-2">
                  <div
                    v-if="isFailureTopic(topic.name)"
                    class="h-1.5 w-1.5 shrink-0 rounded-full bg-red-500"
                  />
                  {{ topic.name }}
                </div>
              </TableCell>
              <TableCell class="py-2.5 text-xs">{{ formatPercent(topic.share) }}</TableCell>
              <TableCell class="py-2.5 font-mono text-xs">{{ formatNumber(topic.dialogs_count) }}</TableCell>
              <TableCell class="py-2.5">
                <div v-if="(topic.evidence_dialog_ids || []).length" class="flex flex-wrap gap-1">
                  <button
                    v-for="did in (topic.evidence_dialog_ids || []).slice(0, 4)"
                    :key="did"
                    type="button"
                    class="max-w-[120px] truncate rounded border border-border/60 bg-muted px-1 py-0.5 font-mono text-[9px] text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
                    :title="`Скопировать: ${did}`"
                    @click.stop="copyDialogId(did)"
                  >
                    {{ shortDialogId(did) }}
                  </button>
                  <span
                    v-if="(topic.evidence_dialog_ids || []).length > 4"
                    class="self-center text-[9px] text-muted-foreground"
                  >
                    +{{ topic.evidence_dialog_ids!.length - 4 }}
                  </span>
                </div>
                <span v-else class="text-[10px] text-muted-foreground">—</span>
              </TableCell>
              <TableCell class="py-2.5">
                <div class="flex items-center gap-1.5">
                  <div class="h-1 w-10 overflow-hidden rounded-full bg-secondary">
                    <div
                      class="h-full"
                      :class="getHealthBarClassForTopic(topic.health)"
                      :style="{ width: `${topicHealthBarPercent(topic.health)}%` }"
                    />
                  </div>
                  <span class="text-[10px] font-bold">{{ topicHealthLabel(topic.health) }}</span>
                </div>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </CardContent>
    </Card>

    <!-- Проблемные темы -->
    <div
      v-if="(report?.top_failure_topics || []).length"
      class="rounded-xl border border-red-100 bg-red-50/50 p-3"
    >
      <div class="mb-2 flex items-center gap-2">
        <AlertTriangle class="h-3.5 w-3.5 text-red-500" />
        <span class="text-[11px] font-bold uppercase tracking-wider text-red-700">Проблемные темы</span>
      </div>
      <div class="flex flex-wrap gap-1.5">
        <Badge
          v-for="topic in report!.top_failure_topics"
          :key="topic"
          variant="outline"
          class="border-red-200 bg-red-50 text-[10px] text-red-700"
        >
          {{ topic }}
        </Badge>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { AlertTriangle } from 'lucide-vue-next'
import Badge from '~/components/ui/badge/Badge.vue'
import Card from '~/components/ui/card/Card.vue'
import CardContent from '~/components/ui/card/CardContent.vue'
import CardDescription from '~/components/ui/card/CardDescription.vue'
import CardHeader from '~/components/ui/card/CardHeader.vue'
import CardTitle from '~/components/ui/card/CardTitle.vue'
import ScrollArea from '~/components/ui/scroll-area/ScrollArea.vue'
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '~/components/ui/sheet'
import Table from '~/components/ui/table/Table.vue'
import TableBody from '~/components/ui/table/TableBody.vue'
import TableCell from '~/components/ui/table/TableCell.vue'
import TableHead from '~/components/ui/table/TableHead.vue'
import TableHeader from '~/components/ui/table/TableHeader.vue'
import TableRow from '~/components/ui/table/TableRow.vue'
import type { AnalysisRecommendation, AnalysisReport } from '~/types/agent-analysis'
import { useToast } from '~/composables/useToast'
import type { KpiCard, ToolTypeCard } from './constants'
import {
  formatNumber,
  formatPercent,
  getHealthBarClassForTopic,
  getRecommendationsForToolTypeId,
  topicHealthBarPercent,
  topicHealthLabel,
} from './constants'

const props = defineProps<{
  agentId: string
  kpiCards: KpiCard[]
  toolTypeCards: ToolTypeCard[]
  recommendations: AnalysisRecommendation[]
  report: AnalysisReport | null
  selectedTopicName: string
}>()

const { success: toastSuccess, error: toastError } = useToast()

const shortDialogId = (id: string) => {
  const t = id.trim()
  if (t.length <= 14) return t
  return `${t.slice(0, 8)}…${t.slice(-4)}`
}

const copyDialogId = async (id: string) => {
  try {
    await navigator.clipboard.writeText(id)
    toastSuccess('Скопировано', 'ID диалога в буфере обмена')
  } catch {
    toastError('Не удалось скопировать', id)
  }
}

const emit = defineEmits<{
  'update:selectedTopicName': [value: string]
}>()

const toolSheetOpen = ref(false)
const selectedToolId = ref<string | null>(null)

const activeToolCard = computed(() =>
  props.toolTypeCards.find((t) => t.id === selectedToolId.value) ?? null
)

const toolSheetRecommendations = computed(() => {
  if (!selectedToolId.value) return []
  return getRecommendationsForToolTypeId(selectedToolId.value, props.recommendations)
})

const openToolSheet = (toolId: string) => {
  selectedToolId.value = toolId
  toolSheetOpen.value = true
}

const onToolSheetOpenChange = (open: boolean) => {
  toolSheetOpen.value = open
  if (!open) selectedToolId.value = null
}

const isFailureTopic = (topicName: string) =>
  (props.report?.top_failure_topics || []).includes(topicName)
</script>
