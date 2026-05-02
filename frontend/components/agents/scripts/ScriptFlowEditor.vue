<template>
  <div class="flex h-full min-h-0 w-full flex-row overflow-hidden bg-background">
    <div
      ref="canvasWrapperRef"
      class="relative min-h-0 min-w-0 flex-1"
      @drop="onDrop"
      @dragover="onDragOver"
    >
      <CustomFlow
        v-if="viewMode === 'schema'"
        ref="customFlowRef"
        v-model:nodes="nodes"
        v-model:edges="edges"
        :default-viewport="defaultViewport"
        :default-edge-stroke="'rgba(99, 102, 241, 0.55)'"
        class="script-flow-canvas h-full w-full"
        :class="{ 'is-dragging': isDraggingNode }"
        @node-click="onNodeClick"
        @node-double-click="onNodeDblClick"
        @edge-click="onEdgeClick"
        @pane-click="onPaneClick"
        @node-drag-start="onNodeDragStart"
        @node-drag-stop="onNodeDragStop"
        @drop="onCustomFlowDrop"
        @connect="onConnect"
      >
        <!-- Custom node rendering — все типы рендерятся через ExpertNode (он сам разруливает по data.node_type). -->
        <template #node-default="nodeProps">
          <ExpertNode
            :id="nodeProps.id"
            :data="nodeProps.data"
            :selected="nodeProps.selected"
          />
        </template>
      </CustomFlow>

      <!-- Empty-state поверх канваса. -->
      <div
        v-if="viewMode === 'schema' && nodes.length === 0"
        class="pointer-events-none absolute left-4 top-4 z-[5] max-w-sm"
      >
        <div class="rounded-2xl border border-border/70 bg-background/92 px-4 py-3 shadow-xl backdrop-blur-md">
          <p class="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">Карта разговора</p>
          <p class="mt-1 text-sm font-semibold text-foreground">Собирайте сценарий как цепочку понятных шагов</p>
          <p class="mt-1.5 text-[11px] leading-relaxed text-muted-foreground">
            Нажмите <strong>+</strong> справа чтобы добавить первый шаг, или перетащите его на холст.
          </p>
        </div>
      </div>

      <!-- Зум-контролы (+/−/fitView/lock). -->
      <div
        v-if="viewMode === 'schema'"
        class="pointer-events-none absolute bottom-4 left-4 z-[10] flex flex-row items-end gap-3"
      >
        <div class="script-flow-zoom-controls pointer-events-auto flex flex-row overflow-hidden rounded-lg border border-border bg-card shadow-md">
          <button class="flex h-9 w-9 items-center justify-center text-muted-foreground transition-colors hover:bg-muted disabled:opacity-40" type="button" title="Увеличить" :disabled="zoomMaxReached" @click="zoomIn()">
            <ZoomIn class="h-3.5 w-3.5" aria-hidden="true" />
          </button>
          <button class="flex h-9 w-9 items-center justify-center text-muted-foreground transition-colors hover:bg-muted disabled:opacity-40" type="button" title="Уменьшить" :disabled="zoomMinReached" @click="zoomOut()">
            <ZoomOut class="h-3.5 w-3.5" aria-hidden="true" />
          </button>
          <button class="flex h-9 w-9 items-center justify-center text-muted-foreground transition-colors hover:bg-muted" type="button" title="Весь граф на экране" @click="resetView">
            <Maximize2 class="h-3.5 w-3.5" aria-hidden="true" />
          </button>
          <button class="flex h-9 w-9 items-center justify-center text-muted-foreground transition-colors hover:bg-muted" type="button" :title="interactionLocked ? 'Разблокировать' : 'Заблокировать'" @click="toggleViewportInteraction">
            <Lock v-if="interactionLocked" class="h-3.5 w-3.5" aria-hidden="true" />
            <Unlock v-else class="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        </div>
      </div>

      <!-- Toolbar справа. -->
      <div class="pointer-events-auto absolute right-4 top-1/2 z-[60] flex -translate-y-1/2 flex-col gap-2">
        <div class="canvas-toolbar flex flex-col gap-1 rounded-xl border border-border bg-card/95 p-1.5 shadow-xl backdrop-blur-md">
          <button v-if="viewMode === 'schema'" type="button" class="flex size-10 items-center justify-center rounded-lg transition-colors hover:bg-muted" :class="isPaletteOpen ? 'bg-primary text-primary-foreground hover:bg-primary/90' : 'text-muted-foreground'" title="Добавить шаг разговора" @click="isPaletteOpen = !isPaletteOpen">
            <Plus class="size-5" />
          </button>
          <button v-if="viewMode === 'schema'" type="button" class="flex size-10 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted" title="Поиск узла (Ctrl+K)" @click="nodeSearchOpen = true">
            <Search class="size-5" />
          </button>
          <button v-if="viewMode === 'schema'" type="button" class="flex size-10 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted" title="Режим списка: шаги как playbook" @click="emit('update:viewMode', 'list')">
            <FileText class="size-5" />
          </button>
          <button v-if="viewMode === 'list'" type="button" class="flex size-10 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted" title="Режим карты: ветки разговора на холсте" @click="emit('update:viewMode', 'schema')">
            <Network class="size-5" />
          </button>
          <button v-if="viewMode === 'schema'" type="button" class="flex size-10 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted" title="Шаблоны сценария" @click="openTemplatePickerFromMenu">
            <Sparkles class="size-5" />
          </button>

          <button type="button" class="flex size-10 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted" title="Как собрать понятный сценарий" @click="isCanvasGuideOpen = true">
            <HelpCircle class="size-5" />
          </button>
        </div>
      </div>

      <!-- List-view fallback (когда viewMode === 'list'). -->
      <div v-if="viewMode === 'list'" class="absolute inset-0 z-[10] flex h-full min-h-0 w-full flex-col overflow-hidden bg-background">
        <div class="border-b border-border bg-background/95 px-4 py-3 text-[11px] leading-relaxed text-muted-foreground">
          Здесь удобнее собирать сценарий как набор смысловых шагов: когда включаться в разговор, что отвечать клиенту и как вести его дальше.
        </div>
        <TacticLibraryView :flow-definition="flowDefinition" />
      </div>

      <!-- Edge delete popup (click on edge to delete it) -->
      <Transition
        enter-active-class="transition-all duration-150 ease-out"
        enter-from-class="opacity-0 scale-95"
        enter-to-class="opacity-100 scale-100"
        leave-active-class="transition-all duration-100 ease-in"
        leave-from-class="opacity-100 scale-100"
        leave-to-class="opacity-0 scale-95"
      >
        <div
          v-if="edgeLabelPopup.visible"
          class="absolute z-50 flex items-center gap-2 rounded-xl border border-border bg-card px-3 py-2 shadow-2xl"
          :style="{ left: `${edgeLabelPopup.x}px`, top: `${edgeLabelPopup.y}px` }"
        >
          <span class="text-[11px] text-muted-foreground">Удалить линию?</span>
          <button
            class="rounded-lg bg-destructive/10 border border-destructive/30 px-3 py-1 text-xs font-bold text-destructive hover:bg-destructive/20 transition-colors"
            @click="deleteSelectedEdge"
          >Удалить</button>
          <button
            class="rounded-lg border border-border px-2 py-1 text-xs text-muted-foreground hover:bg-muted transition-colors"
            @click="closeEdgeLabelPopup"
          >✕</button>
        </div>
      </Transition>

      <!-- Ctrl+K поиск узла -->
      <Teleport to="body">
        <div
          v-if="nodeSearchOpen"
          class="fixed inset-0 z-[100] flex items-start justify-center bg-black/40 pt-[15vh] px-4"
          @click.self="nodeSearchOpen = false"
        >
          <div class="w-full max-w-md rounded-xl border border-border bg-card p-3 shadow-2xl">
            <input
              ref="nodeSearchInputRef"
              v-model="nodeSearchQuery"
              type="text"
              placeholder="Поиск узла по названию или тексту…"
              class="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none ring-primary/30 focus:ring-2"
              @keydown.escape="nodeSearchOpen = false"
            >
            <ul class="mt-2 max-h-56 overflow-auto text-sm">
              <li
                v-for="opt in filteredSearchNodes"
                :key="opt.id"
              >
                <button
                  type="button"
                  class="flex w-full flex-col gap-0.5 rounded-md px-2 py-2 text-left hover:bg-muted"
                  @click="focusSearchNode(opt.id)"
                >
                  <span class="font-medium">{{ opt.title }}</span>
                  <span class="text-[10px] text-muted-foreground">{{ opt.sub }}</span>
                </button>
              </li>
              <li v-if="!filteredSearchNodes.length" class="px-2 py-4 text-center text-muted-foreground text-xs">
                Ничего не найдено
              </li>
            </ul>
          </div>
        </div>
      </Teleport>
    </div>

    <!-- Палитра: открывается и из тулбара, и по клику + на source-хэндле ноды -->
    <Sheet
      :open="isPaletteOpen"
      :modal="false"
      @update:open="isPaletteOpen = $event"
    >
      <SheetContent
        side="right"
        :hide-overlay="true"
        class-name="w-full sm:max-w-[360px] p-0 border-l border-border !bg-card shadow-2xl"
      >
        <SheetTitle class="sr-only">Палитра шагов сценария</SheetTitle>
        <div class="flex h-full min-h-0 flex-col overflow-y-auto">
          <div class="border-b border-border px-4 py-4">
            <h4 class="text-xs font-bold uppercase tracking-widest text-muted-foreground">Добавить шаг разговора</h4>
            <p class="mt-1.5 text-[11px] leading-relaxed text-muted-foreground">
              {{ paletteSourceNode ? 'Выберите тип следующего шага — он будет связан с текущим.' : 'Выберите нужный смысловой блок и перетащите его на карту разговора.' }}
            </p>
          </div>
          <div class="flex flex-col gap-2 border-b border-border p-3">
            <button
              v-for="row in scenarioPalette"
              :key="row.type"
              type="button"
              :draggable="!paletteSourceNode"
              :title="paletteDescription(row.type)"
              class="flex w-full cursor-grab flex-col items-start rounded-xl border border-border/80 bg-background px-4 py-3.5 text-left transition-colors hover:border-primary/30 hover:bg-muted/40 active:cursor-grabbing"
              @dragstart="onPaletteDragStart($event, row.type, false)"
              @click="paletteSourceNode ? addNodeFromPalette(row.type, false) : undefined"
            >
              <div class="flex w-full items-center justify-between gap-3">
                <span class="text-sm font-semibold leading-snug text-foreground">{{ row.label }}</span>
                <span class="rounded-full border border-border bg-muted/40 px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                  шаг
                </span>
              </div>
              <span class="mt-1 text-[11px] leading-relaxed text-muted-foreground">{{ paletteDescription(row.type) }}</span>
            </button>
          </div>

          <div class="border-b border-border px-4 py-3">
            <h4 class="text-xs font-bold uppercase tracking-widest text-muted-foreground">Стандарты клиники</h4>
            <p class="mt-1 text-[11px] leading-relaxed text-muted-foreground">
              Отдельные правила для услуг и сотрудников, которые можно держать рядом со сценарием.
            </p>
          </div>
          <div class="flex flex-col gap-2 border-b border-border p-3">
            <button
              v-for="row in catalogPalette"
              :key="row.type"
              type="button"
              :draggable="!paletteSourceNode"
              :title="paletteDescription(row.type)"
              class="flex w-full cursor-grab flex-col items-start rounded-xl border border-sky-200/80 bg-background px-4 py-3.5 text-left transition-colors hover:border-sky-400/40 hover:bg-sky-50/70 active:cursor-grabbing"
              @dragstart="onPaletteDragStart($event, row.type, true)"
              @click="paletteSourceNode ? addNodeFromPalette(row.type, true) : undefined"
            >
              <div class="flex w-full items-center justify-between gap-3">
                <span class="text-sm font-semibold leading-snug text-foreground">{{ row.label }}</span>
                <span class="rounded-full border border-sky-200 bg-sky-50 px-2 py-0.5 text-[10px] font-medium text-sky-700">
                  правило
                </span>
              </div>
              <span class="mt-1 text-[11px] leading-relaxed text-muted-foreground">{{ paletteDescription(row.type) }}</span>
            </button>
          </div>

          <div class="mt-auto border-t border-border">
            <button
              type="button"
              class="w-full rounded-none px-4 py-4 text-sm font-bold text-foreground transition-colors hover:bg-muted"
              title="Аккуратно разложить шаги на карте"
              @click="runAutoLayout"
            >
              Расставить шаги
            </button>
          </div>
        </div>
      </SheetContent>
    </Sheet>

    <Sheet
      :open="isInspectorOpen"
      :modal="false"
      @update:open="onInspectorOpenChange"
    >
      <SheetContent
        side="right"
        :hide-overlay="true"
        class-name="w-full sm:max-w-[480px] md:max-w-[560px] p-0 border-l border-border !bg-background shadow-2xl flex flex-col min-h-0 max-h-[100vh]"
      >
        <SheetTitle class="sr-only">
          {{ inspectorTemplateLabel ? `Шаблон: ${inspectorTemplateLabel}` : 'Параметры узла' }}
        </SheetTitle>
        <div class="flex min-h-0 flex-1 flex-col overflow-hidden">
          <div
            v-if="inspectorTemplateLabel"
            class="shrink-0 border-b border-border bg-muted/30 px-4 py-2.5"
          >
            <p class="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Шаблон сценария</p>
            <p class="text-sm font-semibold text-foreground">{{ inspectorTemplateLabel }}</p>
          </div>
          <ScriptFlowNodeInspector
            class="min-h-0 flex-1"
            :node-id="inspectorNodeId"
            @clear="inspectorNodeId = null"
            @open-node="focusCanvasNode"
            @focus-node="focusCanvasNode"
            @remove-connection="removeCanvasEdge"
            @add-connection="addCanvasConnectionFromInspector"
          />
        </div>
      </SheetContent>
    </Sheet>


    <Sheet
      :open="isTemplatePickerOpen"
      :modal="false"
      @update:open="onTemplatePickerOpenChange"
    >
      <SheetContent
        side="right"
        :hide-overlay="true"
        class-name="w-full sm:max-w-[380px] p-0 border-l border-border !bg-card shadow-2xl"
      >
        <SheetTitle class="sr-only">Шаблоны сценария</SheetTitle>
        <div class="flex h-full min-h-0 flex-col overflow-y-auto">
          <div class="border-b border-border px-4 py-3.5">
            <div class="flex items-center justify-between gap-2">
              <h4 class="text-xs font-bold uppercase tracking-widest text-muted-foreground">
                Шаблоны сценария
              </h4>
              <span class="rounded-md border border-border bg-muted/40 px-2 py-0.5 text-[10px] font-semibold text-muted-foreground">
                {{ SCRIPT_FLOW_TEMPLATE_LIST.length }}
              </span>
            </div>
            <p class="mt-1.5 text-[11px] leading-snug text-muted-foreground">
              Выберите готовую схему. После подтверждения текущие узлы и связи на канвасе будут заменены.
            </p>
          </div>
          <div class="flex flex-col gap-2 p-2">
            <button
              v-for="tmpl in SCRIPT_FLOW_TEMPLATE_LIST"
              :key="tmpl.id"
              type="button"
              class="flex w-full flex-col gap-2 rounded-lg border px-3.5 py-3.5 text-left transition-colors"
              :class="pendingTemplateId === tmpl.id
                ? 'border-primary bg-primary/5'
                : 'border-border bg-card hover:bg-muted/50'"
              @click="requestApplyScriptFlowTemplate(tmpl)"
            >
              <div class="flex items-start justify-between gap-3">
                <span class="text-sm font-semibold text-foreground">{{ tmpl.title }}</span>
                <span
                  class="rounded-md border px-2 py-0.5 text-[10px] font-semibold"
                  :class="pendingTemplateId === tmpl.id
                    ? 'border-primary/30 bg-primary/10 text-primary'
                    : 'border-border bg-muted/40 text-muted-foreground'"
                >
                  {{ pendingTemplateId === tmpl.id ? 'Выбран' : 'Шаблон' }}
                </span>
              </div>
              <span class="text-[11px] leading-snug text-muted-foreground">{{ tmpl.description }}</span>
            </button>
          </div>
          <div v-if="pendingTemplate" class="mt-auto border-t border-border bg-background/95 p-3">
            <p class="text-xs font-semibold text-foreground">Загрузить «{{ pendingTemplate.title }}»?</p>
            <p class="mt-1 text-[11px] leading-snug text-muted-foreground">
              Текущая схема будет полностью заменена выбранным шаблоном.
            </p>
            <div class="mt-3 flex items-center gap-2">
              <button
                type="button"
                class="rounded-md border border-border px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted"
                @click="pendingTemplateId = null"
              >
                Отмена
              </button>
              <button
                type="button"
                class="rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground transition-colors hover:bg-primary/90"
                @click="confirmApplyScriptFlowTemplate"
              >
                Загрузить шаблон
              </button>
            </div>
          </div>
        </div>
      </SheetContent>
    </Sheet>


    <Dialog :open="isCanvasGuideOpen" @update:open="isCanvasGuideOpen = $event">
      <DialogContent class="max-h-[85vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Как заполнять канвас сценария</DialogTitle>
          <DialogDescription>
            Памятка для эксперта: как описывать шаги разговора так, чтобы ассистент звучал по-человечески и вел диалог дальше.
          </DialogDescription>
        </DialogHeader>

        <div class="space-y-5 text-sm leading-6 text-slate-700">
          <section class="space-y-2">
            <h4 class="text-sm font-semibold text-slate-950">Главный принцип</h4>
            <p>
              Канвас - это карта живого разговора, а не справка об услуге. Один шаг = одна понятная ситуация клиента,
              правильная реакция на нее и один следующий шаг диалога.
            </p>
          </section>

          <section class="space-y-2">
            <h4 class="text-sm font-semibold text-slate-950">Что писать в шаге</h4>
            <ul class="list-disc space-y-1 pl-5 marker:text-slate-400">
              <li>когда этот шаг применять;</li>
              <li>что важно понять про клиента в этой ситуации;</li>
              <li>какую главную мысль нужно донести;</li>
              <li>2-4 живые формулировки, которыми это можно сказать;</li>
              <li>каких фраз нельзя использовать;</li>
              <li>какой один вопрос или переход идет дальше.</li>
            </ul>
          </section>

          <section class="space-y-2">
            <h4 class="text-sm font-semibold text-slate-950">Что считается точкой входа в сценарий</h4>
            <p>
              Точка входа - это <span class="font-semibold text-slate-900">trigger-узел</span>. Он отвечает не за основной ответ,
              а за стартовую ситуацию: по каким первым словам клиента должен включиться этот поток.
            </p>
            <ul class="list-disc space-y-1 pl-5 marker:text-slate-400">
              <li>опишите, с каким запросом приходит клиент;</li>
              <li>добавьте типичные фразы клиента;</li>
              <li>укажите, когда этот поток уместен;</li>
              <li>не пишите сюда длинную аргументацию - она должна быть в следующих шагах.</li>
            </ul>
          </section>

          <section class="space-y-2">
            <h4 class="text-sm font-semibold text-slate-950">Как должен звучать текст</h4>
            <ul class="list-disc space-y-1 pl-5 marker:text-slate-400">
              <li>коротко и по-человечески;</li>
              <li>как переписка сильного администратора, а не язык системы;</li>
              <li>без канцелярита, внутренних процессов и объяснений логики маршрутизации;</li>
              <li>с фокусом на конкретную ситуацию клиента, а не на общую лекцию об услуге.</li>
            </ul>
          </section>

          <section class="grid gap-3 sm:grid-cols-2">
            <div class="rounded-xl border border-emerald-200 bg-emerald-50 p-3">
              <p class="text-xs font-bold uppercase tracking-wide text-emerald-700">Хорошо</p>
              <ul class="mt-2 list-disc space-y-1 pl-5 text-[13px] marker:text-emerald-400">
                <li>"Да, конечно, такая процедура у нас есть."</li>
                <li>"Проводим и инъекционную, и безинъекционную биоревитализацию."</li>
                <li>"Чтобы подобрать вариант правильно, врач сначала смотрит состояние кожи."</li>
                <li>"Скажите, вам раньше уже делали такую процедуру?"</li>
              </ul>
            </div>
            <div class="rounded-xl border border-rose-200 bg-rose-50 p-3">
              <p class="text-xs font-bold uppercase tracking-wide text-rose-700">Плохо</p>
              <ul class="mt-2 list-disc space-y-1 pl-5 text-[13px] marker:text-rose-400">
                <li>"В системе вижу несколько позиций."</li>
                <li>"По логике клиники первично проводится консультация."</li>
                <li>"Данная услуга относится к категории."</li>
                <li>"Осуществляется подбор оптимального протокола."</li>
              </ul>
            </div>
          </section>

          <section class="space-y-2">
            <h4 class="text-sm font-semibold text-slate-950">Для question-шага</h4>
            <p>
              Задавайте один понятный вопрос, который реально нужен сейчас. Выберите ожидаемый тип ответа и
              коротко поясните, зачем этот вопрос задается и какой следующий шаг он открывает.
            </p>
          </section>

          <section class="space-y-2">
            <h4 class="text-sm font-semibold text-slate-950">Для expertise-шага</h4>
            <p>
              Опишите конкретную ситуацию клиента, скрытый смысл его запроса, главную тактику ответа и добавьте
              живые примеры формулировок. Не пишите про услугу вообще - пишите реакцию на конкретный момент диалога.
            </p>
          </section>

          <section class="rounded-xl border border-slate-200 bg-slate-50 p-3 text-[13px]">
            <p class="font-semibold text-slate-900">Короткое правило</p>
            <p class="mt-1 text-slate-700">
              Заполняйте канвас так, как будто обучаете сильного менеджера вести переписку с клиентом: одна
              ситуация, одна правильная реакция, один следующий шаг.
            </p>
          </section>
        </div>
      </DialogContent>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, shallowRef, watch, markRaw, nextTick, provide, computed, toRaw, type Ref } from 'vue'
