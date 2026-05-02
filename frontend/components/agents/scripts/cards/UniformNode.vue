<template>
  <div
    v-memo="[props.data, props.selected, props.warnOrphan, props.warnCoverage, props.runtimeUsage?.count ?? 0]"
    class="uniform-node relative flex flex-col overflow-visible rounded-xl border bg-card"
    :class="[
      props.warnOrphan ? 'ring-2 ring-amber-500/55' : '',
      props.warnCoverage ? 'ring-2 ring-destructive/55' : '',
      isStandalone ? 'dashed-border-card' : '',
    ]"
    :style="{
      width: '220px',
      borderColor: isSelected ? accent : 'hsl(var(--border))',
      borderWidth: isSelected ? '2px' : '1px',
      contain: 'layout',
      boxShadow: isSelected
        ? `0 6px 18px rgba(15,23,42,0.14), 0 0 0 2px ${accent}28`
        : '0 1px 6px rgba(15,23,42,0.06), 0 1px 3px rgba(15,23,42,0.05)',
    }"
  >
    <!-- Цветная вертикальная полоса слева — тип ноды -->
    <span
      class="pointer-events-none absolute left-0 top-0 h-full w-[3px] rounded-l-xl"
      :style="{ backgroundColor: accent }"
    />

    <FlowN8nConnector
      v-if="!isStandalone"
      :node-id="id"
      handle-type="target"
      handle-id="target"
      :connect-position="Position.Left"
      :accent="accent"
      :highlight-line="isSelected"
      side="left"
    />

    <!-- Шапка: эмодзи + заголовок + статус-точки -->
    <div class="flex h-[64px] items-center gap-2.5 px-3 py-2">
      <span
        class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-base leading-none"
        :style="{ backgroundColor: `${accent}24` }"
      >{{ typeEmoji }}</span>

      <div class="min-w-0 flex-1">
        <div class="truncate text-[12.5px] font-semibold leading-tight text-foreground">{{ cardTitle }}</div>
        <div class="mt-0.5 truncate text-[10px] leading-tight text-muted-foreground">{{ typeSubtitle }}</div>
      </div>

      <!-- Status dots (вертикально, справа) -->
      <div class="flex shrink-0 flex-col items-end gap-1">
        <span
          v-if="readinessTone !== 'ok'"
          class="h-1.5 w-1.5 rounded-full"
          :class="readinessTone === 'danger' ? 'bg-red-500' : 'bg-amber-400'"
          :title="readinessTone === 'danger' ? 'Заполните основные поля' : 'Не хватает связей со знаниями'"
        />
        <span
          v-if="kgLinkCount > 0"
          class="h-1.5 min-w-[6px] rounded-full bg-indigo-500"
          :title="`Связи: ${kgLinkCount}`"
        />
        <span
          v-if="(props.runtimeUsage?.count ?? 0) > 0"
          class="h-1.5 w-1.5 rounded-full bg-cyan-500"
          :title="`Использований: ${props.runtimeUsage?.count ?? 0}`"
        />
      </div>
    </div>

    <!-- Маркер «вход в поток» для trigger -->
    <span
      v-if="isEntry"
      class="pointer-events-none absolute left-1.5 top-1.5 text-[8px] font-bold uppercase tracking-widest"
      :style="{ color: accent }"
    >вход</span>

    <!-- Условная нода — дерево-развилка.
         SVG-ствол сидит в левом 28px-гуттере и НЕ пересекает текст.
         Подписи и handles — справа. -->
    <template v-if="isCondition && allBranches.length">
      <div
        class="condition-fork relative border-t border-border/60 pr-3 pt-3 pb-2"
        :style="{ background: `${accent}08` }"
      >
        <!-- SVG-дерево: только в левом 28px-гуттере, не залезает на текст -->
        <svg
          class="pointer-events-none absolute left-0 top-0 h-full"
          :viewBox="`0 0 28 ${forkSvgHeight}`"
          :height="forkSvgHeight"
          width="28"
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          <!-- Junction-точка наверху (выход из шапки) -->
          <circle cx="14" cy="6" r="3.5" :fill="accent" />
          <!-- Вертикальный ствол -->
          <line
            x1="14" :y1="6"
            x2="14" :y2="forkTrunkBottom"
            :stroke="accent"
            stroke-width="1.5"
            stroke-linecap="round"
            opacity="0.75"
          />
          <!-- Короткие горизонтальные стабы: ствол → начало текста (12px вправо) -->
          <line
            v-for="i in branchRowIndices"
            :key="i"
            x1="14"
            :y1="forkBranchY(i)"
            x2="26"
            :y2="forkBranchY(i)"
            :stroke="i === branchRowIndices.length - 1 ? 'hsl(var(--muted-foreground))' : accent"
            stroke-width="1.5"
            stroke-linecap="round"
            :opacity="i === branchRowIndices.length - 1 ? 0.55 : 0.85"
          />
          <!-- Точка-узел на стволе в начале каждой ветки -->
          <circle
            v-for="i in branchRowIndices"
            :key="`d-${i}`"
            cx="14"
            :cy="forkBranchY(i)"
            r="2"
            :fill="i === branchRowIndices.length - 1 ? 'hsl(var(--muted-foreground))' : accent"
          />
        </svg>

        <!-- Подписи веток (с pl-7 чтобы стартовали ПОСЛЕ SVG-гуттера) -->
        <div class="relative flex flex-col gap-1.5 pl-7">
          <div
            v-for="(br, i) in visibleBranches"
            :key="br.id"
            class="flex h-5 items-center"
          >
            <span class="min-w-0 flex-1 truncate text-[10px] font-medium leading-none text-foreground/90">
              {{ String(br.label).trim() || `Ветка ${i + 1}` }}
            </span>
          </div>
          <!-- Default fallback (серый) -->
          <div class="flex h-5 items-center">
            <span class="min-w-0 flex-1 truncate text-[10px] italic leading-none text-muted-foreground">
              По умолчанию
            </span>
          </div>
        </div>

        <!-- HANDLES СНАРУЖИ карточки на правой кромке, по одному на каждую ветку.
             Каждый позиционирован absolutely на Y-уровне своей строки. -->
        <div
          v-for="(br, i) in visibleBranches"
          :key="`ext-${br.id}`"
          class="pointer-events-none absolute z-[5] flex -translate-y-1/2 items-center"
          :style="{ left: '100%', top: `${forkBranchY(i)}px` }"
        >
          <FlowN8nConnector
            :node-id="id"
            variant="inline"
            handle-type="source"
            :handle-id="branchHandleId(br.id)"
            :connect-position="Position.Right"
            :accent="accent"
            :highlight-line="isSelected"
            line-width-class="w-6"
          />
        </div>
        <div
          class="pointer-events-none absolute z-[5] flex -translate-y-1/2 items-center"
          :style="{ left: '100%', top: `${forkBranchY(visibleBranches.length)}px` }"
        >
          <FlowN8nConnector
            :node-id="id"
            variant="inline"
            handle-type="source"
            handle-id="cond-default"
            :connect-position="Position.Right"
            accent="hsl(var(--muted-foreground) / 0.7)"
            :highlight-line="isSelected"
            line-width-class="w-6"
          />
        </div>

        <!-- Сообщение «есть ещё ветки» -->
        <div
          v-if="hiddenBranchesCount > 0"
          class="relative mt-1 pl-1 text-[9px] italic text-muted-foreground"
        >
          + ещё {{ hiddenBranchesCount }} {{ pluralBranches(hiddenBranchesCount) }}, открыть в редакторе
        </div>
      </div>
    </template>

    <FlowN8nConnector
      v-if="!isStandalone && !isCondition"
      :node-id="id"
      handle-type="source"
      handle-id="source"
      :connect-position="Position.Right"
      :accent="accent"
      :highlight-line="isSelected"
      side="right"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, inject, ref, type Ref } from 'vue'
