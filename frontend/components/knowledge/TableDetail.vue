<template>
  <div class="flex min-h-0 w-full min-w-0 max-w-full flex-1 flex-col -mt-5">

    <div v-if="loading" class="flex justify-center py-16">
      <Loader2 class="h-8 w-8 animate-spin text-indigo-600" />
    </div>

    <div v-else-if="error" class="rounded-3xl border border-red-200 bg-red-50 p-8 text-center">
      <p class="text-sm text-red-600">{{ error }}</p>
    </div>

    <template v-else-if="table">
      <div v-show="isToolbarVisible" class="flex flex-wrap items-center justify-between gap-3 py-3 shrink-0">
        <div v-show="!hasRowSelection" class="flex flex-wrap items-center gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger as-child>
              <button
                type="button"
                class="inline-flex h-10 shrink-0 items-center gap-2 rounded-md bg-indigo-600 px-4 text-sm font-bold text-white transition-colors hover:bg-indigo-700 disabled:opacity-50"
                :disabled="!table || saving"
              >
                <Plus class="h-4 w-4" />
                Добавить
                <ChevronDown class="h-4 w-4 opacity-90" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="start" class="min-w-[17.5rem] p-1.5">
              <DropdownMenuItem
                class="cursor-pointer flex items-start gap-3 rounded-md px-3 py-2.5"
                @select="openAddSheet"
              >
                <List class="mt-0.5 h-4 w-4 shrink-0 text-slate-500" />
                <div class="min-w-0 text-left">
                  <div class="text-sm font-semibold text-slate-900">Добавить строку</div>
                  <div class="text-xs text-slate-500">Новая запись в таблице</div>
                </div>
              </DropdownMenuItem>
              <DropdownMenuItem
                class="cursor-pointer flex items-start gap-3 rounded-md px-3 py-2.5"
                @select="openSettingsForNewColumn"
              >
                <Columns class="mt-0.5 h-4 w-4 shrink-0 text-slate-500" />
                <div class="min-w-0 text-left">
                  <div class="text-sm font-semibold text-slate-900">Добавить колонку</div>
                  <div class="text-xs text-slate-500">Настройки таблицы — блок «Колонки»</div>
                </div>
              </DropdownMenuItem>
              <DropdownMenuItem
                class="cursor-pointer flex items-start gap-3 rounded-md px-3 py-2.5"
                @select="openImportSheet"
              >
                <FileUp class="mt-0.5 h-4 w-4 shrink-0 text-slate-500" />
                <div class="min-w-0 text-left">
                  <div class="text-sm font-semibold text-slate-900">Импорт из CSV</div>
                  <div class="text-xs text-slate-500">
                    Боковая панель: новые колонки создаются автоматически, до 1000 строк за запрос
                  </div>
                </div>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <DropdownMenu v-model:open="filterMenuOpen" :modal="false">
            <DropdownMenuTrigger as-child>
              <button
                type="button"
                class="inline-flex h-10 shrink-0 items-center gap-2 rounded-md border px-4 text-sm font-bold transition-colors disabled:opacity-50"
                :class="
                  hasActiveFilters
                    ? 'border-indigo-300 bg-indigo-50 text-indigo-900 hover:bg-indigo-100'
                    : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
                "
                :disabled="!table || saving || displayColumns.length === 0"
              >
                <Filter class="h-4 w-4 shrink-0" aria-hidden="true" />
                Фильтр
                <span
                  v-if="appliedFilters.length > 0"
                  class="inline-flex min-w-[1.25rem] items-center justify-center rounded-md bg-indigo-600 px-1 text-[11px] font-bold text-white"
                >
                  {{ appliedFilters.length }}
                </span>
                <ChevronDown class="h-4 w-4 shrink-0 opacity-90" aria-hidden="true" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="start"
              :side-offset="8"
              class="z-[10002] max-h-[min(85vh,32rem)] w-[min(40rem,calc(100vw-1rem))] min-w-[min(40rem,calc(100vw-1rem))] !overflow-x-visible !overflow-y-auto border-slate-200 p-0 shadow-lg"
            >
              <div class="border-b border-slate-100 px-4 py-3">
                <p v-if="filterDraft.length === 0" class="text-sm font-medium text-slate-800">
                  К этому виду фильтры не применены
                </p>
                <p v-else class="text-sm font-medium text-slate-800">Условия фильтра</p>
                <p class="mt-1 text-xs text-slate-500">
                  Добавьте колонку и значение ниже, затем нажмите «Применить фильтр». Для пустых ячеек
                  выберите «Пусто» или «Не пусто» — поле значения не нужно.
                </p>
              </div>

              <div
                v-if="filterDraft.length >= 2"
                class="border-b border-slate-100 px-4 py-2.5"
              >
                <p class="mb-2 text-xs font-medium uppercase tracking-wide text-slate-500">
                  Объединение условий
                </p>
                <div class="flex flex-wrap gap-4">
                  <label class="flex cursor-pointer items-center gap-2 text-sm text-slate-800">
                    <input
                      v-model="filterCombineDraft"
                      type="radio"
                      value="and"
                      class="h-4 w-4 border-slate-300 text-indigo-600 focus:ring-indigo-500"
                    />
                    Все условия (И)
                  </label>
                  <label class="flex cursor-pointer items-center gap-2 text-sm text-slate-800">
                    <input
                      v-model="filterCombineDraft"
                      type="radio"
                      value="or"
                      class="h-4 w-4 border-slate-300 text-indigo-600 focus:ring-indigo-500"
                    />
                    Любое условие (ИЛИ)
                  </label>
                </div>
              </div>

              <div
                v-if="filterDraft.length > 0"
                class="max-h-[min(50vh,16rem)] space-y-2 overflow-y-auto overflow-x-visible px-4 py-3"
              >
                <div
                  v-for="rule in filterDraft"
                  :key="rule.uid"
                  class="grid grid-cols-1 gap-2 rounded-md border border-slate-100 bg-slate-50/80 p-2.5 sm:grid-cols-[minmax(10.5rem,1.45fr)_minmax(11rem,auto)_minmax(8rem,1.55fr)_2.25rem] sm:items-center sm:gap-x-2"
                >
                  <select
                    v-model="rule.columnName"
                    class="h-9 w-full min-w-0 rounded-md border border-slate-200 bg-white px-2 text-left text-sm text-slate-800 outline-none focus:ring-2 focus:ring-indigo-500/30"
                  >
                    <option v-for="attr in displayColumns" :key="attr.name" :value="attr.name">
                      {{ attr.label }}
                    </option>
                  </select>
                  <select
                    v-model="rule.operator"
                    class="h-9 w-full min-w-0 rounded-md border border-slate-200 bg-white px-2 text-left text-sm text-slate-800 outline-none focus:ring-2 focus:ring-indigo-500/30 sm:min-w-[11rem] sm:w-full"
                  >
                    <option value="contains">Содержит</option>
                    <option value="not_contains">Не содержит</option>
                    <option value="equals">Равно</option>
                    <option value="gt">Больше</option>
                    <option value="lt">Меньше</option>
                    <option value="gte">Больше или равно</option>
                    <option value="lte">Меньше или равно</option>
                    <option value="is_empty">Пусто</option>
                    <option value="is_not_empty">Не пусто</option>
                  </select>
                  <input
                    v-if="rule.operator !== 'is_empty' && rule.operator !== 'is_not_empty'"
                    v-model="rule.value"
                    type="text"
                    placeholder="Значение"
                    class="h-9 w-full min-w-0 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-800 outline-none placeholder:text-slate-400 focus:ring-2 focus:ring-indigo-500/30"
                  />
                  <div
                    v-else
                    class="flex h-9 w-full min-w-0 items-center rounded-md border border-dashed border-slate-200 bg-slate-50/90 px-2 text-xs text-slate-400"
                  >
                    Значение не нужно
                  </div>
                  <button
                    type="button"
                    class="inline-flex h-9 w-9 shrink-0 items-center justify-center justify-self-start rounded-md border border-slate-200 bg-white text-slate-500 transition-colors hover:border-rose-200 hover:bg-rose-50 hover:text-rose-600 sm:justify-self-center"
                    aria-label="Удалить условие"
                    @click="removeFilterRow(rule.uid)"
                  >
                    <span class="text-lg leading-none">×</span>
                  </button>
                </div>
              </div>

              <div class="flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 px-4 py-3">
                <button
                  type="button"
                  class="inline-flex items-center gap-1.5 text-sm font-semibold text-indigo-600 hover:text-indigo-800 disabled:opacity-40"
                  :disabled="displayColumns.length === 0"
                  @click="addFilterRow"
                >
                  <Plus class="h-4 w-4" />
                  Добавить фильтр
                </button>
                <div class="flex flex-wrap items-center gap-2">
                  <button
                    v-if="filterDraft.length > 0 || appliedFilters.length > 0"
                    type="button"
                    class="text-sm font-medium text-slate-500 hover:text-slate-800"
                    @click="clearAllFilters"
                  >
                    Сбросить
                  </button>
                  <button
                    type="button"
                    class="inline-flex h-9 items-center rounded-md border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-800 transition-colors hover:bg-slate-50"
                    @click="applyFilterDraft"
                  >
                    Применить фильтр
                  </button>
                </div>
              </div>
            </DropdownMenuContent>
          </DropdownMenu>

          <DropdownMenu v-model:open="sortMenuOpen" :modal="false">
            <DropdownMenuTrigger as-child>
              <button
                type="button"
                class="inline-flex h-10 shrink-0 items-center gap-2 rounded-md border px-4 text-sm font-bold transition-colors disabled:opacity-50"
                :class="
                  hasActiveSort
                    ? 'border-indigo-300 bg-indigo-50 text-indigo-900 hover:bg-indigo-100'
                    : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
                "
                :disabled="!table || saving || displayColumns.length === 0"
              >
                <ArrowDownUp class="h-4 w-4 shrink-0" aria-hidden="true" />
                Сортировка
                <span
                  v-if="appliedSortRules.length > 0"
                  class="inline-flex min-w-[1.25rem] items-center justify-center rounded-md bg-indigo-600 px-1 text-[11px] font-bold text-white"
                >
                  {{ appliedSortRules.length }}
                </span>
                <ChevronDown class="h-4 w-4 shrink-0 opacity-90" aria-hidden="true" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="start"
              :side-offset="8"
              class="z-[10002] max-h-[min(85vh,32rem)] w-[min(30rem,calc(100vw-1rem))] min-w-[min(30rem,calc(100vw-1rem))] !overflow-x-visible !overflow-y-auto border-slate-200 p-0 shadow-lg"
            >
              <div class="border-b border-slate-100 px-4 py-3">
                <p v-if="sortDraft.length === 0" class="text-sm font-medium text-slate-800">
                  К этому виду сортировка не задана
                </p>
                <p v-else class="text-sm font-medium text-slate-800">Порядок сортировки</p>
                <p class="mt-1 text-xs text-slate-500">
                  Сначала выше — важнее. Ниже выберите колонку или добавьте уровень, затем нажмите «Применить».
                </p>
              </div>

              <div
                v-if="sortDraft.length > 0"
                class="max-h-[min(50vh,16rem)] space-y-2 overflow-y-auto overflow-x-visible px-4 py-3"
              >
                <div
                  v-for="rule in sortDraft"
                  :key="rule.uid"
                  class="grid grid-cols-1 gap-2 rounded-md border border-slate-100 bg-slate-50/80 p-2.5 sm:grid-cols-[minmax(11rem,1.25fr)_auto_2.25rem] sm:items-center sm:gap-x-3"
                >
                  <div class="min-w-0">
                    <select
                      v-model="rule.columnName"
                      class="h-8 w-full min-w-0 rounded-md border border-slate-200 bg-white px-2 text-left text-sm text-slate-800 outline-none focus:ring-2 focus:ring-indigo-500/30"
                    >
                      <option v-for="attr in displayColumns" :key="attr.name" :value="attr.name">
                        {{ attr.label }}
                      </option>
                    </select>
                  </div>
                  <div class="flex items-center gap-2 self-start sm:self-center">
                    <div
                      class="flex h-6 w-7 shrink-0 items-center justify-center text-emerald-600"
                      aria-hidden="true"
                    >
                      <ArrowUp v-if="rule.ascending" class="h-4 w-4" />
                      <ArrowDown v-else class="h-4 w-4" />
                    </div>
                    <Switch
                      :model-value="rule.ascending"
                      class-name="shrink-0"
                      @update:model-value="(v) => (rule.ascending = v)"
                    />
                  </div>
                  <button
                    type="button"
                    class="inline-flex h-9 w-9 shrink-0 items-center justify-center justify-self-start rounded-md text-slate-400 transition-colors hover:bg-rose-50 hover:text-rose-600 sm:justify-self-center"
                    aria-label="Удалить уровень сортировки"
                    @click="removeSortRow(rule.uid)"
                  >
                    <span class="text-lg leading-none">×</span>
                  </button>
                </div>
              </div>

              <div class="space-y-3 border-t border-slate-100 px-4 py-3">
                <div v-if="sortColumnsAvailableForPick.length > 0" class="sm:pl-2.5">
                  <div class="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center sm:gap-x-3">
                    <label class="sr-only">Добавить колонку в порядок сортировки</label>
                    <select
                      :key="sortColumnPickerKey"
                      class="h-8 w-full min-w-0 rounded-md border border-slate-200 bg-white px-2 text-left text-sm text-slate-800 outline-none focus:ring-2 focus:ring-indigo-500/30 sm:max-w-[min(100%,18rem)]"
                      @change="onSortColumnPicked"
                    >
                      <option value="">Выберите колонку…</option>
                      <option v-for="attr in sortColumnsAvailableForPick" :key="attr.name" :value="attr.name">
                        {{ attr.label }}
                      </option>
                    </select>
                    <button
                      type="button"
                      class="inline-flex shrink-0 items-center gap-1.5 text-sm font-semibold text-indigo-600 hover:text-indigo-800"
                      @click="addSortRow"
                    >
                      <Plus class="h-4 w-4" />
                      Добавить
                    </button>
                  </div>
                </div>
                <div
                  v-else
                  class="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3 sm:pl-2.5"
                >
                  <p class="min-w-0 flex-1 text-xs text-slate-500">
                    Все колонки уже в списке — удалите уровень, чтобы выбрать другую.
                  </p>
                  <button
                    type="button"
                    class="inline-flex shrink-0 items-center gap-1.5 text-sm font-semibold text-indigo-600 disabled:opacity-40"
                    disabled
                  >
                    <Plus class="h-4 w-4" />
                    Добавить
                  </button>
                </div>
                <div class="flex flex-wrap items-center justify-end gap-2">
                  <button
                    v-if="sortDraft.length > 0 || appliedSortRules.length > 0"
                    type="button"
                    class="text-sm font-medium text-slate-500 hover:text-slate-800"
                    @click="clearAllSorts"
                  >
                    Сбросить
                  </button>
                  <button
                    type="button"
                    class="inline-flex h-9 items-center rounded-md border-0 bg-slate-100 px-3 text-sm font-semibold text-slate-800 transition-colors hover:bg-slate-200 disabled:pointer-events-none disabled:opacity-40"
                    :disabled="sortDraft.length === 0"
                    @click="applySortDraft"
                  >
                    Применить
                  </button>
                </div>
              </div>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <div v-show="hasRowSelection" class="flex flex-wrap items-center gap-2">
          <button
            type="button"
            class="inline-flex h-10 shrink-0 items-center gap-2 rounded-md border border-rose-200 bg-white px-4 text-sm font-semibold text-rose-700 transition-colors hover:bg-rose-50 disabled:opacity-50"
            :disabled="saving"
            @click="deleteSelectedRows"
          >
            <Trash2 class="h-4 w-4" />
            Удалить ({{ selectedIds.size }})
          </button>
          <button
            type="button"
            class="inline-flex h-10 shrink-0 items-center gap-2 rounded-md border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50 disabled:opacity-50"
            :disabled="saving"
            @click="exportSelectedToCsv"
          >
            <FileDown class="h-4 w-4" />
            Экспортировать в CSV
          </button>
        </div>

        <button
          v-show="!hasRowSelection"
          type="button"
          class="inline-flex h-10 shrink-0 items-center gap-2 rounded-md border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50 disabled:opacity-50"
          :disabled="!table || saving"
          @click="showSettingsSheet = true"
        >
          <Pencil class="h-4 w-4" />
          Настройки таблицы
        </button>
      </div>

      <div
        ref="tableContainerRef"
        class="-mx-5 -mb-5 min-h-0 flex-1 min-w-0 border-t border-slate-100 bg-white overflow-auto overscroll-contain"
      >
        <Table
          :style="{
            width: `max(100%, ${recordsTable.getTotalSize()}px)`,
          }"
          wrapper-class="!overflow-visible !rounded-none !border-0 !bg-transparent !shadow-none"
        >
        <TableHeader class-name="[&_th]:shadow-[inset_0_-1px_0_0_rgb(226_232_240)]">
          <TableRow class-name="hover:bg-transparent">
            <TableHead
              v-for="header in recordsTable.getHeaderGroups()[0]?.headers ?? []"
              :key="header.id"
              :class-name="
                header.column.id === 'actions'
                  ? 'relative z-[12] select-none align-middle !bg-slate-50 sticky top-0 !px-1.5'
                  : 'relative z-[12] select-none align-middle !bg-slate-50 sticky top-0'
              "
              :style="{ width: `${header.getSize()}px`, minWidth: `${header.column.columnDef.minSize ?? 50}px` }"
            >
              <div
                v-if="header.column.id === 'actions'"
                class="flex items-center gap-1"
              >
                <span class="inline-flex w-4 shrink-0 justify-center">
                  <input
                    v-if="filteredRecords.length > 0"
                    type="checkbox"
                    class="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                    :checked="isAllRowsSelected"
                    @change="toggleSelectAllRows"
                  />
                </span>
                <!-- Та же ширина, что у кнопки «открыть» в строке — чекбокс ровно над чекбоксом -->
                <span
                  class="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md"
                  aria-hidden="true"
                />
                <span class="sr-only">Выбор строк</span>
              </div>
              <div v-else class="truncate px-1 py-0.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
                {{ columnHeaderLabel(header) }}
              </div>
              <div
                v-if="header.column.getCanResize()"
                class="absolute right-0 top-0 z-10 h-full w-1 cursor-col-resize touch-none select-none group/resize"
                :class="header.column.getIsResizing() ? 'bg-indigo-400' : 'hover:bg-indigo-300'"
                @dblclick="header.column.resetSize()"
                @mousedown="header.getResizeHandler()?.($event)"
                @touchstart="header.getResizeHandler()?.($event)"
              />
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-if="records.length === 0">
            <TableCell
              :colspan="emptyTableColspan"
              class-name="py-12 text-center text-sm text-slate-500"
            >
              Добавьте первую запись — таблица пока пустая.
            </TableCell>
          </TableRow>
          <TableRow v-else-if="filteredRecords.length === 0">
            <TableCell
              :colspan="emptyTableColspan"
              class-name="py-12 text-center text-sm text-slate-500"
            >
              Нет строк по текущим фильтрам. Измените условия или
              <button type="button" class="font-semibold text-indigo-600 hover:underline" @click="clearAllFilters">
                сбросьте фильтр
              </button>
              .
            </TableCell>
          </TableRow>
          <TableRow
            v-for="row in recordsTable.getRowModel().rows"
            :key="row.id"
            class-name="group"
          >
            <TableCell
              v-for="cell in row.getVisibleCells()"
              :key="cell.id"
              :class-name="
                cell.column.id === 'actions'
                  ? 'align-top !px-1.5 !text-xs leading-snug text-slate-800'
                  : 'align-top !text-xs leading-snug text-slate-800'
              "
              :style="{ width: `${cell.column.getSize()}px`, minWidth: `${cell.column.columnDef.minSize ?? 50}px` }"
            >
              <template v-if="cell.column.id === 'actions'">
                <div class="flex items-center gap-1">
                  <span class="inline-flex w-4 shrink-0 justify-center">
                    <input
                      type="checkbox"
                      class="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                      :checked="selectedIds.has(row.original.id)"
                      @click.stop
                      @change="toggleRowSelected(row.original.id)"
                    />
                  </span>
                  <TooltipProvider :delay-duration="300">
                    <Tooltip>
                      <TooltipTrigger as-child>
                        <button
                          type="button"
                          class="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md p-0 text-slate-400 opacity-100 transition-all hover:bg-indigo-50 hover:text-indigo-600 sm:opacity-0 sm:group-hover:opacity-100"
                          @click="openEditSheet(row.original)"
                        >
                          <MoveDiagonal2 class="h-4 w-4" aria-hidden="true" />
                          <span class="sr-only">Открыть запись</span>
                        </button>
                      </TooltipTrigger>
                      <TooltipContent side="top">Открыть запись</TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                </div>
              </template>
              <span v-else class="line-clamp-3 break-words">
                {{ cellDisplayValue(cell) }}
              </span>
            </TableCell>
          </TableRow>
        </TableBody>
        </Table>
      <p v-if="total > records.length" class="border-t border-slate-100 px-5 py-3 text-center text-xs text-slate-500">
        Показано {{ records.length }} из {{ total }}. Пагинация появится позже.
      </p>
      </div>
    </template>

  </div>

    <AddRowSheet
      :open="isAddSheetOpen"
      :columns="sheetColumns"
      :saving="saving"
      :row-save="handleAddRowSave"
      @update:open="isAddSheetOpen = $event"
    />

    <EditRowSheet
      ref="editRowSheetRef"
      :open="isEditSheetOpen"
      :columns="sheetColumns"
      :item="editSheetItem"
      :saving="saving"
      @update:open="onEditSheetOpenChange"
      @save="handleEditSave"
    />

    <TableSettingsSheet
      :is-open="showSettingsSheet"
      :table="table"
      :tables-api="tablesApiForSettings"
      @close="showSettingsSheet = false"
      @saved="onTableSettingsSaved"
    />

    <ImportCsvTableSheet
      :open="isImportSheetOpen"
      :table-id="tableId"
      :attributes="userEditableAttributes"
      :total-attribute-count="table?.attributes?.length ?? 0"
      :tables-api="tablesApiForCsvImport"
      @update:open="isImportSheetOpen = $event"
      @imported="onCsvImported"
    />
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useScroll } from '@vueuse/core'
import {
  useVueTable,
  getCoreRowModel,
  getSortedRowModel,
  type ColumnDef,
  type Header,
  type SortingState,
} from '@tanstack/vue-table'
import {
  ArrowDown,
  ArrowDownUp,
  ArrowUp,
  ChevronDown,
  Columns,
  FileDown,
  FileUp,
  Filter,
  List,
  Loader2,
  MoveDiagonal2,
  Pencil,
  Plus,
  Trash2,
} from 'lucide-vue-next'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '~/components/ui/tooltip'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '~/components/ui/dropdown-menu'
import { Switch } from '~/components/ui/switch'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '~/components/ui/table'
import { valueUpdater } from '~/lib/utils'
import { useToast } from '~/composables/useToast'
import { coercePayloadFromData as coerceTableRecordPayload } from '~/utils/tableCsvImport'
import AddRowSheet from './AddRowSheet.vue'
import EditRowSheet from './EditRowSheet.vue'
import ImportCsvTableSheet from './ImportCsvTableSheet.vue'
import TableSettingsSheet from './TableSettingsSheet.vue'
import type { DirectoryColumn, DirectoryItem } from '~/types/directories'
import type { TableAttribute, TableRead, TableRecordRead } from '~/types/tables'