import { onKeyStroke, useDebounceFn, useEventListener } from '@vueuse/core'
import dagre from 'dagre'
import { nanoid } from 'nanoid'
// ── Кастомный DOM-канвас (замена Vue Flow) ─────────────────────────────────
// Ради устранения cold-start лагов и контроля над reactivity hot-path.
// API максимально совместим с useVueFlow через template ref + shim ниже.
import CustomFlow from './canvas/CustomFlow.vue'
import type { NodePosition as XYPosition, EdgeMeta as FlowEdge, NodeMeta } from './canvas/composables/useFlowCanvas'

/** Тип ноды — расширяет NodeMeta из CustomFlow. */
type Node = NodeMeta & { position: XYPosition; type?: string }
type Connection = { source: string; target: string; sourceHandle?: string | null; targetHandle?: string | null }
type EdgeMouseEvent = { edge: FlowEdge; event: MouseEvent | TouchEvent }
/** Шим — старый код на VueFlow ConnectionLineType — теперь это string-перечисление. */
const ConnectionLineType = { Bezier: 'bezier', SmoothStep: 'smoothstep', Straight: 'straight' } as const
import {
  Maximize2,
  ZoomIn,
  ZoomOut,
  Lock,
  Unlock,
  Plus,
  Search,
  FileText,
  Network,
  HelpCircle,
  AlertCircle,
  Sparkles,
} from 'lucide-vue-next'
import ExpertNode from './ExpertNode.vue'
import DedicatedFlowNodes from './nodes/DedicatedFlowNodes.vue'
import TacticLibraryView from './TacticLibraryView.vue'
import ScriptFlowNodeInspector from './ScriptFlowNodeInspector.vue'
import Sheet from '~/components/ui/sheet/Sheet.vue'
import SheetContent from '~/components/ui/sheet/SheetContent.vue'
import SheetTitle from '~/components/ui/sheet/SheetTitle.vue'
import { AGENT_SCRIPT_FLOW_VUE_FLOW_ID } from '~/constants/agentScriptFlow'
import { SCRIPT_FLOW_TEMPLATE_LIST, type ScriptFlowTemplateItem } from '~/constants/scriptFlowTemplates'
import { TEMPLATE_NODE_MOTIVE_BY_NODE_ID } from '~/constants/scriptFlowTemplateMotives'
import { NODE_TYPES } from '~/types/scriptFlow'
import { migrateFlowDefinition, serializeFlowDefinition } from '~/utils/scriptFlowNodeRole'
import { connectionViolatesCatalogPolicy } from '~/utils/scriptFlowEdges'
import { useToast } from '~/composables/useToast'
import { useLayoutState } from '~/composables/useLayoutState'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '~/components/ui/dialog'
import { useScriptFlows } from '~/composables/useScriptFlows'
import { SCRIPT_FLOW_CANVAS_ADAPTER_KEY } from '~/composables/useScriptFlowInspectorModel'