import FlowN8nConnector from './FlowN8nConnector.vue'

/** Position — string enum, раньше был из @vue-flow/core. */
const Position = { Left: 'left', Right: 'right', Top: 'top', Bottom: 'bottom' } as const
import type { FlowBranch, NodeType, ScriptFlowToolUsageNode, ScriptNodeData } from '~/types/scriptFlow'
import { NODE_TYPE_COLORS, NODE_TYPES } from '~/types/scriptFlow'
import { branchSourceHandleId, isStandaloneCatalogRule, normalizeConditionsToBranches } from '~/utils/scriptFlowNodeRole'

const NODE_EMOJIS: Record<string, string> = {
  trigger: '⚡',
  expertise: '🧠',
  question: '❓',
  condition: '🔀',
  goto: '➡️',
  end: '🔴',
  business_rule: '📋',
}

const MAX_VISIBLE_BRANCHES = 5

const props = defineProps<{
  id: string
  data: ScriptNodeData & { content?: string }
  selected?: boolean
  warnOrphan?: boolean
  warnCoverage?: boolean
  runtimeUsage?: ScriptFlowToolUsageNode | null
}>()

const isSelected = computed(() => !!props.selected)

/** ID ноды, которую сейчас тащат (или null). Set'ится только на реальный drag-start, не на mousedown. */
const draggingNodeId = inject<Ref<string | null>>('draggingNodeId', ref(null))
const isThisNodeDragging = computed(() => draggingNodeId.value === props.id)

const nodeType = computed<NodeType>(() => (props.data.node_type as NodeType) || 'expertise')

