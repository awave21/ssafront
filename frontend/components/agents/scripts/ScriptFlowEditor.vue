<template>
  <div class="flex h-full min-h-0 w-full flex-row overflow-hidden bg-background">
    <div
      class="relative min-h-0 min-w-0 flex-1"
      @drop="onDrop"
      @dragover="onDragOver"
    >
      <VueFlow
        :id="AGENT_SCRIPT_FLOW_VUE_FLOW_ID"
        v-model:nodes="nodes"
        v-model:edges="edges"
        :default-viewport="defaultViewport"
        :snap-to-grid="true"
        :snap-grid="[16, 16]"
        :connect-on-click="false"
        :default-edge-options="defaultEdgeOptions"
        :connection-line-type="ConnectionLineType.Bezier"
        :connection-line-style="{ stroke: '#6366f1', strokeWidth: 2, strokeDasharray: '6 3' }"
        class="script-flow-canvas h-full w-full bg-slate-50/70"
        :node-types="nodeTypes"
        @connect="onConnect"
        @node-click="onNodeClick"
        @edge-click="onEdgeClick"
        @pane-click="onPaneClick"
      >
        <Background v-if="viewMode === 'schema'" :gap="24" pattern-color="#cbd5e1" :size="1" />

        <Panel
          v-if="viewMode === 'schema'"
          position="top-left"
          class="pointer-events-none !m-4 max-w-sm"
        >
          <div class="rounded-2xl border border-border/70 bg-background/92 px-4 py-3 shadow-xl backdrop-blur-md">
            <p class="text-[10px] font-bold uppercase tracking-[0.18em] text-muted-foreground">Карта разговора</p>
            <p class="mt-1 text-sm font-semibold text-foreground">Собирайте сценарий как цепочку понятных шагов</p>
            <p class="mt-1.5 text-[11px] leading-relaxed text-muted-foreground">
              Перетаскивайте карточки на холст, соединяйте их плавными линиями и редактируйте текст справа.
            </p>
          </div>
        </Panel>

        <!-- Мини-карта и зум (+ / − / весь граф / замок) — в один ряд -->
        <Panel
          v-if="viewMode === 'schema'"
          position="bottom-left"
          class="script-flow-map-controls pointer-events-none !m-4 flex flex-row items-end gap-3"
        >
          <div class="pointer-events-auto shrink-0 overflow-hidden rounded-lg border border-border bg-card/90 shadow-lg">
            <MiniMap
              class="!static !m-0"
              style="width: 160px; height: 120px;"
              :mask-color="'rgba(0,0,0,0.12)'"
              pannable
              zoomable
            />
          </div>
          <div class="script-flow-zoom-controls pointer-events-auto flex shrink-0 flex-row overflow-hidden rounded-lg border border-border bg-card shadow-md">
            <ControlButton
              class="!rounded-none !border-b-0"
              title="Увеличить"
              :disabled="zoomMaxReached"
              @click="zoomIn()"
            >
              <ZoomIn class="h-3.5 w-3.5" aria-hidden="true" />
            </ControlButton>
            <ControlButton
              class="!rounded-none !border-b-0"
              title="Уменьшить"
              :disabled="zoomMinReached"
              @click="zoomOut()"
            >
              <ZoomOut class="h-3.5 w-3.5" aria-hidden="true" />
            </ControlButton>
            <ControlButton class="!rounded-none !border-b-0" title="Весь граф на экране" @click="resetView">
              <Maximize2 class="h-3.5 w-3.5" aria-hidden="true" />
            </ControlButton>
            <ControlButton
              class="!rounded-none !border-b-0"
              :title="interactionLocked ? 'Разблокировать узлы и связи' : 'Заблокировать перетаскивание'"
              @click="toggleViewportInteraction"
            >
              <Lock v-if="interactionLocked" class="h-3.5 w-3.5" aria-hidden="true" />
              <Unlock v-else class="h-3.5 w-3.5" aria-hidden="true" />
            </ControlButton>
          </div>
        </Panel>

        <Panel position="top-right" class="m-4 !top-1/2 -translate-y-1/2 flex flex-col gap-2 pointer-events-auto !z-[60]">
          <div class="flex flex-col gap-1 rounded-xl border border-border bg-card/95 p-1.5 shadow-xl backdrop-blur-md">
            <button
              v-if="viewMode === 'schema'"
              type="button"
              class="flex size-10 items-center justify-center rounded-lg transition-colors hover:bg-muted"
              :class="isPaletteOpen ? 'bg-primary text-primary-foreground hover:bg-primary/90' : 'text-muted-foreground'"
              title="Добавить шаг разговора"
              @click="isPaletteOpen = !isPaletteOpen"
            >
              <Plus class="size-5" />
            </button>
            <button
              v-if="viewMode === 'schema'"
              type="button"
              class="flex size-10 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted"
              title="Поиск узла (Ctrl+K)"
              @click="nodeSearchOpen = true"
            >
              <Search class="size-5" />
            </button>
            <button
              v-if="viewMode === 'schema'"
              type="button"
              class="flex size-10 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted"
              title="Режим списка: шаги как playbook"
              @click="emit('update:viewMode', 'list')"
            >
              <FileText class="size-5" />
            </button>
            <button
              v-if="viewMode === 'list'"
              type="button"
              class="flex size-10 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted"
              title="Режим карты: ветки разговора на холсте"
              @click="emit('update:viewMode', 'schema')"
            >
              <Network class="size-5" />
            </button>

            <DropdownMenu v-if="viewMode === 'schema'" :modal="false">
              <DropdownMenuTrigger as-child>
                <button
                  type="button"
                  class="flex size-10 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted"
                  title="Дополнительные действия сценария"
                >
                  <MoreHorizontal class="size-5" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" class="w-72 p-1.5">
                <DropdownMenuItem
                  class="cursor-pointer flex items-start gap-3 rounded-md px-3 py-2.5"
                  @click="isTemplatePickerOpen = true"
                >
                  <Sparkles class="mt-0.5 size-4 shrink-0" />
                  <div class="space-y-0.5">
                    <div class="text-sm font-medium">Шаблоны сценария</div>
                    <div class="text-[11px] leading-snug text-muted-foreground">
                      Заменить текущую схему готовым шаблоном.
                    </div>
                  </div>
                </DropdownMenuItem>
                <DropdownMenuItem
                  class="cursor-pointer flex items-start gap-3 rounded-md px-3 py-2.5"
                  @click="scriptFlowCoverageOpen = true"
                >
                  <LayoutGrid class="mt-0.5 size-4 shrink-0" />
                  <div class="space-y-0.5">
                    <div class="text-sm font-medium">Покрытие сценария</div>
                    <div class="text-[11px] leading-snug text-muted-foreground">
                      Проверить, где сценарий закрывает услуги и возражения.
                    </div>
                  </div>
                </DropdownMenuItem>
                <DropdownMenuItem
                  class="cursor-pointer flex items-start gap-3 rounded-md px-3 py-2.5"
                  @click="scriptFlowSandboxOpen = true"
                >
                  <FlaskConical class="mt-0.5 size-4 shrink-0" />
                  <div class="space-y-0.5">
                    <div class="text-sm font-medium">Debug-поиск сценария</div>
                    <div class="text-[11px] leading-snug text-muted-foreground">
                      Посмотреть, какой сценарий ассистент найдет по фразе клиента.
                    </div>
                  </div>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            <div class="h-px w-full bg-border" />

            <button
              type="button"
              class="flex size-10 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted"
              title="Обучение ассистента и статистика"
              @click="isStatusSheetOpen = true"
            >
              <Activity class="size-5" />
            </button>

            <button
              type="button"
              class="flex size-10 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted"
              title="Как собрать понятный сценарий"
              @click="isCanvasGuideOpen = true"
            >
              <HelpCircle class="size-5" />
            </button>
          </div>
        </Panel>

        <template v-if="viewMode === 'list'">
          <Panel position="top-left" class="h-full w-full !m-0 pointer-events-none">
            <div class="flex h-full min-h-0 w-full flex-col pointer-events-auto overflow-hidden bg-background">
              <div class="border-b border-border bg-background/95 px-4 py-3 text-[11px] leading-relaxed text-muted-foreground">
                Здесь удобнее собирать сценарий как набор смысловых шагов: когда включаться в разговор,
                что отвечать клиенту и как вести его дальше.
              </div>
              <TacticLibraryView :flow-definition="flowDefinition" />
            </div>
          </Panel>
        </template>
      </VueFlow>

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

    <Sheet
      :open="isInspectorOpen"
      :modal="false"
      @update:open="onInspectorOpenChange"
    >
      <SheetContent
        side="right"
        :hide-overlay="true"
        class-name="w-full sm:max-w-[760px] md:max-w-[860px] lg:max-w-[980px] p-0 border-l border-border !bg-background shadow-2xl flex flex-col min-h-0 max-h-[100vh]"
      >
        <SheetTitle class="sr-only">
          {{ inspectorTemplateLabel ? `Шаблон: ${inspectorTemplateLabel}` : 'Параметры узла' }}
        </SheetTitle>
        <div class="flex min-h-0 flex-1 flex-col overflow-hidden">
          <div
            v-if="inspectorTemplateLabel"
            class="shrink-0 border-b border-border bg-muted/30 px-4 py-2.5"
          >
            <p class="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
              Шаблон сценария
            </p>
            <p class="text-sm font-semibold text-foreground">
              {{ inspectorTemplateLabel }}
            </p>
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
              Выберите нужный смысловой блок и перетащите его на карту разговора.
            </p>
          </div>
          <div class="flex flex-col gap-2 border-b border-border p-3">
            <button
              v-for="row in scenarioPalette"
              :key="row.type"
              type="button"
              draggable="true"
              :title="paletteDescription(row.type)"
              class="flex w-full cursor-grab flex-col items-start rounded-xl border border-border/80 bg-background px-4 py-3.5 text-left transition-colors hover:border-primary/30 hover:bg-muted/40 active:cursor-grabbing"
              @dragstart="onPaletteDragStart($event, row.type, false)"
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
              draggable="true"
              :title="paletteDescription(row.type)"
              class="flex w-full cursor-grab flex-col items-start rounded-xl border border-sky-200/80 bg-background px-4 py-3.5 text-left transition-colors hover:border-sky-400/40 hover:bg-sky-50/70 active:cursor-grabbing"
              @dragstart="onPaletteDragStart($event, row.type, true)"
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
      :open="isTemplatePickerOpen"
      :modal="false"
      @update:open="isTemplatePickerOpen = $event"
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

    <Sheet
      :open="isStatusSheetOpen"
      :modal="false"
      @update:open="isStatusSheetOpen = $event"
    >
      <SheetContent
        side="right"
        :hide-overlay="true"
        class-name="w-full sm:max-w-[360px] p-0 border-l border-border !bg-card shadow-2xl"
      >
        <SheetTitle class="sr-only">Статус и статистика</SheetTitle>
        <div class="flex h-full flex-col overflow-y-auto">
          <div class="border-b border-border px-4 py-4">
            <h4 class="text-sm font-bold text-foreground">Статус и статистика</h4>
          </div>

          <div class="flex flex-col divide-y divide-border border-b border-border">
            <!-- Индекс -->
            <div class="flex flex-col gap-1.5 px-4 py-4">
              <div class="flex items-center justify-between">
                <span class="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Память ассистента</span>
                <span
                  class="rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-tight"
                  :class="indexStatusClass"
                >
                  {{ indexLabel }}
                </span>
              </div>
              <p class="text-[11px] leading-relaxed text-muted-foreground">
                {{ indexDescription }}
              </p>
            </div>

            <!-- Проблемы -->
            <div class="flex flex-col gap-1.5 px-4 py-4">
              <div class="flex items-center justify-between">
                <span class="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Проверка перед публикацией</span>
                <div v-if="riskSummary" class="flex items-center gap-1.5">
                  <span
                    class="rounded border px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-tight"
                    :class="riskPillClass"
                  >
                    {{ riskBadgeText }}
                  </span>
                </div>
                <span v-else class="text-[11px] text-muted-foreground">Проверки не проводились</span>
              </div>
              <p v-if="riskSummary" class="text-[11px] leading-relaxed text-muted-foreground">
                {{ riskTitle }}
              </p>
              <div class="mt-2 flex flex-col gap-1">
                <button
                  type="button"
                  class="text-left text-[11px] font-semibold text-indigo-600 hover:underline"
                  @click="emit('update:viewMode', 'schema'); scriptFlowCoverageOpen = true"
                >
                  Открыть карту ветвлений и покрытие →
                </button>
                <button
                  v-if="scriptFlowToolbarPayload?.onReadiness"
                  type="button"
                  class="text-left text-[11px] font-semibold text-indigo-600 hover:underline"
                  @click="scriptFlowToolbarPayload.onReadiness()"
                >
                  Список всех проверок →
                </button>
              </div>
            </div>

            <!-- Статистика -->
            <div class="flex flex-col gap-1.5 px-4 py-4">
              <span class="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Использование</span>
              <div v-if="toolUsageDisplay" class="space-y-2">
                <div class="flex items-center gap-3">
                  <div class="flex size-8 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-600">
                    <BarChart3 class="size-4" />
                  </div>
                  <div>
                    <div class="text-sm font-bold text-foreground">~{{ toolUsageDisplay.calls }} вызовов</div>
                    <div class="text-[10px] text-muted-foreground">за последние {{ toolUsageDisplay.days }} дн.</div>
                  </div>
                </div>
                <p v-if="toolUsageDisplay.disclaimer" class="text-[10px] leading-snug text-muted-foreground italic">
                  {{ toolUsageDisplay.disclaimer }}
                </p>
              </div>
              <div v-else class="py-2 text-[11px] text-muted-foreground">
                Нет данных об использовании за указанный период.
              </div>
            </div>

            <!-- GraphRAG -->
            <div class="flex flex-col gap-2 px-4 py-4">
              <div class="flex items-center justify-between gap-2">
                <span class="text-xs font-semibold uppercase tracking-wider text-muted-foreground">GraphRAG</span>
                <button
                  type="button"
                  class="text-[11px] font-semibold text-indigo-600 hover:underline disabled:cursor-not-allowed disabled:opacity-50"
                  :disabled="graphPreviewLoading"
                  @click="loadGraphPreview"
                >
                  {{ graphPreviewLoading ? 'Обновляем…' : 'Обновить превью' }}
                </button>
              </div>

              <p class="text-[11px] leading-relaxed text-muted-foreground">
                Показывает, как текущий canvas превращается в граф знаний: узлы, связи, сообщества и качество LLM-извлечения.
              </p>

              <div v-if="graphPreviewError" class="rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-[11px] text-destructive">
                {{ graphPreviewError }}
              </div>

              <div v-else-if="graphPreviewLoading" class="rounded-lg border border-border bg-muted/30 px-3 py-3 text-[11px] text-muted-foreground">
                Строим GraphRAG-превью по текущему черновику…
              </div>

              <div v-else-if="graphSummary" class="space-y-3">
                <div class="grid grid-cols-3 gap-2">
                  <div class="rounded-lg border border-border bg-muted/20 px-3 py-2">
                    <div class="text-[10px] uppercase tracking-wider text-muted-foreground">Узлы</div>
                    <div class="mt-1 text-sm font-bold text-foreground">{{ graphSummary.nodes }}</div>
                  </div>
                  <div class="rounded-lg border border-border bg-muted/20 px-3 py-2">
                    <div class="text-[10px] uppercase tracking-wider text-muted-foreground">Связи</div>
                    <div class="mt-1 text-sm font-bold text-foreground">{{ graphSummary.relations }}</div>
                  </div>
                  <div class="rounded-lg border border-border bg-muted/20 px-3 py-2">
                    <div class="text-[10px] uppercase tracking-wider text-muted-foreground">Кластеры</div>
                    <div class="mt-1 text-sm font-bold text-foreground">{{ graphSummary.communities }}</div>
                  </div>
                </div>

                <div class="rounded-lg border border-border bg-background/60 px-3 py-2.5 text-[11px]">
                  <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <span class="font-semibold text-foreground">Режим: {{ graphSummary.extractionMode }}</span>
                    <span v-if="graphSummary.llmOkNodes !== null" class="text-emerald-700">LLM OK: {{ graphSummary.llmOkNodes }}</span>
                    <span v-if="graphSummary.llmFailedNodes !== null" class="text-amber-700">LLM fallback: {{ graphSummary.llmFailedNodes }}</span>
                  </div>
                </div>

                <div v-if="topGraphCommunities.length" class="space-y-2">
                  <div class="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Главные сообщества знаний
                  </div>
                  <div
                    v-for="community in topGraphCommunities"
                    :key="community.community_key"
                    class="rounded-lg border border-border bg-card px-3 py-2.5"
                  >
                    <div class="text-xs font-semibold text-foreground">
                      {{ community.title }}
                    </div>
                    <p v-if="community.summary" class="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                      {{ community.summary }}
                    </p>
                    <div class="mt-2 flex flex-wrap gap-2 text-[10px] text-muted-foreground">
                      <span class="rounded border border-border bg-muted/30 px-1.5 py-0.5">
                        {{ community.node_ids.length }} узл.
                      </span>
                      <span
                        v-if="Array.isArray(community.properties?.key_points) && community.properties?.key_points.length"
                        class="rounded border border-border bg-muted/30 px-1.5 py-0.5"
                      >
                        {{ community.properties?.key_points.length }} ключевых тезисов
                      </span>
                    </div>
                  </div>
                </div>

                <div v-if="topGraphEntities.length" class="space-y-2">
                  <div class="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Извлечённые сущности
                  </div>
                  <div class="flex flex-wrap gap-2">
                    <span
                      v-for="entity in topGraphEntities"
                      :key="entity.graph_node_id"
                      class="rounded-full border border-border bg-muted/30 px-2 py-1 text-[10px] text-foreground"
                    >
                      {{ entity.entity_type }} · {{ entity.title }}
                    </span>
                  </div>
                </div>

                <div v-if="topRelationTypes.length" class="space-y-2">
                  <div class="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                    Основные типы связей
                  </div>
                  <div class="flex flex-wrap gap-2">
                    <span
                      v-for="[relationType, count] in topRelationTypes"
                      :key="relationType"
                      class="rounded border border-border bg-background/70 px-2 py-1 text-[10px] text-muted-foreground"
                    >
                      {{ relationType }} ×{{ count }}
                    </span>
                  </div>
                </div>

                <details v-if="graphDiagnosticRaw" class="rounded-lg border border-border bg-muted/10 px-3 py-2.5">
                  <summary class="cursor-pointer text-[11px] font-semibold text-foreground">
                    Raw diagnostics
                  </summary>
                  <pre class="mt-2 overflow-x-auto whitespace-pre-wrap text-[10px] leading-relaxed text-muted-foreground">{{ graphDiagnosticRaw }}</pre>
                </details>
              </div>

              <div v-else class="rounded-lg border border-border bg-muted/20 px-3 py-2 text-[11px] text-muted-foreground">
                GraphRAG-превью ещё не загружено.
              </div>
            </div>
          </div>

          <div class="mt-auto border-t border-border p-4">
            <div class="rounded-lg bg-muted/40 p-3">
              <div class="flex items-start gap-2.5">
                <Clock class="mt-0.5 size-3.5 text-muted-foreground" />
                <div class="space-y-1">
                  <p class="text-[11px] font-semibold text-foreground leading-none">Последние изменения</p>
                  <p class="text-[10px] text-muted-foreground leading-relaxed">
                    {{ dirtyLabel || 'Черновик соответствует опубликованной версии.' }}
                  </p>
                </div>
              </div>
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
import { ref, watch, markRaw, nextTick, provide, computed, toRaw } from 'vue'
import { onKeyStroke, useDebounceFn, useEventListener } from '@vueuse/core'
import dagre from 'dagre'
import { nanoid } from 'nanoid'
import {
  VueFlow, useVueFlow, ConnectionLineType,
  type Node, type Edge as FlowEdge, type XYPosition,
  type Connection, type EdgeMouseEvent, Panel,
} from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { ControlButton } from '@vue-flow/controls'
import { MiniMap } from '@vue-flow/minimap'
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
  LayoutGrid,
  FlaskConical,
  Activity,
  HelpCircle,
  AlertCircle,
  BarChart3,
  Clock,
  Sparkles,
  MoreHorizontal,
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
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '~/components/ui/dropdown-menu'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '~/components/ui/dialog'
import { useScriptFlows } from '~/composables/useScriptFlows'
import { getReadableErrorMessage } from '~/utils/api-errors'
import type { ScriptFlowGraphPreview } from '~/types/scriptFlow'

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