/** Совпадает с подписями в инспекторе (`NODE_TYPES` → «Тип ноды»), чтобы не путать палитру и форму */
const scenarioPalette = computed(() =>
  (['trigger', 'expertise', 'question', 'condition', 'goto', 'end'] as const).map((type) => {
    const meta = NODE_TYPES.find(t => t.value === type)!
    return { type, label: meta.label }
  }),
)

const catalogPalette = computed(() => {
  const meta = NODE_TYPES.find(t => t.value === 'business_rule')!
  return [{ type: 'business_rule' as const, label: meta.label }]
})

const paletteDescription = (nodeType: string) =>
  NODE_TYPES.find((t) => t.value === nodeType)?.description ?? ''


import '@vue-flow/core/dist/style.css'
import '@vue-flow/controls/dist/style.css'
import '@vue-flow/minimap/dist/style.css'

const props = defineProps<{
  revision: number
  flowDefinition: Record<string, unknown>
  viewMode?: 'schema' | 'list'
  varNames?: string[]
  /** Агентские функции (tools) для привязки переменных потока */
  agentFunctions?: Array<{ id: string; name: string; description?: string }>
  /** Переменные потока из flow_metadata.variables */
  flowVariables?: Record<string, unknown>
  serviceOptions?: Array<{ id: string; name: string; is_enabled?: boolean }>
  employeeOptions?: Array<{ id: string; name: string; active?: boolean }>
  kgEntityOptions?: Array<{
    id: string
    name: string
    description?: string | null
    entity_type: string
  }>
  runtimeUsageByNode?: Record<string, {
    node_ref: string
    tactic_title?: string | null
    count: number
    last_invoked_at?: string | null
  }>
}>()

const emit = defineEmits<{
  (e: 'update:flowDefinition', v: Record<string, unknown>): void
  (e: 'update:viewMode', v: 'schema' | 'list'): void
  (e: 'selectNode', id: string | null): void
  /** После большой замены графа (шаблон): родитель делает PATCH сразу, без ожидания debounce автосохранения. */
  (e: 'requestImmediatePersist'): void
  /** Обновление переменных потока из инспектора (сохраняются в flow_metadata) */
  (e: 'update:flowVariables', v: Record<string, unknown>): void
  /** После успешной подстановки шаблона — родитель может засеять мотивы в библиотеке и вернуть привязку. */
  (e: 'template-applied', payload: { templateId: string }): void
}>()

const { scriptFlowToolbarPayload } = useLayoutState()
const route = useRoute()
const agentId = String(route.params.id ?? '')


// ── Canvas wrapper ref (for addNodeAtCenter) ─────────────────────────────────
const canvasWrapperRef = ref<HTMLDivElement | null>(null)

// ── Палитра и экшн-бар ──────────────────────────────────────────────────────
const isPaletteOpen = ref(false)
const isTemplatePickerOpen = ref(false)
const isCanvasGuideOpen = ref(false)
const pendingTemplateId = ref<string | null>(null)
const templatePickerOpenedAtMs = ref<number | null>(null)
const pendingTemplate = computed(() =>
  SCRIPT_FLOW_TEMPLATE_LIST.find(t => t.id === pendingTemplateId.value) ?? null,
)

/**
 * Открываем Sheet с шаблонами на следующий кадр, чтобы избежать конфликта
 * с событием закрытия DropdownMenu (иначе шит может сразу схлопнуться).
 */