/** В формах добавления/редактирования скрываем только системный id (строка задаётся на сервере). */
const TABLE_FORM_EXCLUDED = new Set(['id'])

const props = defineProps<{
  tableId: string
  tablesApi: {
    fetchTable: (id: string) => Promise<TableRead>
    fetchRecords: (id: string, opts?: { limit?: number; offset?: number }) => Promise<{
      items: TableRecordRead[]
      total: number
      limit: number
      offset: number
    }>
    createRecord: (tableId: string, data: Record<string, unknown>) => Promise<TableRecordRead>
    updateRecord: (tableId: string, recordId: string, data: Record<string, unknown>) => Promise<TableRecordRead>
    deleteRecord: (tableId: string, recordId: string) => Promise<void>
    updateTable: (id: string, p: { name?: string; description?: string | null }) => Promise<TableRead>
    createAttribute: (
      tableId: string,
      body: {
        name: string
        label: string
        attribute_type: string
        type_config?: Record<string, unknown>
        is_required?: boolean
        is_searchable?: boolean
        is_unique?: boolean
        order_index?: number
      }
    ) => Promise<TableAttribute>
    updateAttribute: (tableId: string, attributeId: string, body: Record<string, unknown>) => Promise<unknown>
    deleteAttribute: (tableId: string, attributeId: string) => Promise<void>
    reorderAttributes: (tableId: string, attributeIds: string[]) => Promise<void>
    bulkCreateRecords: (
      tableId: string,
      records: Record<string, unknown>[]
    ) => Promise<{ created: number; failed: number; errors: Record<string, unknown>[] }>
  }
}>()