const { scriptFlowSandboxOpen, scriptFlowCoverageOpen, scriptFlowToolbarPayload } = useLayoutState()
const route = useRoute()
const agentId = String(route.params.id ?? '')
const { getGraphRagPreviewDraft } = useScriptFlows(agentId)

const indexLabel = computed(() => {
  const s = scriptFlowToolbarPayload.value?.flow?.index_status
  const labels: Record<string, string> = {
    idle: 'не начато',
    pending: 'в очереди',
    indexing: 'обновление',
    indexed: 'готово',
    failed: 'ошибка',
  }
  return labels[s ?? 'idle'] ?? s ?? '—'
})

const indexStatusClass = computed(() => {
  switch (scriptFlowToolbarPayload.value?.flow?.index_status) {
    case 'indexed':
      return 'border-emerald-200 bg-emerald-50 text-emerald-800'
    case 'pending':
    case 'indexing':
      return 'border-sky-200 bg-sky-50 text-sky-800'
    case 'failed':
      return 'border-destructive/40 bg-destructive/10 text-destructive'
    default:
      return 'border-border bg-muted/40 text-muted-foreground'
  }
})

const indexDescription = computed(() => {
  const s = scriptFlowToolbarPayload.value?.flow?.index_status
  if (s === 'indexed') return 'Ассистент уже опирается на актуальный сценарий при ответах.'
  if (s === 'failed') return scriptFlowToolbarPayload.value?.flow?.index_error || 'Не удалось обновить память ассистента по этому сценарию.'
  if (s === 'indexing' || s === 'pending') return 'Обновляем память ассистента по опубликованному сценарию…'
  return 'После публикации сценарий попадёт в память ассистента для поиска и ответов.'
})