const openTemplatePickerFromMenu = () => {
  requestAnimationFrame(() => {
    templatePickerOpenedAtMs.value = Date.now()
    isTemplatePickerOpen.value = true
  })
}

const onTemplatePickerOpenChange = (next: boolean) => {
  if (!next && templatePickerOpenedAtMs.value !== null) {
    const elapsed = Date.now() - templatePickerOpenedAtMs.value
    // Dropdown и Sheet делят один цикл interaction outside — игнорируем "мгновенный" close.
    if (elapsed < 300)
      return
  }
  isTemplatePickerOpen.value = next
  if (!next)
    templatePickerOpenedAtMs.value = null
}

// ── Палитра: единая, открывается из тулбара и по клику + на source-хэндле ────
const paletteSourceNode = ref<{ sourceNodeId: string; sourceHandleId: string } | null>(null)

const openPaletteFromConnector = (nodeId: string, handleId: string) => {
  paletteSourceNode.value = { sourceNodeId: nodeId, sourceHandleId: handleId }
  inspectorNodeId.value = null
  isPaletteOpen.value = true
}

const addNodeFromPalette = (type: string, catalogDrop = false) => {
  const source = paletteSourceNode.value
  if (source) {
    const sourceNode = findNode(source.sourceNodeId)
    const basePos = sourceNode
      ? { x: sourceNode.position.x + 320, y: sourceNode.position.y }
      : project({ x: window.innerWidth / 2, y: window.innerHeight / 2 })
    isPaletteOpen.value = false
    paletteSourceNode.value = null
    const newId = createNodeAtPosition(type, basePos, catalogDrop)
    addEdges([{ id: `e-${source.sourceNodeId}-${newId}`, source: source.sourceNodeId, target: newId, sourceHandle: source.sourceHandleId }])
  }
  else {
    addNodeAtCenter(type, catalogDrop)
    isPaletteOpen.value = false
  }
}

provide('openPaletteFromConnector', openPaletteFromConnector)

// ── Инспектор: открывается как боковой Sheet при выборе узла ─────────────────
const inspectorNodeId = ref<string | null>(null)
/** Подпись сверху инспектора после загрузки готового примера (очищается при смене узла). */
const inspectorTemplateLabel = ref<string | null>(null)
const isInspectorOpen = computed(() => inspectorNodeId.value !== null)
const onInspectorOpenChange = (v: boolean) => {
  if (!v) inspectorNodeId.value = null
  if (v) {
    isPaletteOpen.value = false
    isTemplatePickerOpen.value = false
  }
}

watch(() => props.viewMode, (mode) => {
  if (mode === 'list') {
    inspectorNodeId.value = null
    isPaletteOpen.value = false
    isTemplatePickerOpen.value = false
  }
})

watch(isPaletteOpen, (v) => {
  if (v) {
    inspectorNodeId.value = null
    isTemplatePickerOpen.value = false
  }
  else {
    paletteSourceNode.value = null
  }
})

watch(isTemplatePickerOpen, (v) => {
  if (v) {
    inspectorNodeId.value = null
    isPaletteOpen.value = false
  }
  if (!v)
    pendingTemplateId.value = null
})

watch(isCanvasGuideOpen, (v) => {
  if (v) {
    inspectorNodeId.value = null
    isPaletteOpen.value = false
    isTemplatePickerOpen.value = false
  }
})

watch(inspectorNodeId, (id, prevId) => {
  if (!id) {
    inspectorTemplateLabel.value = null
  }
  else {
    isTemplatePickerOpen.value = false
    isPaletteOpen.value = false
    paletteSourceNode.value = null
  }
  if (prevId && prevId !== id) {
    const prev = findNode(prevId)
    if (prev) removeSelectedNodes([prev])
  }
  if (id) {
    const next = findNode(id)
    if (next && !next.selected) addSelectedNodes([next])
  }
})

// Адаптер канваса для inspector регистрируется ниже, после declaration nodes/edges
// (иначе TDZ на `edges`).

provide('flowVarNames', computed(() => props.varNames ?? []))
provide('flowAgentFunctions', computed(() => props.agentFunctions ?? []))
provide('flowVariables', computed(() => props.flowVariables as Record<string, unknown> | undefined))
provide('onFlowVariablesUpdate', (v: Record<string, unknown>) => emit('update:flowVariables', v))
provide('flowServiceOptions', computed(() => props.serviceOptions ?? []))
provide('flowEmployeeOptions', computed(() => props.employeeOptions ?? []))
provide('flowKgEntityOptions', computed(() => props.kgEntityOptions ?? []))
provide('flowRuntimeUsageByNode', computed(() => props.runtimeUsageByNode ?? {}))

// ── Template ref на CustomFlow + API-shim вместо useVueFlow ─────────────────
// Старый код использовал useVueFlow(...) — деструктуризация даёт прямой доступ
// к API. С CustomFlow тот же API экспонирован через defineExpose. Имеем шим:
const customFlowRef = ref<InstanceType<typeof CustomFlow> | null>(null)

/** project: screen → flow координаты. */
const project = (screen: { x: number; y: number }): XYPosition =>
  customFlowRef.value?.project?.(screen) ?? { x: 0, y: 0 }

/** fitView: подогнать viewport под все ноды (или указанные). */
const fitView = (opts?: { padding?: number; nodes?: { id: string }[]; duration?: number }) => {
  customFlowRef.value?.fitView?.(opts ?? {})
}

/** addEdges: добавить рёбра. С CustomFlow — просто меняем edges.value. */
const addEdges = (newEdges: FlowEdge[]) => {
  edges.value = [...edges.value, ...newEdges]
}

/** findNode: найти ноду по id. */
const findNode = (id: string): Node | null => {
  return customFlowRef.value?.findNode?.(id) ?? null
}

/** viewport как computed для совместимости с {.x .y .zoom}.value. */
const viewport = computed(() => customFlowRef.value?.viewport?.value ?? { x: 0, y: 0, zoom: 1 })

const zoomIn = () => customFlowRef.value?.zoomIn?.()
const zoomOut = () => customFlowRef.value?.zoomOut?.()
const minZoom = computed(() => 0.2)
const maxZoom = computed(() => 2)
/** Стабы для interactivity-замка — в новом канвасе пока всегда interactive. */
const nodesDraggable = ref(true)
const nodesConnectable = ref(true)
const elementsSelectable = ref(true)
const setInteractive = (v: boolean) => {
  nodesDraggable.value = v
  nodesConnectable.value = v
  elementsSelectable.value = v
}
const addSelectedNodes = (nodes: Array<{ id: string }>) =>
  customFlowRef.value?.setSelectedNodes?.(nodes.map(n => n.id))
const removeSelectedNodes = () => customFlowRef.value?.clearSelection?.()

/** onNodesChange / onEdgesChange — стабы. CustomFlow эмитит события напрямую,
 *  а structural-changes detect-аем через @update:nodes/@update:edges. */
type ChangeListener = (...args: unknown[]) => void
const _nodesChangeListeners: ChangeListener[] = []
const _edgesChangeListeners: ChangeListener[] = []
const onNodesChange = (cb: ChangeListener) => { _nodesChangeListeners.push(cb) }
const onEdgesChange = (cb: ChangeListener) => { _edgesChangeListeners.push(cb) }
/** Стаб для prewarm — больше не нужен, CustomFlow не имеет cold-start. */
const onNodesInitialized = (_cb: () => void) => { /* no-op */ }
const updateNodeInternals = (_id: string) => { /* no-op для совместимости */ }
const getNodes = computed(() => nodes.value)

const zoomMaxReached = computed(() => viewport.value.zoom >= maxZoom.value)
const zoomMinReached = computed(() => viewport.value.zoom <= minZoom.value)

const interactionLocked = computed(
  () => !(nodesDraggable.value || nodesConnectable.value || elementsSelectable.value),
)

/** Замок: выкл. интерактив → вкл. обратно (как стандартные Controls Vue Flow). */
const toggleViewportInteraction = () => {
  setInteractive(interactionLocked.value)
}

const { success: toastSuccess } = useToast()

const defaultEdgeOptions = {
  type: 'smoothstep',
  animated: false,
  style: { stroke: 'rgba(99,102,241,0.5)', strokeWidth: 2 },
  labelStyle: { fill: 'hsl(var(--foreground))', fontWeight: 600, fontSize: 11 },
  labelBgStyle: { fill: 'hsl(var(--card))', rx: 6, ry: 6 },
  labelBgPadding: [6, 4] as [number, number],
}

// ── Edge label popup ─────────────────────────────────────────────────────────
const edgeLabelInputRef = ref<HTMLInputElement | null>(null)
const edgeLabelPopup = ref({
  visible: false,
  edgeId: '',
  label: '',
  x: 0,
  y: 0,
})

// All node types use ExpertNode — the visual is differentiated by node.data.node_type
const nodeTypes = {
  expert:   markRaw(ExpertNode),
  trigger:  markRaw(ExpertNode),
  expertise: markRaw(ExpertNode),
  question: markRaw(ExpertNode),
  condition: markRaw(DedicatedFlowNodes),
  goto:     markRaw(DedicatedFlowNodes),
  business_rule: markRaw(DedicatedFlowNodes),
  end:      markRaw(DedicatedFlowNodes),
}

const defaultViewport = { x: 0, y: 0, zoom: 0.8 }
const CONSTRAINT_EDGE_PREFIX = 'cst-'

function isXYPosition(p: unknown): p is XYPosition {
  if (typeof p !== 'object' || p === null) return false
  const o = p as { x?: unknown; y?: unknown }
  return typeof o.x === 'number' && typeof o.y === 'number'
}