const isCondition = computed(() => nodeType.value === 'condition')
const isStandalone = computed(() => isStandaloneCatalogRule(props.data))

const accent = computed(() => NODE_TYPE_COLORS[nodeType.value] || '#10b981')
const typeEmoji = computed(() => NODE_EMOJIS[nodeType.value] || '🎯')
const typeSubtitle = computed(() =>
  NODE_TYPES.find(t => t.value === nodeType.value)?.label ?? 'Шаг сценария',
)

const cardTitle = computed(() => {
  const t = String(props.data.title ?? props.data.label ?? '').trim()
  return t || typeSubtitle.value
})

const allBranches = computed<FlowBranch[]>(() =>
  isCondition.value ? normalizeConditionsToBranches(props.data.conditions) : [],
)

const visibleBranches = computed(() => allBranches.value.slice(0, MAX_VISIBLE_BRANCHES))
const hiddenBranchesCount = computed(() =>
  Math.max(0, allBranches.value.length - MAX_VISIBLE_BRANCHES),
)

const branchHandleId = (id: string) => branchSourceHandleId(id)

// ── Геометрия SVG-развилки (ствол + ветки) ──────────────────────────────────
// Должны совпадать с CSS-классами строк ниже: pt-3 (12px) / h-5 (20px) / gap-1.5 (6px) / pb-2 (8px)
const FORK_TOP_PAD = 12
const FORK_ROW_HEIGHT = 20
const FORK_ROW_GAP = 6
const FORK_BOTTOM_PAD = 8

/** Кол-во рисуемых строк (видимые ветки + одна "по умолчанию"). */
const totalBranchRowsCount = computed(() => visibleBranches.value.length + 1)

/** Y-центр i-й строки в SVG-координатах. */
const forkBranchY = (i: number) =>
  FORK_TOP_PAD + i * (FORK_ROW_HEIGHT + FORK_ROW_GAP) + FORK_ROW_HEIGHT / 2

/** Y-низ ствола = Y-центр последней строки (default-fallback). */
const forkTrunkBottom = computed(() => forkBranchY(totalBranchRowsCount.value - 1))

/** Полная высота SVG-области (равна высоте branches-блока). */
const forkSvgHeight = computed(() =>
  FORK_TOP_PAD
  + totalBranchRowsCount.value * FORK_ROW_HEIGHT
  + (totalBranchRowsCount.value - 1) * FORK_ROW_GAP
  + FORK_BOTTOM_PAD,
)

/** Массив 0..N-1 для удобного v-for в SVG. */
const branchRowIndices = computed(() =>
  Array.from({ length: totalBranchRowsCount.value }, (_, i) => i),
)

const pluralBranches = (n: number) => {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return 'ветка'
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return 'ветки'
  return 'веток'
}

const kgLinkCount = computed(() => {
  const kg = props.data.kg_links as Record<string, unknown> | null | undefined
  if (!kg) return 0
  const arrLen = (x: unknown) => (Array.isArray(x) ? (x as unknown[]).length : 0)
  return (
    arrLen(kg.motive_ids)
    + arrLen(kg.argument_ids)
    + arrLen(kg.proof_ids)
    + arrLen(kg.objection_ids)
    + arrLen(kg.constraint_ids)
    + (kg.outcome_id ? 1 : 0)
  )
})

const isEntry = computed(() =>
  props.data.node_type === 'trigger'
  && (props.data.is_flow_entry ?? props.data.is_entry_point !== false))

const needsKgLinks = computed(() =>
  ['expertise', 'question', 'end'].includes(nodeType.value),
)

const hasContent = computed(() => {
  const nt = nodeType.value
  if (nt === 'trigger') {
    const phrases = props.data.client_phrase_examples ?? props.data.example_phrases
    return Array.isArray(phrases) && phrases.some(p => String(p).trim())
  }
  if (nt === 'question') return Boolean(String(props.data.good_question ?? '').trim())
  if (nt === 'condition') return allBranches.value.length > 0
  if (nt === 'end') return Boolean(String(props.data.final_action ?? '').trim())
  if (nt === 'goto') return Boolean(String(props.data.target_flow_id ?? '').trim())
  if (nt === 'business_rule')
    return Boolean(String(props.data.rule_condition ?? '').trim() || String(props.data.rule_action ?? '').trim())
  return Boolean(String(props.data.situation ?? props.data.approach ?? '').trim())
})

const readinessTone = computed<'ok' | 'warn' | 'danger'>(() => {
  if (!hasContent.value) return 'danger'
  if (needsKgLinks.value && kgLinkCount.value === 0) return 'warn'
  return 'ok'
})
</script>

<style scoped>
.dashed-border-card {
  border-style: dashed;
}
</style>