const riskSummary = computed(() => scriptFlowToolbarPayload.value?.riskSummary)

const riskBadgeText = computed(() =>
  riskSummary.value ? coverageRiskBadgeLabel(riskSummary.value) : '',
)

const riskTitle = computed(() => {
  const s = riskSummary.value
  if (!s) return ''
  if (s.level === 'ok') return 'Критических проблем в таблице покрытия нет.'
  return s.level === 'critical'
    ? `Критично: ${s.criticalCount} проблем. Публикация заблокирована.`
    : `Предупреждения: ${s.warningCount}. Публикация возможна.`
})

const riskPillClass = computed(() => {
  switch (riskSummary.value?.level) {
    case 'ok':
      return 'border-emerald-200/80 bg-emerald-50 text-emerald-900'
    case 'warn':
      return 'border-amber-300 bg-amber-50 text-amber-950'
    case 'critical':
      return 'border-destructive/50 bg-destructive/15 text-destructive'
    default:
      return 'border-border'
  }
})

const toolUsageDisplay = computed(() => {
  const u = scriptFlowToolbarPayload.value?.toolUsage
  if (!u || typeof u.approximate_flow_tool_calls !== 'number') return null
  let peakNote = ''
  const ds = u.daily_series
  if (Array.isArray(ds) && ds.length) {
    const mx = ds.reduce((a, b) => (b.count > a.count ? b : a), ds[0]!)
    peakNote = `Пик: ${mx.count} (${mx.date})`
  }
  const disclaimer = [u.disclaimer ?? '', peakNote].filter(Boolean).join(' · ')
  return {
    calls: u.approximate_flow_tool_calls,
    days: typeof u.days === 'number' ? u.days : 7,
    disclaimer: disclaimer || undefined,
  }
})