function parseFlowNodes(raw: unknown): Node[] {
  if (!Array.isArray(raw)) return []
  const out: Node[] = []
  for (const item of raw) {
    if (typeof item !== 'object' || item === null) continue
    const o = item as Record<string, unknown>
    if (typeof o.id !== 'string' || !isXYPosition(o.position)) continue
    out.push({
      ...item,
      type: o.type || 'expert', // Default to expert type
    } as Node)
  }
  return out
}

function parseFlowEdges(raw: unknown): FlowEdge[] {
  if (!Array.isArray(raw)) return []
  const out: FlowEdge[] = []
  for (const item of raw) {
    if (typeof item !== 'object' || item === null) continue
    const o = item as Record<string, unknown>
    if (typeof o.id !== 'string' || typeof o.source !== 'string' || typeof o.target !== 'string') {
      continue
    }
    // Force bezier curve; strip any stored labels (conditions live on nodes now)
    const { label: _label, ...rest } = item as Record<string, unknown>
    void _label
    const edgeId = typeof o.id === 'string' ? o.id : ''
    if (edgeId.startsWith(CONSTRAINT_EDGE_PREFIX)) continue
    out.push({ ...rest, type: 'smoothstep' } as FlowEdge)
  }
  return out
}

const defaultNodes = (): Node[] => [
  {
    id: 'n1',
    type: 'expert',
    position: { x: 250, y: 150 },
    data: {
      title: NODE_TYPES.find(t => t.value === 'trigger')?.label ?? 'Повод для разговора',
      node_type: 'trigger',
      client_phrase_examples: [],
      keyword_hints: [],
      when_relevant: 'Когда уместен этот поток',
      is_flow_entry: true,
      is_searchable: true,
    },
  },
]

const nodes = ref<Node[]>([])
const edges = ref<FlowEdge[]>([])

// Адаптер канваса для inspector — после nodes/edges declaration чтобы избежать TDZ.
provide(SCRIPT_FLOW_CANVAS_ADAPTER_KEY, {
  findNode: (id: string) => nodes.value.find(n => n.id === id) ?? null,
  updateNodeData: (id: string, dataPatch: Partial<Record<string, unknown>>) => {
    const idx = nodes.value.findIndex(n => n.id === id)
    if (idx < 0) return
    const cur = nodes.value[idx]!
    const newNode = { ...cur, data: { ...((cur as { data?: Record<string, unknown> }).data ?? {}), ...dataPatch } }
    nodes.value = [...nodes.value.slice(0, idx), newNode as Node, ...nodes.value.slice(idx + 1)]
  },
  edges,
})
const selectedId = ref<string | null>(null)
/** Не эмитить flow_definition на родителя пока подтягиваем граф из props (избегаем лишнего PATCH). */
const syncingFromParent = ref(false)

const orphanNodeIds = shallowRef<Set<string>>(new Set())
const _recomputeOrphans = () => {
  const edgeList = edges.value as FlowEdge[]
  const nodeList = nodes.value as Node[]
  const incoming = new Set(edgeList.map(e => String(e.target)))
  const outgoing = new Set(edgeList.map(e => String(e.source)))
  const orphans = new Set<string>()
  for (const n of nodeList) {
    const nid = String(n.id)
    const data = (n.data || {}) as { node_type?: string }
    if (data.node_type === 'trigger') continue
    if (!incoming.has(nid)) orphans.add(nid)
  }
  for (const n of nodeList) {
    const nid = String(n.id)
    const data = (n.data || {}) as { node_type?: string }
    if (data.node_type === 'end' && !outgoing.has(nid)) orphans.add(nid)
  }
  orphanNodeIds.value = orphans
}
watch(() => edges.value.length, _recomputeOrphans, { immediate: true })
watch(() => nodes.value.length, _recomputeOrphans)
provide('flowOrphanNodeIds', orphanNodeIds)

/** Явный тип — иначе TS разворачивает глубокие дженерики `GraphNode` из Vue Flow до ошибки «слишком глубоко». */
type FlowNodeRefOption = { id: string; title: string; node_type: string }

const nodeRefOptions = shallowRef<FlowNodeRefOption[]>([])
const _computeNodeRefOptions = () => {
  nodeRefOptions.value = nodes.value.map((n) => {
    const data = (n.data || {}) as Record<string, unknown>
    const title = typeof data.title === 'string' && data.title.trim() ? data.title : String(n.id)
    const nodeType = typeof data.node_type === 'string' ? data.node_type : String(n.type ?? '')
    return { id: String(n.id), title, node_type: nodeType }
  })
}
_computeNodeRefOptions()
provide('flowNodeRefOptions', nodeRefOptions)

/**
 * Безопасный deep clone:
 * - сначала разворачиваем Vue Proxy через toRaw, иначе structuredClone может упасть
 *   на reactive-объекте (см. ошибку "#<Object> could not be cloned");
 * - structuredClone пробуем в try/catch, чтобы любая некруглая/несериализуемая ветка
 *   (Symbol, функции, getters в data ноды) не ломала всю гидратацию канваса —
 *   иначе при `syncFromProps` ловим throw, nodes остаются пустыми, и пользователь
 *   видит «пустой» канвас после перезагрузки, хотя в БД всё лежит.
 */
const deepClone = <T,>(x: T): T => {
  const source = (x && typeof x === 'object' ? toRaw(x as object) : x) as T
  if (typeof structuredClone === 'function') {
    try {
      return structuredClone(source)
    }
    catch {
      /* fallthrough на JSON */
    }
  }
  try {
    return JSON.parse(JSON.stringify(source)) as T
  }
  catch {
    return source
  }
}

const syncFromProps = () => {
  syncingFromParent.value = true
  /**
   * Гидратация канваса из props.flowDefinition.
   * Любая ошибка тут приводила к «пустому» канвасу после reload (на самом деле
   * данные в БД сохранены, но клонирование падало на reactive Proxy/несериализуемых
   * полях VueFlow — handleBounds, dimensions и т.д.). Поэтому каждая ветка обёрнута
   * в try/catch + есть fallback на сырой массив без deepClone.
   */
  try {
    const rawDef = toRaw((props.flowDefinition || {}) as Record<string, unknown>)
    const cloned = (() => {
      try { return deepClone(rawDef) }
      catch { return rawDef }
    })()
    const d = migrateFlowDefinition(cloned)
    const rawNodes = Array.isArray(d.nodes) ? d.nodes : []
    const rawEdges = Array.isArray(d.edges) ? d.edges : []
    const nodesForParse = (() => {
      try { return deepClone(rawNodes) }
      catch { return rawNodes }
    })()
    const edgesForParse = (() => {
      try { return deepClone(rawEdges) }
      catch { return rawEdges }
    })()
    const parsedNodes = parseFlowNodes(nodesForParse)
    nodes.value = parsedNodes.length > 0 ? parsedNodes : defaultNodes()
    edges.value = parseFlowEdges(edgesForParse)
  }
  catch (e) {
    console.error('[ScriptFlowEditor] syncFromProps failed; keeping previous canvas', e)
    if (nodes.value.length === 0) nodes.value = defaultNodes()
  }
  nextTick(() => {
    nextTick(() => {
      syncingFromParent.value = false
    })
  })
}

const hasAutoOpenedGuide = ref(false)

watch(
  () => [scriptFlowToolbarPayload.value?.flow?.id, props.flowDefinition] as const,
  ([flowId, flowDefinition]) => {
    if (hasAutoOpenedGuide.value) return
    if (!flowId || typeof window === 'undefined') return
    const fd = (flowDefinition || {}) as Record<string, unknown>
    const rawNodes = Array.isArray(fd.nodes) ? fd.nodes : []
    const rawEdges = Array.isArray(fd.edges) ? fd.edges : []
    const isEmptyFlow = rawNodes.length === 0 && rawEdges.length === 0
    if (!isEmptyFlow) return
    const storageKey = `script-flow-guide-opened:${String(flowId)}`
    if (window.sessionStorage.getItem(storageKey) === '1') {
      hasAutoOpenedGuide.value = true
      return
    }
    window.sessionStorage.setItem(storageKey, '1')
    hasAutoOpenedGuide.value = true
    isCanvasGuideOpen.value = true
  },
  { immediate: true, deep: true },
)

const nodesWithoutUiState = (): Node[] =>
  nodes.value.map((n) => {
    const { selected: _sel, ...rest } = n as Node & { selected?: boolean }
    void _sel
    return { ...rest } as Node
  })

const cloneGraph = (): { nodes: Node[]; edges: FlowEdge[] } => ({
  nodes: deepClone(nodesWithoutUiState()),
  edges: deepClone(
    edges.value.filter((e) => !String(e.id || '').startsWith(CONSTRAINT_EDGE_PREFIX)),
  ),
})

const historyStates = ref<Array<{ nodes: Node[]; edges: FlowEdge[] }>>([])
const historyPtr = ref(-1)

/** Кэш id нод, layout/reactive-state которых уже прогреты — каждая нода прогревается один раз. */
const _prewarmedNodeIds = new Set<string>()

/**
 * Pre-warm layout + Vue Flow reactive caches.
 *
 * Пользовательское наблюдение: первый драг ноды лагает, второй+ — плавный.
 * Причина: Vue Flow создаёт reactive Proxy для `position.x/y`, `dimensions`,
 * `computedPosition`, `handleBounds` ЛЕНИВО — на первое JS-обращение. В первый
 * mousemove одновременно создаются прокси, меряются handle bounds и стартует
 * drag-pipeline → лаг. Прогрев убирает эту работу из горячего пути.
 */