const table = ref<TableRead | null>(null)
const records = ref<TableRecordRead[]>([])
const total = ref(0)
const loading = ref(true)
const error = ref<string | null>(null)
const saving = ref(false)

const showSettingsSheet = ref(false)
const isImportSheetOpen = ref(false)
const { success: toastSuccess, error: toastError } = useToast()

const selectedIds = ref<Set<string>>(new Set())
const hasRowSelection = computed(() => selectedIds.value.size > 0)

const toggleRowSelected = (id: string) => {
  const next = new Set(selectedIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selectedIds.value = next
}

const clearRowSelection = () => {
  selectedIds.value = new Set()
}

const escapeCsvField = (raw: string) => {
  if (/[",\n\r]/.test(raw)) return `"${raw.replace(/"/g, '""')}"`
  return raw
}

const sanitizeTableFileName = (name: string) =>
  name.replace(/[/\\?%*:|"<>]/g, '_').trim() || 'table'

const exportSelectedToCsv = () => {
  if (!table.value || selectedIds.value.size === 0) return
  const idList = [...selectedIds.value]
  const rows = records.value.filter((r) => idList.includes(r.id))
  if (rows.length === 0) return
  const cols = displayColumns.value
  const headerLine = cols.map((c) => escapeCsvField(c.label)).join(',')
  const lines = [headerLine]
  for (const rec of rows) {
    const cells = cols.map((attr) => {
      const v = rec.data[attr.name]
      return escapeCsvField(formatCell(v, attr))
    })
    lines.push(cells.join(','))
  }
  const blob = new Blob(['\uFEFF', lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${sanitizeTableFileName(table.value.name)}_export.csv`
  a.click()
  URL.revokeObjectURL(url)
  toastSuccess(`Экспорт: ${rows.length} строк`)
}

const deleteSelectedRows = async () => {
  const ids = [...selectedIds.value]
  if (ids.length === 0) return
  if (!confirm(`Удалить выбранные записи (${ids.length})? Это действие нельзя отменить.`)) return
  saving.value = true
  try {
    for (const id of ids) {
      await props.tablesApi.deleteRecord(props.tableId, id)
    }
    clearRowSelection()
    await load({ showLoading: false })
    toastSuccess(`Удалено записей: ${ids.length}`)
  } catch (e: any) {
    toastError(e?.message ?? 'Не удалось удалить записи')
  } finally {
    saving.value = false
  }
}

const tablesApiForSettings = computed(() => ({
  updateTable: props.tablesApi.updateTable,
  createAttribute: props.tablesApi.createAttribute,
  updateAttribute: props.tablesApi.updateAttribute,
  deleteAttribute: props.tablesApi.deleteAttribute,
  reorderAttributes: props.tablesApi.reorderAttributes,
}))

const tablesApiForCsvImport = computed(() => ({
  createAttribute: props.tablesApi.createAttribute,
  bulkCreateRecords: props.tablesApi.bulkCreateRecords,
}))

const onTableSettingsSaved = async () => {
  await load({ showLoading: false })
}

const isAddSheetOpen = ref(false)
const isEditSheetOpen = ref(false)
const editingRecord = ref<TableRecordRead | null>(null)
const editRowSheetRef = ref<InstanceType<typeof EditRowSheet> | null>(null)
const tableContainerRef = ref<HTMLElement | null>(null)
const { y: tableScrollY } = useScroll(tableContainerRef)
const isToolbarVisible = computed(() => tableScrollY.value < 10)

const mapAttributeToSheetColumn = (attr: TableAttribute): DirectoryColumn => {
  const base = { name: attr.name, label: attr.label, required: attr.is_required }
  switch (attr.attribute_type) {
    case 'integer':
    case 'float':
      return { ...base, type: 'number' }
    case 'boolean':
      return { ...base, type: 'bool' }
    case 'date':
      return { ...base, type: 'date' }
    case 'datetime':
    case 'timestamp':
      return { ...base, type: 'datetime' }
    case 'text':
      return { ...base, type: 'textarea' }
    case 'varchar': {
      const maxLength = typeof attr.type_config?.max_length === 'number' ? attr.type_config.max_length : 256
      return { ...base, type: 'text', maxLength }
    }
    default:
      return { ...base, type: 'text' }
  }
}

const sheetColumns = computed<DirectoryColumn[]>(() =>
  userEditableAttributes.value.map(mapAttributeToSheetColumn)
)

const editSheetItem = computed<DirectoryItem | null>(() => {
  if (!editingRecord.value) return null
  return { id: editingRecord.value.id, data: editingRecord.value.data }
})

const displayColumns = computed(() => {
  const attrs = table.value?.attributes ?? []
  return [...attrs].sort((a, b) => a.order_index - b.order_index)
})

const userEditableAttributes = computed(() =>
  displayColumns.value.filter((a) => !TABLE_FORM_EXCLUDED.has(a.name))
)

const getDefaultColSize = (attr: TableAttribute): number => {
  switch (attr.attribute_type) {
    case 'boolean':
      return 88
    case 'integer':
    case 'float':
      return 104
    case 'date':
    case 'datetime':
    case 'timestamp':
      return 128
    case 'varchar':
      return 200
    default:
      return 160
  }
}

const formatCell = (value: unknown, attr: TableAttribute): string => {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? 'Да' : 'Нет'
  if (typeof value === 'object') return JSON.stringify(value)
  if (attr.attribute_type === 'date' && typeof value === 'string' && value) {
    const m = /^(\d{4}-\d{2}-\d{2})/.exec(value)
    return m ? m[1] : value
  }
  if (
    (attr.attribute_type === 'datetime' || attr.attribute_type === 'timestamp') &&
    typeof value === 'string' &&
    value
  ) {
    const d = new Date(value)
    return Number.isNaN(d.getTime()) ? value : d.toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' })
  }
  return String(value)
}

const compareCellValues = (a: unknown, b: unknown, attr: TableAttribute): number => {
  const nullish = (v: unknown) => v === null || v === undefined
  if (nullish(a) && nullish(b)) return 0
  if (nullish(a)) return 1
  if (nullish(b)) return -1
  switch (attr.attribute_type) {
    case 'integer':
    case 'float': {
      const na = Number(a)
      const nb = Number(b)
      const aNaN = Number.isNaN(na)
      const bNaN = Number.isNaN(nb)
      if (aNaN && bNaN) return 0
      if (aNaN) return 1
      if (bNaN) return -1
      if (na === nb) return 0
      return na < nb ? -1 : 1
    }
    case 'boolean': {
      const ba = Boolean(a)
      const bb = Boolean(b)
      if (ba === bb) return 0
      return ba ? 1 : -1
    }
    case 'date':
    case 'datetime':
    case 'timestamp': {
      const ta = new Date(String(a)).getTime()
      const tb = new Date(String(b)).getTime()
      const fa = Number.isFinite(ta) ? ta : 0
      const fb = Number.isFinite(tb) ? tb : 0
      if (fa === fb) return 0
      return fa < fb ? -1 : 1
    }
    default: {
      const sa = formatCell(a, attr).toLowerCase()
      const sb = formatCell(b, attr).toLowerCase()
      if (sa === sb) return 0
      return sa < sb ? -1 : 1
    }
  }
}

type TableFilterOperator =
  | 'contains'
  | 'not_contains'
  | 'equals'
  | 'gt'
  | 'lt'
  | 'gte'
  | 'lte'
  | 'is_empty'
  | 'is_not_empty'

type TableFilterCombineMode = 'and' | 'or'

type TableFilterRule = {
  uid: string
  columnName: string
  operator: TableFilterOperator
  value: string
}

let filterUidSeq = 0
const newFilterUid = () => `flt-${++filterUidSeq}`

const filterMenuOpen = ref(false)
const filterDraft = ref<TableFilterRule[]>([])
const appliedFilters = ref<TableFilterRule[]>([])
const filterCombineDraft = ref<TableFilterCombineMode>('and')
const appliedFilterCombineMode = ref<TableFilterCombineMode>('and')

const hasActiveFilters = computed(() => appliedFilters.value.length > 0)

watch(filterMenuOpen, (open) => {
  if (open) {
    filterDraft.value =
      appliedFilters.value.length > 0
        ? appliedFilters.value.map((r) => ({ ...r }))
        : []
    filterCombineDraft.value = appliedFilterCombineMode.value
  }
})

type TableSortRule = {
  uid: string
  columnName: string
  ascending: boolean
}

let sortUidSeq = 0
const newSortUid = () => `srt-${++sortUidSeq}`

const sortMenuOpen = ref(false)
const sortDraft = ref<TableSortRule[]>([])
const appliedSortRules = ref<TableSortRule[]>([])
const tableSorting = ref<SortingState>([])
const sortColumnPickerKey = ref(0)

const hasActiveSort = computed(() => appliedSortRules.value.length > 0)

const sortColumnsAvailableForPick = computed(() => {
  const used = new Set(sortDraft.value.map((r) => r.columnName))
  return displayColumns.value.filter((a) => !used.has(a.name))
})

watch(sortMenuOpen, (open) => {
  if (open) {
    sortDraft.value =
      appliedSortRules.value.length > 0
        ? appliedSortRules.value.map((r) => ({ ...r }))
        : []
  }
})

watch(
  () => props.tableId,
  () => {
    appliedFilters.value = []
    filterDraft.value = []
    filterCombineDraft.value = 'and'
    appliedFilterCombineMode.value = 'and'
    filterMenuOpen.value = false
    appliedSortRules.value = []
    sortDraft.value = []
    sortMenuOpen.value = false
    tableSorting.value = []
    sortColumnPickerKey.value++
  }
)

const onSortColumnPicked = (ev: Event) => {
  const el = ev.target as HTMLSelectElement
  const name = el.value
  if (!name) return
  sortDraft.value = [
    ...sortDraft.value,
    { uid: newSortUid(), columnName: name, ascending: true },
  ]
  sortColumnPickerKey.value++
}

const addSortRow = () => {
  const pick = sortColumnsAvailableForPick.value[0]
  if (!pick) return
  sortDraft.value = [
    ...sortDraft.value,
    { uid: newSortUid(), columnName: pick.name, ascending: true },
  ]
}

const removeSortRow = (uid: string) => {
  sortDraft.value = sortDraft.value.filter((r) => r.uid !== uid)
}

const applySortDraft = () => {
  const seen = new Set<string>()
  const deduped: TableSortRule[] = []
  for (const r of sortDraft.value) {
    if (!r.columnName || seen.has(r.columnName)) continue
    seen.add(r.columnName)
    deduped.push({ uid: r.uid, columnName: r.columnName, ascending: r.ascending })
  }
  appliedSortRules.value = deduped
  tableSorting.value = deduped.map((r) => ({
    id: r.columnName,
    desc: !r.ascending,
  }))
  sortMenuOpen.value = false
}

const clearAllSorts = () => {
  sortDraft.value = []
  appliedSortRules.value = []
  tableSorting.value = []
  sortColumnPickerKey.value++
}

const addFilterRow = () => {
  const cols = displayColumns.value
  const first = cols[0]
  filterDraft.value = [
    ...filterDraft.value,
    {
      uid: newFilterUid(),
      columnName: first?.name ?? '',
      operator: 'contains',
      value: '',
    },
  ]
}

const removeFilterRow = (uid: string) => {
  filterDraft.value = filterDraft.value.filter((r) => r.uid !== uid)
}

const applyFilterDraft = () => {
  appliedFilters.value = filterDraft.value
    .filter((r) => {
      if (!r.columnName) return false
      if (r.operator === 'is_empty' || r.operator === 'is_not_empty') return true
      return r.value.trim() !== ''
    })
    .map((r) => ({ ...r, uid: r.uid }))
  appliedFilterCombineMode.value = filterCombineDraft.value
  filterMenuOpen.value = false
}

const clearAllFilters = () => {
  filterDraft.value = []
  appliedFilters.value = []
  filterCombineDraft.value = 'and'
  appliedFilterCombineMode.value = 'and'
}

const parseBooleanFilterNeedle = (s: string): number | null => {
  const x = s.trim().toLowerCase()
  if (['да', 'yes', 'true', '1', 'д'].includes(x)) return 1
  if (['нет', 'no', 'false', '0', 'н'].includes(x)) return 0
  return null
}

const cellNumericForFilter = (raw: unknown, attr: TableAttribute): number | null => {
  if (raw === null || raw === undefined) return null
  if (attr.attribute_type === 'integer' || attr.attribute_type === 'float') {
    const n = Number(raw)
    return Number.isFinite(n) ? n : null
  }
  if (
    attr.attribute_type === 'date' ||
    attr.attribute_type === 'datetime' ||
    attr.attribute_type === 'timestamp'
  ) {
    const ms = new Date(String(raw)).getTime()
    return Number.isFinite(ms) ? ms : null
  }
  if (attr.attribute_type === 'boolean') {
    return raw === true || raw === 'true' || raw === 1 || raw === '1' || raw === 'да' ? 1 : 0
  }
  const n = Number(String(raw).replace(',', '.'))
  return Number.isFinite(n) ? n : null
}

const needleNumericForFilter = (needle: string, attr: TableAttribute): number | null => {
  const t = needle.trim()
  if (!t) return null
  if (attr.attribute_type === 'boolean') return parseBooleanFilterNeedle(t)
  if (attr.attribute_type === 'integer' || attr.attribute_type === 'float') {
    const n = Number(t.replace(',', '.'))
    return Number.isFinite(n) ? n : null
  }
  if (
    attr.attribute_type === 'date' ||
    attr.attribute_type === 'datetime' ||
    attr.attribute_type === 'timestamp'
  ) {
    const ms = new Date(t).getTime()
    return Number.isFinite(ms) ? ms : null
  }
  const n = Number(t.replace(',', '.'))
  return Number.isFinite(n) ? n : null
}

const orderingOpMatches = (cmp: number, op: 'gt' | 'lt' | 'gte' | 'lte'): boolean => {
  if (op === 'gt') return cmp > 0
  if (op === 'lt') return cmp < 0
  if (op === 'gte') return cmp >= 0
  return cmp <= 0
}

const isCellEmptyForFilter = (raw: unknown, _attr: TableAttribute): boolean => {
  if (raw === null || raw === undefined) return true
  if (typeof raw === 'string' && raw.trim() === '') return true
  return false
}

const rowMatchesFilterRule = (raw: unknown, attr: TableAttribute, rule: TableFilterRule): boolean => {
  if (rule.operator === 'is_empty') {
    return isCellEmptyForFilter(raw, attr)
  }
  if (rule.operator === 'is_not_empty') {
    return !isCellEmptyForFilter(raw, attr)
  }

  const needleRaw = rule.value.trim()
  if (needleRaw === '') return true

  if (rule.operator === 'contains' || rule.operator === 'not_contains' || rule.operator === 'equals') {
    const cellStr = formatCell(raw, attr).toLowerCase()
    const needle = needleRaw.toLowerCase()
    if (rule.operator === 'equals') return cellStr === needle
    if (rule.operator === 'not_contains') return !cellStr.includes(needle)
    return cellStr.includes(needle)
  }

  const op = rule.operator
  const isOrdering = op === 'gt' || op === 'lt' || op === 'gte' || op === 'lte'
  if (!isOrdering) return true

  if (
    attr.attribute_type === 'integer' ||
    attr.attribute_type === 'float' ||
    attr.attribute_type === 'date' ||
    attr.attribute_type === 'datetime' ||
    attr.attribute_type === 'timestamp' ||
    attr.attribute_type === 'boolean'
  ) {
    const a = cellNumericForFilter(raw, attr)
    const b = needleNumericForFilter(needleRaw, attr)
    if (b === null) return false
    if (a === null) return false
    return orderingOpMatches(a - b, op)
  }

  const sa = formatCell(raw, attr).toLowerCase()
  const sb = needleRaw.toLowerCase()
  const cmp = sa < sb ? -1 : sa > sb ? 1 : 0
  return orderingOpMatches(cmp, op)
}

const filteredRecords = computed(() => {
  const list = records.value
  const rules = appliedFilters.value
  if (rules.length === 0) return list
  const mode = appliedFilterCombineMode.value
  return list.filter((row) => {
    const matches: boolean[] = []
    for (const rule of rules) {
      const attr = displayColumns.value.find((a) => a.name === rule.columnName)
      if (!attr) continue
      const raw = row.data[attr.name]
      matches.push(rowMatchesFilterRule(raw, attr, rule))
    }
    if (matches.length === 0) return true
    return mode === 'or' ? matches.some(Boolean) : matches.every(Boolean)
  })
})

const isAllRowsSelected = computed(
  () =>
    filteredRecords.value.length > 0 &&
    filteredRecords.value.every((r) => selectedIds.value.has(r.id))
)

const toggleSelectAllRows = () => {
  const ids = filteredRecords.value.map((r) => r.id)
  if (ids.length === 0) return
  const allSelected = ids.every((id) => selectedIds.value.has(id))
  const next = new Set(selectedIds.value)
  if (allSelected) for (const id of ids) next.delete(id)
  else for (const id of ids) next.add(id)
  selectedIds.value = next
}

const actionsColumnDef: ColumnDef<TableRecordRead, unknown> = {
  id: 'actions',
  accessorFn: () => null,
  header: '',
  size: 68,
  minSize: 62,
  maxSize: 88,
  enableResizing: false,
  enableSorting: false,
}

const tanstackColumns = computed<ColumnDef<TableRecordRead, unknown>[]>(() => {
  const attrCols: ColumnDef<TableRecordRead, unknown>[] = displayColumns.value.map((attr) => ({
    id: attr.name,
    accessorFn: (row: TableRecordRead) => row.data[attr.name],
    header: attr.label,
    meta: { attr },
    size: getDefaultColSize(attr),
    minSize: 48,
    maxSize: 800,
    sortingFn: (rowA, rowB) =>
      compareCellValues(rowA.original.data[attr.name], rowB.original.data[attr.name], attr),
  }))
  const idIdx = attrCols.findIndex((c) => c.id === 'id')
  if (idIdx >= 0) {
    return [...attrCols.slice(0, idIdx), actionsColumnDef, ...attrCols.slice(idIdx)]
  }
  return [actionsColumnDef, ...attrCols]
})

const recordsTable = useVueTable({
  get data() {
    return filteredRecords.value
  },
  get columns() {
    return tanstackColumns.value
  },
  columnResizeMode: 'onChange',
  enableColumnResizing: true,
  state: {
    get sorting() {
      return tableSorting.value
    },
  },
  onSortingChange: (updater) => valueUpdater(updater, tableSorting),
  getCoreRowModel: getCoreRowModel(),
  getSortedRowModel: getSortedRowModel(),
  getRowId: (row) => row.id,
})

const emptyTableColspan = computed(() => Math.max(1, recordsTable.getAllColumns().length))

const columnHeaderLabel = (header: Header<TableRecordRead, unknown>) => {
  const h = header.column.columnDef.header
  return typeof h === 'string' ? h : ''
}

const attrForDataCell = (cell: { column: { columnDef: { meta?: unknown }; id: string } }) => {
  const meta = cell.column.columnDef.meta as { attr?: TableAttribute } | undefined
  const fromMeta = meta?.attr
  if (fromMeta) return fromMeta
  return displayColumns.value.find((a) => a.name === cell.column.id)
}

const cellDisplayValue = (cell: {
  getValue: () => unknown
  column: { columnDef: { meta?: unknown }; id: string }
}) => {
  const attr = attrForDataCell(cell)
  if (!attr) return String(cell.getValue() ?? '—')
  return formatCell(cell.getValue(), attr)
}

const load = async (opts?: { showLoading?: boolean }) => {
  const showLoading = opts?.showLoading !== false
  if (showLoading) loading.value = true
  error.value = null
  try {
    table.value = await props.tablesApi.fetchTable(props.tableId)
    const res = await props.tablesApi.fetchRecords(props.tableId, { limit: 100, offset: 0 })
    records.value = res.items
    total.value = res.total
    clearRowSelection()
  } catch (e: any) {
    error.value = e?.message ?? 'Не удалось загрузить таблицу'
    table.value = null
    records.value = []
    clearRowSelection()
  } finally {
    if (showLoading) loading.value = false
  }
}

onMounted(async () => {
  await load()
})

watch(
  () => props.tableId,
  async () => {
    await load()
  }
)

const coercePayloadFromData = (data: Record<string, unknown>): Record<string, unknown> =>
  coerceTableRecordPayload(data, userEditableAttributes.value)

const openSettingsForNewColumn = () => {
  nextTick(() => {
    nextTick(() => {
      showSettingsSheet.value = true
    })
  })
}

const openImportSheet = () => {
  nextTick(() => {
    nextTick(() => {
      isImportSheetOpen.value = true
    })
  })
}

const onCsvImported = async () => {
  await load({ showLoading: false })
  toastSuccess('Таблица обновлена', 'Импорт CSV применён.')
}

const handleAddRowSave = async (data: Record<string, unknown>) => {
  saving.value = true
  try {
    const payload = coercePayloadFromData(data)
    await props.tablesApi.createRecord(props.tableId, payload)
    await load({ showLoading: false })
  } finally {
    saving.value = false
  }
}

/** После пункта dropdown: даём меню закрыться, иначе body остаётся с pointer-events: none */
const openAddSheet = () => {
  nextTick(() => {
    nextTick(() => {
      isAddSheetOpen.value = true
    })
  })
}

const openEditSheet = (rec: TableRecordRead) => {
  editingRecord.value = rec
  isEditSheetOpen.value = true
}

const onEditSheetOpenChange = (open: boolean) => {
  isEditSheetOpen.value = open
  if (!open) editingRecord.value = null
}

const handleEditSave = async (itemId: string, data: Record<string, unknown>) => {
  saving.value = true
  try {
    const payload = coercePayloadFromData(data)
    await props.tablesApi.updateRecord(props.tableId, itemId, payload)
    await load({ showLoading: false })
    isEditSheetOpen.value = false
    editingRecord.value = null
  } catch (e: any) {
    editRowSheetRef.value?.setError(e?.message ?? 'Ошибка сохранения')
  } finally {
    saving.value = false
  }
}

</script>