const dirtyLabel = computed(() => {
  const flow = scriptFlowToolbarPayload.value?.flow
  if (flow?.flow_status !== 'published') return ''
  const meta = flow?.flow_metadata as Record<string, unknown> | undefined
  const snap = meta?.published_flow_definition
  if (!snap || typeof snap !== 'object') return ''
  try {
    const cur = JSON.stringify(flow?.flow_definition ?? {})
    const pub = JSON.stringify(snap)
    return cur !== pub ? 'Черновик отличается от опубликованной версии.' : ''
  }
  catch {
    return ''
  }
})

const graphPreviewLoading = ref(false)
const graphPreviewError = ref<string | null>(null)
const graphPreview = ref<ScriptFlowGraphPreview | null>(null)

const graphSummary = computed(() => {
  const preview = graphPreview.value
  if (!preview) return null
  const diagnostic = preview.debug?.diagnostic
  return {
    nodes: preview.nodes.length,
    relations: preview.relations.length,
    communities: preview.communities.length,
    extractionMode: diagnostic?.extraction_mode || String(preview.debug?.source || 'draft_preview'),
    llmOkNodes: diagnostic?.llm_ok_nodes ?? null,
    llmFailedNodes: diagnostic?.llm_failed_nodes ?? null,
  }
})

const topGraphCommunities = computed(() =>
  (graphPreview.value?.communities ?? []).slice(0, 3),
)