const prewarmLayout = () => {
  if (typeof document === 'undefined') return

  const all = getNodes.value

  // 1) DOM layout warm-up для НОВЫХ нод (тех, что ещё не прогревались).
  for (const n of all) {
    if (_prewarmedNodeIds.has(n.id)) continue
    const el = document.querySelector<HTMLElement>(`.vue-flow__node[data-id="${n.id}"]`)
    if (el) {
      void el.offsetHeight
      el.querySelectorAll<HTMLElement>('.vue-flow__handle').forEach((h) => { void h.offsetHeight })
    }
    // 2) Vue Flow reactive proxies warm-up: создать Proxy заранее.
    void n.position?.x
    void n.position?.y
    void (n as { dimensions?: { width: number; height: number } }).dimensions?.width
    void (n as { dimensions?: { width: number; height: number } }).dimensions?.height
    void (n as { computedPosition?: { x: number; y: number } }).computedPosition?.x
    void (n as { computedPosition?: { x: number; y: number } }).computedPosition?.y
    // 3) Принудительно пересчитать handle bounds через Vue Flow API.
    try { updateNodeInternals(n.id) }
    catch { /* нода может ещё не быть в DOM */ }
    _prewarmedNodeIds.add(n.id)
  }
}

watch(
  () => props.revision,
  () => {
    syncFromProps()
    // Сбрасываем кэш прогретых нод — при revision change набор нод мог измениться
    _prewarmedNodeIds.clear()
    nextTick(() => {
      nextTick(() => {
        try {
          fitView({ padding: 0.15, duration: 0 })
        }
        catch {
          /* Vue Flow ещё не смонтирован в первом кадре */
        }
        // Прогрев теперь происходит через onNodesInitialized — официальный
        // Vue Flow event «все ноды измерены и готовы».
        historyStates.value = [cloneGraph()]
        historyPtr.value = 0
      })
    })
  },
  { immediate: true },
)

const pushEmit = () => {
  const vpLive = viewport.value as { x: number; y: number; zoom: number } | undefined
  const vp = vpLive && typeof vpLive.x === 'number' && typeof vpLive.zoom === 'number'
    ? { x: vpLive.x, y: vpLive.y, zoom: vpLive.zoom }
    : ((props.flowDefinition.viewport as Record<string, unknown>) || defaultViewport)
  emit(
    'update:flowDefinition',
    serializeFlowDefinition({
      nodes: nodesWithoutUiState(),
      edges: edges.value.filter((e) => !String(e.id || '').startsWith(CONSTRAINT_EDGE_PREFIX)),
      viewport: vp as Record<string, unknown>,
    }),
  )
}

const emitViewportDebounced = useDebounceFn(() => {
  if (syncingFromParent.value) return
  pushEmit()
}, 400)

const debouncedPushDefinition = useDebounceFn(() => {
  if (syncingFromParent.value) return
  pushEmit()
}, 140)

const requestImmediatePersist = () => {
  emit('requestImmediatePersist')
}

const isDraggingNode = ref(false)
provide('isDraggingNode', isDraggingNode)

/**
 * Per-node флаг: id ноды, которую В ДАННЫЙ МОМЕНТ тащат (или null).
 * В отличие от CSS-класса `.dragging` (он добавляется на mousedown — даже без движения,
 * из-за чего пропадал контент при клике), `draggingNodeId` устанавливается только когда
 * Vue Flow эмитит JS-событие `onNodeDragStart` — то есть при ФАКТИЧЕСКОМ драге.
 * Используется в condition-карточках чтобы прятать тяжёлые inline-ветки только
 * на время реального драга именно этой ноды.
 */
const draggingNodeId = ref<string | null>(null)
provide('draggingNodeId', draggingNodeId)

/**
 * Реактивность ТОЛЬКО на меняющиеся события — position-events игнорируем
 * (они летят сотнями за drag-кадр, и это было главной причиной лагов).
 * Vue Flow посылает явные change-types: position | dimensions | add | remove | replace | select | data
 */
const NON_POSITION_NODE_CHANGE = (t: string) => t !== 'position' && t !== 'select' && t !== 'dimensions'

onNodesChange((changes) => {
  if (isDraggingNode.value) return
  const meaningful = changes.some(c => NON_POSITION_NODE_CHANGE(String(c.type ?? '')))
  if (!meaningful) return
  _computeNodeRefOptions()
  debouncedPushDefinition()
  debouncedRecordHistory()
})

onEdgesChange((changes) => {
  if (isDraggingNode.value) return
  const meaningful = changes.some(c => c.type !== 'select')
  if (!meaningful) return
  debouncedPushDefinition()
  debouncedRecordHistory()
})

/**
 * Pre-warm: при ПЕРВОМ hover на ноду прогреваем её layout И Vue Flow reactive state.
 * Кэшируем по id (см. _prewarmedNodeIds) — каждая нода прогревается ОДИН РАЗ,
 * иначе движение мыши по канвасу триггерит layout flush на каждый mouse-enter.
 */
const onNodeMouseEnter = (evt: { node?: { id: string } }) => {
  const id = evt.node?.id
  if (!id || _prewarmedNodeIds.has(id)) return
  _prewarmedNodeIds.add(id)

  // 1) DOM layout warm-up для ноды и её handles
  if (typeof document !== 'undefined') {
    const nodeEl = document.querySelector<HTMLElement>(`.vue-flow__node[data-id="${id}"]`)
    if (nodeEl) {
      void nodeEl.offsetHeight
      nodeEl.querySelectorAll<HTMLElement>('.vue-flow__handle').forEach((h) => {
        void h.offsetHeight
      })
    }
  }

  // 2) Vue Flow reactive proxies warm-up: создаст Proxy для свойств ноды
  const node = findNode(id)
  if (node) {
    void node.position?.x
    void node.position?.y
    void (node as { dimensions?: { width: number } }).dimensions?.width
    void (node as { computedPosition?: { x: number } }).computedPosition?.x
  }

  // 3) Force-кэш внутренних bounds Vue Flow для этой конкретной ноды
  try { updateNodeInternals(id) }
  catch { /* ignore */ }
}

const onNodeDragStart = (evt: { node?: { id: string } }) => {
  isDraggingNode.value = true
  draggingNodeId.value = evt.node?.id ?? null
}
const onNodeDragStop = () => {
  isDraggingNode.value = false
  draggingNodeId.value = null
  // Только сейчас position изменилась окончательно — единственный момент сохранения после drag.
  debouncedPushDefinition()
  debouncedRecordHistory()
}

watch(
  () => [viewport.value.x, viewport.value.y, viewport.value.zoom] as const,
  () => {
    emitViewportDebounced()
  },
)

const nodeSearchOpen = ref(false)
const nodeSearchQuery = ref('')
const nodeSearchInputRef = ref<HTMLInputElement | null>(null)

const filteredSearchNodes = shallowRef<{ id: string; title: string; sub: string }[]>([])
const _runFilteredSearch = () => {
  const q = nodeSearchQuery.value.trim().toLowerCase()
  const out: { id: string; title: string; sub: string }[] = []
  for (const n of nodes.value) {
    const data = (n.data || {}) as Record<string, unknown>
    const title = String(data.title ?? data.label ?? n.id)
    const situation = String(data.situation ?? '')
    const whenRel = String(data.when_relevant ?? '')
    const phrases = Array.isArray(data.client_phrase_examples)
      ? (data.client_phrase_examples as string[]).join(' ')
      : ''
    const routeHint = String(data.routing_hint ?? '')
    const gq = String(data.good_question ?? '')
    const hay = `${title} ${situation} ${whenRel} ${phrases} ${routeHint} ${gq}`.toLowerCase()
    if (q && !hay.includes(q))
      continue
    out.push({ id: String(n.id), title: title || String(n.id), sub: situation || gq || '' })
  }
  filteredSearchNodes.value = out.slice(0, 40)
}
const debouncedRunFilteredSearch = useDebounceFn(_runFilteredSearch, 200)
watch(nodeSearchQuery, debouncedRunFilteredSearch)
watch(nodeSearchOpen, (open) => { if (open) _runFilteredSearch() })

/** Выделить узел, открыть инспектор, подскроллить вид к узлу (из диалога «Готовность» и поиска). */
const focusCanvasNode = (id: string): boolean => {
  if (!findNode(id))
    return false
  inspectorNodeId.value = id
  emit('selectNode', id)
  nextTick(() => {
    try {
      fitView({ nodes: [id], padding: 0.35, duration: 350 })
    }
    catch {
      /* ignore */
    }
  })
  return true
}

const focusSearchNode = (id: string) => {
  nodeSearchOpen.value = false
  nodeSearchQuery.value = ''
  focusCanvasNode(id)
}

useEventListener(window, 'keydown', (e: KeyboardEvent) => {
  if (!(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== 'k')
    return
  const t = e.target as HTMLElement | null
  if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable))
    return
  e.preventDefault()
  nodeSearchOpen.value = true
  nextTick(() => nodeSearchInputRef.value?.focus())
})

/** Undo / redo (Ctrl+Z / Ctrl+Shift+Z) */
const MAX_HISTORY = 40

const applySnapshot = (snap: { nodes: Node[]; edges: FlowEdge[] }) => {
  syncingFromParent.value = true
  nodes.value = deepClone(snap.nodes)
  edges.value = deepClone(snap.edges)
  nextTick(() => {
    nextTick(() => {
      syncingFromParent.value = false
    })
  })
}

const recordHistory = () => {
  if (syncingFromParent.value) return
  const snap = cloneGraph()
  const states = historyStates.value.slice(0, historyPtr.value + 1)
  const last = states[states.length - 1]
  if (last && JSON.stringify(last) === JSON.stringify(snap))
    return
  states.push(snap)
  historyStates.value = states.length > MAX_HISTORY ? states.slice(-MAX_HISTORY) : states
  historyPtr.value = historyStates.value.length - 1
}

const debouncedRecordHistory = useDebounceFn(recordHistory, 400)


if (import.meta.client) {
  useEventListener(window, 'keydown', (e: KeyboardEvent) => {
    if (!(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== 'z')
      return
    const t = e.target as HTMLElement | null
    if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable))
      return
    e.preventDefault()
    if (e.shiftKey) {
      if (historyPtr.value >= historyStates.value.length - 1) return
      historyPtr.value += 1
      const snap = historyStates.value[historyPtr.value]
      if (snap)
        applySnapshot(deepClone(snap))
    }
    else {
      if (historyPtr.value <= 0) return
      historyPtr.value -= 1
      const snap = historyStates.value[historyPtr.value]
      if (snap)
        applySnapshot(deepClone(snap))
    }
  })
}

// ── Connect handler ───────────────────────────────────────────────────────────
const onConnect = (connection: Connection) => {
  const src = findNode(connection.source)
  const tgt = findNode(connection.target)
  if (connectionViolatesCatalogPolicy(src, tgt))
    return

  const newEdge: FlowEdge = {
    id: `e-${connection.source}-${connection.target}-${Date.now()}`,
    source: connection.source,
    target: connection.target,
    sourceHandle: connection.sourceHandle ?? undefined,
    targetHandle: connection.targetHandle ?? undefined,
    ...defaultEdgeOptions,
  }
  addEdges([newEdge])
  requestImmediatePersist()
}

const onNodeClick = (evt: { node?: { id: string } }) => {
  const id = evt.node?.id ?? null
  selectedId.value = id
  closeEdgeLabelPopup()
  emit('selectNode', id)
}

const onNodeDblClick = (evt: { node?: { id: string } }) => {
  const id = evt.node?.id ?? null
  if (!id) return
  selectedId.value = id
  inspectorNodeId.value = id
  emit('selectNode', id)
}

const onEdgeClick = ({ edge, event }: EdgeMouseEvent) => {
  const clientX = event instanceof MouseEvent ? event.clientX : (event as TouchEvent).touches[0]?.clientX ?? 0
  const clientY = event instanceof MouseEvent ? event.clientY : (event as TouchEvent).touches[0]?.clientY ?? 0
  openEdgeLabelPopup(edge.id, '', clientX - 80, clientY + 10)
}

const onPaneClick = () => {
  selectedId.value = null
  inspectorNodeId.value = null
  closeEdgeLabelPopup()
  emit('selectNode', null)
}

const openEdgeLabelPopup = (edgeId: string, label: string, x: number, y: number) => {
  edgeLabelPopup.value = { visible: true, edgeId, label, x, y }
  nextTick(() => edgeLabelInputRef.value?.focus())
}

const closeEdgeLabelPopup = () => {
  edgeLabelPopup.value.visible = false
}

const deleteSelectedEdge = () => {
  const { edgeId } = edgeLabelPopup.value
  if (String(edgeId || '').startsWith(CONSTRAINT_EDGE_PREFIX)) {
    closeEdgeLabelPopup()
    return
  }
  edges.value = edges.value.filter(e => e.id !== edgeId)
  closeEdgeLabelPopup()
  requestImmediatePersist()
}

const removeCanvasEdge = (edgeId: string) => {
  if (!edgeId || String(edgeId).startsWith(CONSTRAINT_EDGE_PREFIX))
    return
  edges.value = edges.value.filter(e => e.id !== edgeId)
  closeEdgeLabelPopup()
  requestImmediatePersist()
}

const addCanvasConnectionFromInspector = (targetNodeId: string) => {
  const sourceNodeId = String(inspectorNodeId.value ?? '').trim()
  const targetId = String(targetNodeId ?? '').trim()
  if (!sourceNodeId || !targetId || sourceNodeId === targetId)
    return

  const src = findNode(sourceNodeId)
  const tgt = findNode(targetId)
  if (!src || !tgt)
    return
  if (connectionViolatesCatalogPolicy(src, tgt))
    return

  const alreadyExists = edges.value.some(e =>
    String(e.source ?? '') === sourceNodeId
    && String(e.target ?? '') === targetId
    && !String(e.sourceHandle ?? '').startsWith('branch:'),
  )
  if (alreadyExists)
    return

  const newEdge: FlowEdge = {
    id: `e-${sourceNodeId}-${targetId}-${Date.now()}`,
    source: sourceNodeId,
    target: targetId,
    ...defaultEdgeOptions,
  }
  addEdges([newEdge])
  requestImmediatePersist()
  focusCanvasNode(targetId)
}

const onPaletteDragStart = (event: DragEvent, type: string, catalogDrop: boolean) => {
  event.dataTransfer?.setData('application/vueflow', type)
  event.dataTransfer?.setData('application/catalog', catalogDrop ? '1' : '0')
  event.dataTransfer!.effectAllowed = 'move'
}

const addNodeAtCenter = (type: string, catalogDrop: boolean = false) => {
  const wrapper = canvasWrapperRef.value
  const rect = wrapper?.getBoundingClientRect()
  const cx = rect ? rect.left + rect.width / 2 : window.innerWidth / 2
  const cy = rect ? rect.top + rect.height / 2 : window.innerHeight / 2
  const position = project({ x: cx, y: cy })
  createNodeAtPosition(type, position, catalogDrop)
}

if (import.meta.client) {
  onKeyStroke(['Delete', 'Backspace'], (ev) => {
    const el = document.activeElement as HTMLElement | null
    if (
      el
      && (el.tagName === 'INPUT'
        || el.tagName === 'TEXTAREA'
        || el.tagName === 'SELECT'
        || el.isContentEditable)
    ) {
      return
    }
    if (edgeLabelPopup.value.visible) {
      deleteSelectedEdge()
      return
    }
    if (inspectorNodeId.value) {
      const rm = inspectorNodeId.value
      nodes.value = nodes.value.filter(n => String(n.id) !== rm)
      inspectorNodeId.value = null
      emit('selectNode', null)
      requestImmediatePersist()
      toastSuccess('Узел удалён')
    }
  })
}

if (import.meta.client) {
  useEventListener(window, 'keydown', (e: KeyboardEvent) => {
    if (!(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== 'd')
      return
    const t = e.target as HTMLElement | null
    if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable))
      return
    if (!inspectorNodeId.value)
      return
    e.preventDefault()
    const cur = inspectorNodeId.value
    const src = nodes.value.find(n => String(n.id) === cur)
    if (!src)
      return
    const newId = nanoid()
    const copy = deepClone(src) as Node
    copy.id = newId
    copy.position = { x: src.position.x + 40, y: src.position.y + 40 }
    if (copy.data && typeof copy.data === 'object')
      (copy.data as Record<string, unknown>).title = `${(copy.data as Record<string, unknown>).title || 'Узел'} (копия)`
    nodes.value = [...nodes.value, copy]
    inspectorNodeId.value = newId
    emit('selectNode', newId)
    requestImmediatePersist()
  })
}

const resetView = () => {
  fitView()
}

const requestApplyScriptFlowTemplate = (tmpl: ScriptFlowTemplateItem) => {
  pendingTemplateId.value = tmpl.id
}

const confirmApplyScriptFlowTemplate = () => {
  const tmpl = pendingTemplate.value
  if (!tmpl)
    return

  pendingTemplateId.value = null
  syncingFromParent.value = true
  const d = migrateFlowDefinition(deepClone(tmpl.definition as Record<string, unknown>))
  nodes.value = parseFlowNodes(Array.isArray(d.nodes) ? deepClone(d.nodes) : [])
  edges.value = parseFlowEdges(Array.isArray(d.edges) ? deepClone(d.edges) : [])
  nextTick(() => {
    nextTick(() => {
      syncingFromParent.value = false
      pushEmit()
      requestImmediatePersist()
      try {
        fitView({ padding: 0.12, duration: 400 })
      }
      catch {
        /* Vue Flow может быть ещё не готов */
      }
      historyStates.value = [cloneGraph()]
      historyPtr.value = 0
      inspectorTemplateLabel.value = tmpl.title
      inspectorNodeId.value = tmpl.entryNodeId
      emit('selectNode', tmpl.entryNodeId)
      isTemplatePickerOpen.value = false
      toastSuccess(`Загружен шаблон «${tmpl.title}»`)
      emit('template-applied', { templateId: tmpl.id })
    })
  })
}

/** Подставить id мотивов в узлы текущего графа по карте шаблона (имя мотива lower-case → uuid). */
const applyTemplateKgLinks = (templateId: string, motiveNameLcToId: Record<string, string>) => {
  const bindings = TEMPLATE_NODE_MOTIVE_BY_NODE_ID[templateId]
  if (!bindings || !Object.keys(motiveNameLcToId).length)
    return
  let changed = false
  nodes.value = nodes.value.map((n) => {
    const motiveName = bindings[String(n.id)]
    if (!motiveName)
      return n
    const mid = motiveNameLcToId[motiveName.trim().toLowerCase()]
    if (!mid)
      return n
    const raw = (n.data && typeof n.data === 'object') ? n.data as Record<string, unknown> : {}
    const prevLinks = (raw.kg_links && typeof raw.kg_links === 'object')
      ? raw.kg_links as Record<string, unknown>
      : {}
    const prevMotives = Array.isArray(prevLinks.motive_ids)
      ? [...prevLinks.motive_ids as string[]]
      : []
    if (prevMotives.includes(mid))
      return n
    changed = true
    return {
      ...n,
      data: {
        ...raw,
        kg_links: {
          ...prevLinks,
          motive_ids: [...prevMotives, mid],
        },
      },
    }
  })
  if (!changed)
    return
  nextTick(() => {
    pushEmit()
    requestImmediatePersist()
  })
}