const topGraphEntities = computed(() =>
  (graphPreview.value?.nodes ?? [])
    .filter(node => node.node_kind !== 'canvas' && node.entity_type !== 'stage' && node.entity_type !== 'variable')
    .slice(0, 8),
)

const topRelationTypes = computed(() => {
  const counts = new Map<string, number>()
  for (const rel of graphPreview.value?.relations ?? []) {
    const key = String(rel.relation_type || '').trim()
    if (!key) continue
    counts.set(key, (counts.get(key) ?? 0) + 1)
  }
  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
})

const graphDiagnosticRaw = computed(() => {
  const raw = graphPreview.value?.debug?.diagnostic?.raw
  if (!raw || typeof raw !== 'object') return null
  try {
    return JSON.stringify(raw, null, 2)
  }
  catch {
    return null
  }
})

const loadGraphPreview = async () => {
  const flowId = String(scriptFlowToolbarPayload.value?.flow?.id ?? '').trim()
  if (!flowId) {
    graphPreview.value = null
    return
  }
  graphPreviewLoading.value = true
  graphPreviewError.value = null
  try {
    graphPreview.value = await getGraphRagPreviewDraft(
      flowId,
      (props.flowDefinition as Record<string, unknown>) ?? {},
      (scriptFlowToolbarPayload.value?.flow?.flow_metadata as Record<string, unknown>) ?? {},
    )
  }
  catch (err: unknown) {
    graphPreviewError.value = getReadableErrorMessage(err, 'Не удалось построить GraphRAG-превью')
  }
  finally {
    graphPreviewLoading.value = false
  }
}

import { coverageRiskBadgeLabel } from '~/utils/scriptFlowCoverageRisk'

// ── Палитра и экшн-бар ──────────────────────────────────────────────────────
const isPaletteOpen = ref(false)
const isTemplatePickerOpen = ref(false)
const isStatusSheetOpen = ref(false)
const isCanvasGuideOpen = ref(false)
const pendingTemplateId = ref<string | null>(null)
const pendingTemplate = computed(() =>
  SCRIPT_FLOW_TEMPLATE_LIST.find(t => t.id === pendingTemplateId.value) ?? null,
)

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
    isStatusSheetOpen.value = false
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
    isStatusSheetOpen.value = false
  }
})

watch(isTemplatePickerOpen, (v) => {
  if (v) {
    inspectorNodeId.value = null
    isPaletteOpen.value = false
    isStatusSheetOpen.value = false
  }
  if (!v)
    pendingTemplateId.value = null
})

watch(isStatusSheetOpen, (v) => {
  if (v) {
    inspectorNodeId.value = null
    isPaletteOpen.value = false
    isTemplatePickerOpen.value = false
    loadGraphPreview()
  }
})

watch(isCanvasGuideOpen, (v) => {
  if (v) {
    inspectorNodeId.value = null
    isPaletteOpen.value = false
    isTemplatePickerOpen.value = false
    isStatusSheetOpen.value = false
  }
})