const runAutoLayout = () => {
  if (!nodes.value.length)
    return
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: 'LR', ranksep: 120, nodesep: 80, marginx: 40, marginy: 40 })
  const nw = 300
  const nh = 180
  for (const n of nodes.value)
    g.setNode(n.id, { width: nw, height: nh })
  for (const e of edges.value) {
    if (String(e.id || '').startsWith(CONSTRAINT_EDGE_PREFIX))
      continue
    g.setEdge(e.source, e.target)
  }
  dagre.layout(g)
  nodes.value = nodes.value.map((n) => {
    const pos = g.node(n.id)
    const x = pos ? pos.x - nw / 2 : n.position.x
    const y = pos ? pos.y - nh / 2 : n.position.y
    return { ...n, position: { x, y } }
  })
  // Position-changes больше не реактивны → явный save после layout
  debouncedPushDefinition()
  debouncedRecordHistory()
  nextTick(() => {
    try {
      fitView({ padding: 0.2, duration: 350 })
    }
    catch {
      /* ignore */
    }
  })
}

// Drag and Drop Logic
const onDragOver = (event: DragEvent) => {
  event.preventDefault()
  if (event.dataTransfer) {
    event.dataTransfer.dropEffect = 'move'
  }
}

const createNodeAtPosition = (type: string, position: XYPosition, catalogDrop: boolean): string => {
  const id = nanoid()
  const meta = NODE_TYPES.find(t => t.value === type)
  const commonTitle = meta?.label ?? 'Новый узел'
  const entrySearchable = type === 'trigger' || type === 'expertise' || type === 'question'
  let dropData: Record<string, unknown> = {
    title: commonTitle,
    node_type: type,
  }
  if (type === 'trigger') {
    dropData = { ...dropData, client_phrase_examples: [], keyword_hints: [], when_relevant: '', is_flow_entry: true, is_searchable: true }
  }
  else if (type === 'expertise') {
    dropData = { ...dropData, situation: '', example_phrases: [], is_searchable: true }
  }
  else if (type === 'question') {
    dropData = { ...dropData, good_question: '', alternative_phrasings: [], expected_answer_type: 'open', why_we_ask: '', stage: null, level: 1, service_ids: [], employee_ids: [], is_searchable: true, kg_links: {}, conditions: [] }
  }
  else if (type === 'condition') {
    dropData = { ...dropData, routing_hint: '', conditions: [] }
  }
  else if (type === 'goto') {
    dropData = { ...dropData, target_flow_id: '', target_node_ref: null, transition_phrase: '', trigger_situation: '' }
  }
  else if (type === 'end') {
    dropData = { ...dropData, outcome_type: null, final_action: '', kg_links: {} }
  }
  else if (type === 'business_rule') {
    dropData = {
      ...dropData,
      situation: '',
      is_catalog_rule: catalogDrop,
      rule_condition: '',
      rule_action: '',
      rule_priority: 100,
      rule_active: true,
      service_ids: [],
      employee_ids: [],
      data_source: 'sqns_resources',
      entity_type: 'employee',
      entity_id: '',
      constraints: { requires_entity: 'none', must_follow_node_refs: [] },
    }
  }
  else {
    dropData = { ...dropData, situation: '', ...(entrySearchable ? { is_searchable: true } : {}), ...(type === 'trigger' ? { is_flow_entry: true } : {}) }
  }
  const newNode: Node = { id, type: 'expert', position, data: dropData }
  nodes.value = [...nodes.value, newNode]
  isPaletteOpen.value = false
  inspectorNodeId.value = id
  requestImmediatePersist()
  return id
}

const onDrop = (event: DragEvent) => {
  const type = event.dataTransfer?.getData('application/vueflow')
  if (!type) return
  const catalogDrop = event.dataTransfer?.getData('application/catalog') === '1'
  const position = project({ x: event.clientX - 40, y: event.clientY - 40 })
  createNodeAtPosition(type, position, catalogDrop)
}

/** Drop из CustomFlow — позиция уже в координатах канваса. */
const onCustomFlowDrop = (event: DragEvent, projected: XYPosition) => {
  const type = event.dataTransfer?.getData('application/vueflow')
  if (!type) return
  const catalogDrop = event.dataTransfer?.getData('application/catalog') === '1'
  createNodeAtPosition(type, projected, catalogDrop)
}

defineExpose({
  selectedId,
  nodes,
  edges,
  /** Сразу отправить актуальные nodes/edges/viewport на родителя (обходит debounce 140ms перед PATCH). */
  flushFlowDefinitionToParent: () => {
    if (syncingFromParent.value) return
    pushEmit()
  },
  /** Показать узел на канвасе и открыть инспектор (false — узла с таким id нет). */
  focusCanvasNode,
  /** После засева мотивов в библиотеке — привязать их к узлам шаблона по имени. */
  applyTemplateKgLinks,
})
</script>

<style>
/* All custom node types share the same transparent wrapper */
.vue-flow__node-expert,
.vue-flow__node-trigger,
.vue-flow__node-expertise,
.vue-flow__node-question,
.vue-flow__node-condition,
.vue-flow__node-goto,
.vue-flow__node-business_rule,
.vue-flow__node-end {
  background: transparent !important;
  border: none !important;
  padding: 0 !important;
}

.script-flow-canvas {
  background-image:
    radial-gradient(circle at top left, rgba(99, 102, 241, 0.12), transparent 28%),
    radial-gradient(circle at 85% 18%, rgba(168, 85, 247, 0.08), transparent 22%),
    radial-gradient(circle at bottom right, rgba(14, 165, 233, 0.10), transparent 24%),
    linear-gradient(180deg, rgba(255,255,255,0.72), rgba(248,250,252,0.94));
  background-color: #f8fafc;
}

.script-flow-canvas::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    linear-gradient(180deg, rgba(255,255,255,0.24), transparent 18%),
    radial-gradient(circle at center, transparent 58%, rgba(15, 23, 42, 0.04) 100%);
}

.vue-flow__pane {
  cursor: grab;
}

.vue-flow__pane:active {
  cursor: grabbing;
}

/* GPU-слой только на тащимой ноде, не на всех 30+. */
.vue-flow__node.dragging {
  will-change: transform;
}

/* Во время drag отключаем pointer-events на остальных, чтобы не было hit-test работы. */
.script-flow-canvas.is-dragging .vue-flow__node:not(.dragging) {
  pointer-events: none !important;
}

.vue-flow__handle {
  height: 12px !important;
  width: 12px !important;
  border: 2px solid white !important;
  background: #6366f1 !important;
  box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.10) !important;
}

.vue-flow__handle:hover {
  box-shadow: 0 0 0 6px rgba(99, 102, 241, 0.16) !important;
}

.vue-flow__edge-path {
  stroke: rgba(99, 102, 241, 0.44) !important;
  stroke-width: 3px !important;
  stroke-linecap: round !important;
  stroke-linejoin: round !important;
}

.vue-flow__edge.selected .vue-flow__edge-path,
.vue-flow__edge:hover .vue-flow__edge-path {
  stroke: rgba(79, 70, 229, 0.82) !important;
  stroke-width: 3.5px !important;
}

.vue-flow__edge-textbg {
  fill: rgba(255, 255, 255, 0.92) !important;
  stroke: rgba(148, 163, 184, 0.35) !important;
  stroke-width: 1px !important;
}

.vue-flow__edge-text {
  fill: #334155 !important;
  font-weight: 600 !important;
}

.vue-flow__controls-button {
  border-radius: 12px !important;
  border: 1px solid rgba(226, 232, 240, 0.92) !important;
  background: rgba(255, 255, 255, 0.88) !important;
  color: #0f172a !important;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.10) !important;
  backdrop-filter: blur(10px) !important;
  transition: all 0.2s ease !important;
}

.vue-flow__controls-button:hover {
  background: #f1f5f9 !important;
  transform: scale(1.05);
}

.vue-flow__controls-button:active {
  transform: scale(0.95);
}

.vue-flow__minimap {
  position: static !important;
  border: none !important;
  background: linear-gradient(180deg, rgba(255,255,255,0.72), rgba(248,250,252,0.92)) !important;
  backdrop-filter: none !important;
  box-shadow: none !important;
}

.vue-flow__minimap-mask {
  fill: rgba(99, 102, 241, 0.09) !important;
}

/* Ряд Zoom рядом с миникартой: без «ступеней» как у вертикального столбца */
.script-flow-zoom-controls .vue-flow__controls-button {
  border-radius: 0 !important;
  box-shadow: none !important;
  border-right: 1px solid #e2e8f0 !important;
  border-bottom: none !important;
}

.script-flow-zoom-controls .vue-flow__controls-button:last-child {
  border-right: none !important;
}

.script-flow-zoom-controls .vue-flow__controls-button:hover {
  transform: none !important;
}

.vue-flow__selection {
  border: 1px dashed rgba(99, 102, 241, 0.45) !important;
  background: rgba(99, 102, 241, 0.06) !important;
}
</style>