watch(inspectorNodeId, (id) => {
  if (!id)
    inspectorTemplateLabel.value = null
  else
    isTemplatePickerOpen.value = false
})

provide('inspectorNodeId', inspectorNodeId)
provide('flowVarNames', computed(() => props.varNames ?? []))
provide('flowAgentFunctions', computed(() => props.agentFunctions ?? []))
provide('flowVariables', computed(() => props.flowVariables as Record<string, unknown> | undefined))
provide('onFlowVariablesUpdate', (v: Record<string, unknown>) => emit('update:flowVariables', v))
provide('flowServiceOptions', computed(() => props.serviceOptions ?? []))
provide('flowEmployeeOptions', computed(() => props.employeeOptions ?? []))
provide('flowKgEntityOptions', computed(() => props.kgEntityOptions ?? []))
provide('flowRuntimeUsageByNode', computed(() => props.runtimeUsageByNode ?? {}))

const {
  project,
  fitView,
  addEdges,
  findNode,
  viewport,
  zoomIn,
  zoomOut,
  minZoom,
  maxZoom,
  nodesDraggable,
  nodesConnectable,
  elementsSelectable,
  setInteractive,
} = useVueFlow(AGENT_SCRIPT_FLOW_VUE_FLOW_ID)

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

const orphanNodeIds = computed((): Set<string> => {
  const edgeList = edges.value as FlowEdge[]
  const nodeList = nodes.value as Node[]
  const incoming = new Set(edgeList.map(e => String(e.target)))
  const outgoing = new Set(edgeList.map(e => String(e.source)))
  const orphans = new Set<string>()
  for (const n of nodeList) {
    const nid = String(n.id)
    const data = (n.data || {}) as { node_type?: string }
    const nt = data.node_type
    if (nt === 'trigger')
      continue
    if (!incoming.has(nid))
      orphans.add(nid)
  }
  for (const n of nodeList) {
    const nid = String(n.id)
    const data = (n.data || {}) as { node_type?: string }
    if (data.node_type === 'end' && !outgoing.has(nid))
      orphans.add(nid)
  }
  return orphans
})
provide('flowOrphanNodeIds', orphanNodeIds)

const defaultEdgeOptions = {
  type: 'default',
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
    out.push({ ...rest, type: 'default' } as FlowEdge)
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
const selectedId = ref<string | null>(null)
/** Не эмитить flow_definition на родителя пока подтягиваем граф из props (избегаем лишнего PATCH). */
const syncingFromParent = ref(false)

/** Явный тип — иначе TS разворачивает глубокие дженерики `GraphNode` из Vue Flow до ошибки «слишком глубоко». */
type FlowNodeRefOption = { id: string; title: string; node_type: string }

const nodeRefOptions = computed((): FlowNodeRefOption[] =>
  nodes.value.map((n) => {
    const data = (n.data || {}) as Record<string, unknown>
    const title = typeof data.title === 'string' && data.title.trim() ? data.title : String(n.id)
    const nodeType = typeof data.node_type === 'string' ? data.node_type : String(n.type ?? '')
    return {
      id: String(n.id),
      title,
      node_type: nodeType,
    }
  }),
)
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

watch(
  () => props.revision,
  () => {
    syncFromProps()
    nextTick(() => {
      nextTick(() => {
        try {
          fitView({ padding: 0.15, duration: 0 })
        }
        catch {
          /* Vue Flow ещё не смонтирован в первом кадре */
        }
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

watch(
  [nodes, edges],
  () => debouncedPushDefinition(),
  { deep: true },
)

watch(
  viewport,
  () => {
    emitViewportDebounced()
  },
  { deep: true },
)

const nodeSearchOpen = ref(false)
const nodeSearchQuery = ref('')
const nodeSearchInputRef = ref<HTMLInputElement | null>(null)

const filteredSearchNodes = computed(() => {
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
    out.push({
      id: String(n.id),
      title: title || String(n.id),
      sub: situation || gq || '',
    })
  }
  return q ? out.slice(0, 40) : out.slice(0, 40)
})

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

watch([nodes, edges], () => debouncedRecordHistory(), { deep: true })

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
  inspectorNodeId.value = id
  closeEdgeLabelPopup()
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
  g.setGraph({ rankdir: 'LR', ranksep: 90, nodesep: 48, marginx: 24, marginy: 24 })
  const nw = 240
  const nh = 96
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

const onDrop = (event: DragEvent) => {
  const type = event.dataTransfer?.getData('application/vueflow')
  if (!type) return

  const position = project({
    x: event.clientX - 40,
    y: event.clientY - 40,
  })

  const catalogDrop = event.dataTransfer?.getData('application/catalog') === '1'
  const id = nanoid()
  const meta = NODE_TYPES.find(t => t.value === type)
  const commonTitle = meta?.label ?? 'Новый узел'
  const entrySearchable = type === 'trigger' || type === 'expertise' || type === 'question'
  let dropData: Record<string, unknown> = {
    title: commonTitle,
    node_type: type,
  }
  if (type === 'trigger') {
    dropData = {
      ...dropData,
      client_phrase_examples: [],
      keyword_hints: [],
      when_relevant: '',
      is_flow_entry: true,
      is_searchable: true,
    }
  }
  else if (type === 'expertise') {
    dropData = {
      ...dropData,
      situation: '',
      example_phrases: [],
      is_searchable: true,
    }
  }
  else if (type === 'question') {
    dropData = {
      ...dropData,
      good_question: '',
      alternative_phrasings: [],
      expected_answer_type: 'open',
      why_we_ask: '',
      stage: null,
      level: 1,
      service_ids: [],
      employee_ids: [],
      is_searchable: true,
      kg_links: {},
      conditions: [],
    }
  }
  else if (type === 'condition') {
    dropData = {
      ...dropData,
      routing_hint: '',
      conditions: [],
    }
  }
  else if (type === 'goto') {
    dropData = {
      ...dropData,
      target_flow_id: '',
      target_node_ref: null,
      transition_phrase: '',
      trigger_situation: '',
    }
  }
  else if (type === 'end') {
    dropData = {
      ...dropData,
      outcome_type: null,
      final_action: '',
      kg_links: {},
    }
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
    dropData = {
      ...dropData,
      situation: '',
      ...(entrySearchable ? { is_searchable: true } : {}),
      ...(type === 'trigger' ? { is_flow_entry: true } : {}),
    }
  }

  const newNode: Node = {
    id,
    type: 'expert',
    position,
    data: dropData,
  }

  nodes.value = [...nodes.value, newNode]
  isPaletteOpen.value = false
  inspectorNodeId.value = id
  requestImmediatePersist()
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

.vue-flow__node {
  will-change: transform;
  transition: filter 0.18s ease, opacity 0.18s ease;
}

.vue-flow__node:hover {
  filter: drop-shadow(0 12px 24px rgba(15, 23, 42, 0.10));
}

.vue-flow__node.selected {
  filter: drop-shadow(0 18px 34px rgba(79, 70, 229, 0.18));
}

.vue-flow__handle {
  height: 12px !important;
  width: 12px !important;
  border: 2px solid white !important;
  background: #6366f1 !important;
  box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.10) !important;
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}

.vue-flow__handle:hover {
  transform: scale(1.25);
  box-shadow: 0 0 0 6px rgba(99, 102, 241, 0.16) !important;
}

.vue-flow__edge-path {
  stroke: rgba(99, 102, 241, 0.44) !important;
  stroke-width: 3px !important;
  stroke-linecap: round !important;
  stroke-linejoin: round !important;
  transition: stroke 0.18s ease, stroke-width 0.18s ease, filter 0.18s ease;
}

.vue-flow__edge.selected .vue-flow__edge-path,
.vue-flow__edge:hover .vue-flow__edge-path {
  stroke: rgba(79, 70, 229, 0.82) !important;
  stroke-width: 3.5px !important;
  filter: drop-shadow(0 0 6px rgba(99, 102, 241, 0.16));
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
