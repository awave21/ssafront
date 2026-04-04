<template>
  <div class="space-y-6">
    <div class="bg-white rounded-lg border border-slate-200 p-6 shadow-sm space-y-6">
      <Tabs v-model:value="activeTab">
        <TabsList className="bg-slate-50/70 p-1 rounded-xl">
          <TabsTrigger value="tools">Инструменты</TabsTrigger>
          <TabsTrigger value="all-records">Все записи</TabsTrigger>
          <TabsTrigger value="services">Услуги</TabsTrigger>
          <TabsTrigger value="specialists">Специалисты</TabsTrigger>
          <TabsTrigger value="categories">Категории</TabsTrigger>
        </TabsList>

        <TabsContent value="tools">
          <div class="p-6 border border-slate-200 rounded-lg bg-white space-y-6">
            <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <h3 class="text-lg font-bold text-slate-900">SQNS Инструменты</h3>
                <p class="text-sm text-slate-500 mt-1">
                  Управляйте доступными инструментами и их описаниями для ИИ-агента.
                </p>
              </div>
              <div class="relative">
                <Search class="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                <input
                  v-model="toolSearch"
                  type="text"
                  placeholder="Поиск инструментов..."
                  class="pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all w-64"
                />
              </div>
            </div>

            <div v-if="filteredTools.length === 0" class="py-12 text-center text-slate-400 italic border-2 border-dashed border-slate-100 rounded-xl">
              Инструменты не найдены
            </div>

            <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div
                v-for="tool in filteredTools"
                :key="tool.name"
                class="group relative bg-white border border-slate-200 rounded-xl p-5 hover:border-indigo-300 hover:shadow-md transition-all duration-300"
              >
                <div class="flex items-start justify-between gap-4">
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 mb-1">
                      <h4 class="font-bold text-slate-900 truncate">{{ tool.displayName || tool.name }}</h4>
                      <div
                        v-if="tool.isEnabled"
                        class="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]"
                      ></div>
                    </div>
                    <p class="text-[10px] font-mono text-slate-400 mb-3 uppercase tracking-wider">{{ tool.name }}</p>
                    <p class="text-sm text-slate-600 line-clamp-2 min-h-[2.5rem] leading-relaxed">
                      {{ tool.description || 'Описание не задано' }}
                    </p>
                  </div>
                  <div class="flex flex-col items-end gap-3">
                    <Switch
                      :model-value="tool.isEnabled"
                      :disabled="pendingToolNames.has(tool.name)"
                      @update:model-value="(val) => handleToggleTool(tool, val)"
                    />
                  </div>
                </div>

                <div class="mt-4 pt-4 border-t border-slate-50 flex items-center justify-between gap-4">
                  <div class="flex flex-wrap gap-1">
                    <span
                      v-for="field in tool.requiredFields"
                      :key="field"
                      class="px-2 py-0.5 bg-slate-100 text-slate-500 rounded text-[10px] font-medium"
                    >
                      {{ field }}
                    </span>
                  </div>
                  <button
                    @click="openToolEditor(tool)"
                    class="text-xs font-bold text-indigo-600 hover:text-indigo-800 flex items-center gap-1 transition-colors"
                  >
                    <Pencil class="w-3 h-3" />
                    Настроить
                  </button>
                </div>

                <div
                  v-if="pendingToolNames.has(tool.name)"
                  class="absolute inset-0 bg-white/60 backdrop-blur-[1px] rounded-xl flex items-center justify-center z-10"
                >
                  <Loader2 class="w-6 h-6 animate-spin text-indigo-600" />
                </div>
              </div>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="all-records">
          <div class="space-y-0.5 border border-slate-200 rounded-lg overflow-hidden">
            <div class="p-6 border-b border-slate-100 space-y-4">
              <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                  <h3 class="text-lg font-bold text-slate-900">Все записи SQNS</h3>
                  <p class="text-sm text-slate-500 mt-1">
                    Плоский список связей: услуга, сотрудник, категория и дата обновления.
                  </p>
                </div>
                <div class="relative">
                  <Search class="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                  <Input
                    v-model="allRecordsSearch"
                    placeholder="Поиск по услуге, сотруднику, категории..."
                    class="pl-9 w-72"
                  />
                </div>
              </div>
            </div>
            <Table wrapper-class="rounded-none border-0 bg-transparent">
              <TableHeader>
                <TableRow>
                  <TableHead>
                    <button @click="toggleSort(allRecordsTable, 'service')" class="inline-flex items-center gap-1.5 hover:text-slate-900 transition-colors">
                      Услуга
                      <ArrowUpDown class="h-3.5 w-3.5 text-slate-400" />
                    </button>
                  </TableHead>
                  <TableHead>
                    <button @click="toggleSort(allRecordsTable, 'employee')" class="inline-flex items-center gap-1.5 hover:text-slate-900 transition-colors">
                      Сотрудник
                      <ArrowUpDown class="h-3.5 w-3.5 text-slate-400" />
                    </button>
                  </TableHead>
                  <TableHead>
                    <button @click="toggleSort(allRecordsTable, 'category')" class="inline-flex items-center gap-1.5 hover:text-slate-900 transition-colors">
                      Категория
                      <ArrowUpDown class="h-3.5 w-3.5 text-slate-400" />
                    </button>
                  </TableHead>
                  <TableHead>
                    <button @click="toggleSort(allRecordsTable, 'updated_at')" class="inline-flex items-center gap-1.5 hover:text-slate-900 transition-colors">
                      Дата обновления
                      <ArrowUpDown class="h-3.5 w-3.5 text-slate-400" />
                    </button>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow v-if="isAllRecordsLoading" v-for="i in 8" :key="`all-records-skel-${i}`" class="animate-pulse">
                  <TableCell><div class="h-4 w-48 bg-slate-100 rounded"></div></TableCell>
                  <TableCell><div class="h-4 w-48 bg-slate-100 rounded"></div></TableCell>
                  <TableCell><div class="h-4 w-32 bg-slate-100 rounded"></div></TableCell>
                  <TableCell><div class="h-4 w-36 bg-slate-100 rounded"></div></TableCell>
                </TableRow>
                <TableRow v-else-if="filteredAllRecords.length === 0">
                  <TableCell :colspan="4" className="p-12 text-center text-slate-400 italic">
                    Записи не найдены
                  </TableCell>
                </TableRow>
                <TableRow v-else v-for="(row, index) in pagedAllRecords" :key="`${row.service}-${row.employee}-${index}`">
                  <TableCell className="font-medium text-slate-900">{{ row.service }}</TableCell>
                  <TableCell>{{ row.employee || '—' }}</TableCell>
                  <TableCell>{{ row.category || 'Без категории' }}</TableCell>
                  <TableCell>{{ formatRecordUpdatedAt(row.updated_at) }}</TableCell>
                </TableRow>
              </TableBody>
            </Table>
            <div class="p-4 border-t border-slate-100 bg-slate-50/30 flex items-center justify-between gap-4">
              <div class="flex items-center gap-2">
                <span class="text-xs text-slate-500">Записей на странице:</span>
                <select
                  v-model.number="allRecordsPageSize"
                  class="px-2 py-1 bg-white border border-slate-200 rounded text-xs focus:ring-1 focus:ring-indigo-500 transition-all"
                >
                  <option :value="25">25</option>
                  <option :value="50">50</option>
                  <option :value="100">100</option>
                  <option :value="250">250</option>
                </select>
              </div>
              <p class="text-xs text-slate-500">
                {{ allRecordsPageOffset + 1 }}–{{ Math.min(allRecordsPageOffset + allRecordsPageSize, filteredAllRecords.length) }}
                из {{ filteredAllRecords.length }}
                <span v-if="filteredAllRecords.length !== allRecordsTotal">(всего {{ allRecordsTotal }})</span>
              </p>
              <div class="flex items-center gap-2">
                <button
                  @click="allRecordsPageOffset = Math.max(0, allRecordsPageOffset - allRecordsPageSize)"
                  :disabled="allRecordsPageOffset === 0"
                  class="p-2 rounded-lg hover:bg-white hover:shadow-sm disabled:opacity-30 transition-all"
                >
                  <ChevronLeft class="h-4 w-4" />
                </button>
                <span class="text-xs font-bold text-slate-700">Страница {{ allRecordsCurrentPage }}</span>
                <button
                  @click="allRecordsPageOffset += allRecordsPageSize"
                  :disabled="allRecordsPageOffset + allRecordsPageSize >= filteredAllRecords.length"
                  class="p-2 rounded-lg hover:bg-white hover:shadow-sm disabled:opacity-30 transition-all"
                >
                  <ChevronRight class="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="services">
          <div class="space-y-0.5 border border-slate-200 rounded-lg overflow-hidden">
            <div class="p-6 border-b border-slate-100 space-y-4">
              <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <h3 class="text-lg font-bold text-slate-900">Управление услугами</h3>
                <div class="flex flex-wrap items-center gap-3">
                  <div class="relative">
                    <Search class="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                    <input
                      v-model="filters.search"
                      type="text"
                      placeholder="Поиск услуг..."
                      class="pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all w-64"
                    />
                  </div>

                  <select
                    v-model="filters.category"
                    class="px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all"
                  >
                    <option :value="null">Все категории</option>
                    <option v-for="cat in categories" :key="cat.id" :value="cat.name">
                      {{ cat.name }}
                    </option>
                  </select>

                  <label class="flex items-center gap-2 cursor-pointer">
                    <input
                      v-model="filters.is_enabled"
                      type="checkbox"
                      class="w-4 h-4 text-indigo-600 border-slate-300 rounded focus:ring-indigo-500"
                    />
                    <span class="text-sm text-slate-600">Только включенные</span>
                  </label>
                </div>
              </div>
            </div>

            <Transition
              enter-active-class="transition duration-200 ease-out"
              enter-from-class="transform -translate-y-2 opacity-0"
              enter-to-class="transform translate-y-0 opacity-100"
              leave-active-class="transition duration-150 ease-in"
              leave-from-class="transform translate-y-0 opacity-100"
              leave-to-class="transform -translate-y-2 opacity-0"
            >
              <div v-if="selectedIds.length > 0" class="bg-indigo-50 px-6 py-3 border-b border-indigo-100 flex items-center justify-between">
                <div class="flex items-center gap-4">
                  <span class="text-sm font-bold text-indigo-700">Выбрано: {{ selectedIds.length }}</span>
                  <div class="h-4 w-px bg-indigo-200"></div>
                  <div class="flex items-center gap-2">
                    <button
                      type="button"
                      :disabled="bulkServicesInFlight"
                      @click="handleBulkUpdate(true)"
                      class="text-xs font-bold text-indigo-600 hover:text-indigo-800 transition-colors disabled:opacity-40 disabled:pointer-events-none"
                    >
                      Включить выбранные
                    </button>
                    <button
                      type="button"
                      :disabled="bulkServicesInFlight"
                      @click="handleBulkUpdate(false)"
                      class="text-xs font-bold text-red-600 hover:text-red-800 transition-colors disabled:opacity-40 disabled:pointer-events-none"
                    >
                      Отключить выбранные
                    </button>
                  </div>
                </div>
                <button
                  type="button"
                  :disabled="bulkServicesInFlight"
                  @click="selectedIds = []"
                  class="text-xs font-medium text-slate-500 hover:text-slate-700 disabled:opacity-40"
                >
                  Сбросить выбор
                </button>
              </div>
            </Transition>

            <Table wrapper-class="rounded-none border-0 bg-transparent">
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-10">
                      <input
                        type="checkbox"
                        :checked="isAllSelected"
                        @change="toggleSelectAll"
                        class="w-4 h-4 text-indigo-600 border-slate-300 rounded focus:ring-indigo-500"
                      />
                    </TableHead>
                    <TableHead>
                      <button @click="toggleSort(servicesTable, 'name')" class="inline-flex items-center gap-1.5 hover:text-slate-900 transition-colors">
                        Услуга
                        <ArrowUpDown class="h-3.5 w-3.5 text-slate-400" />
                      </button>
                    </TableHead>
                    <TableHead>
                      <button @click="toggleSort(servicesTable, 'category')" class="inline-flex items-center gap-1.5 hover:text-slate-900 transition-colors">
                        Категория
                        <ArrowUpDown class="h-3.5 w-3.5 text-slate-400" />
                      </button>
                    </TableHead>
                    <TableHead>
                      <button @click="toggleSort(servicesTable, 'price')" class="inline-flex items-center gap-1.5 hover:text-slate-900 transition-colors">
                        Цена
                        <ArrowUpDown class="h-3.5 w-3.5 text-slate-400" />
                      </button>
                    </TableHead>
                    <TableHead>
                      <button @click="toggleSort(servicesTable, 'duration')" class="inline-flex items-center gap-1.5 hover:text-slate-900 transition-colors">
                        Длительность
                        <ArrowUpDown class="h-3.5 w-3.5 text-slate-400" />
                      </button>
                    </TableHead>
                    <TableHead>
                      <button @click="toggleSort(servicesTable, 'status')" class="inline-flex items-center gap-1.5 hover:text-slate-900 transition-colors">
                        Статус
                        <ArrowUpDown class="h-3.5 w-3.5 text-slate-400" />
                      </button>
                    </TableHead>
                    <TableHead className="w-24">
                      <button @click="toggleSort(servicesTable, 'priority')" class="inline-flex items-center gap-1.5 hover:text-slate-900 transition-colors">
                        Приоритет
                        <ArrowUpDown class="h-3.5 w-3.5 text-slate-400" />
                      </button>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow v-if="isLoading" v-for="i in 5" :key="`skeleton-${i}`" class="animate-pulse">
                    <TableCell><div class="h-4 w-4 bg-slate-100 rounded"></div></TableCell>
                    <TableCell><div class="h-4 w-48 bg-slate-100 rounded"></div></TableCell>
                    <TableCell><div class="h-4 w-24 bg-slate-100 rounded"></div></TableCell>
                    <TableCell><div class="h-4 w-16 bg-slate-100 rounded"></div></TableCell>
                    <TableCell><div class="h-4 w-16 bg-slate-100 rounded"></div></TableCell>
                    <TableCell><div class="h-6 w-10 bg-slate-100 rounded-full"></div></TableCell>
                    <TableCell><div class="h-8 w-16 bg-slate-100 rounded"></div></TableCell>
                  </TableRow>
                  <TableRow v-else-if="services.length === 0">
                    <TableCell :colspan="7" className="p-12 text-center text-slate-400 italic">
                      Услуги не найдены
                    </TableCell>
                  </TableRow>
                  <TableRow
                    v-else
                    v-for="service in sortedServices"
                    :key="`${serviceIdKey(service.id)}-${service.is_enabled ? 1 : 0}`"
                    :class="[
                      'hover:bg-slate-50/50 transition-colors',
                      isServiceRowSelected(service.id) ? 'bg-indigo-50/20' : ''
                    ]"
                  >
                    <TableCell>
                      <input
                        type="checkbox"
                        :checked="isServiceRowSelected(service.id)"
                        @change="toggleSelect(service.id)"
                        class="w-4 h-4 text-indigo-600 border-slate-300 rounded focus:ring-indigo-500"
                      />
                    </TableCell>
                    <TableCell>
                      <p class="text-sm font-bold text-slate-900">{{ service.name }}</p>
                      <p v-if="service.description" class="text-[10px] text-slate-500 mt-0.5 line-clamp-1">{{ service.description }}</p>
                    </TableCell>
                    <TableCell>
                      <span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium bg-slate-100 text-slate-600">
                        {{ service.category || 'Без категории' }}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span class="text-sm font-mono text-slate-600">{{ service.price_range || '—' }} ₽</span>
                    </TableCell>
                    <TableCell>
                      <span class="text-sm text-slate-600">{{ service.duration }} мин</span>
                    </TableCell>
                    <TableCell>
                      <button
                        @click="handleToggleService(service)"
                        class="relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none"
                        :class="[service.is_enabled ? 'bg-emerald-500' : 'bg-slate-200']"
                      >
                        <span
                          aria-hidden="true"
                          class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200 ease-in-out"
                          :class="[service.is_enabled ? 'translate-x-4' : 'translate-x-0']"
                        />
                      </button>
                    </TableCell>
                    <TableCell>
                      <input
                        type="number"
                        v-model.number="service.priority"
                        @blur="handleUpdatePriority(service)"
                        @keyup.enter="handleUpdatePriority(service)"
                        class="w-16 px-2 py-1 bg-slate-50 border border-slate-200 rounded text-xs font-mono focus:ring-1 focus:ring-indigo-500 focus:bg-white transition-all"
                        min="0"
                        max="100"
                      />
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>

            <div class="p-4 border-t border-slate-100 bg-slate-50/30 flex flex-wrap items-center justify-between gap-4">
              <div class="flex items-center gap-2">
                <span class="text-xs text-slate-500">Услуг на странице:</span>
                <select
                  v-model.number="pagination.limit"
                  @change="handleServicesPageSizeChange"
                  class="px-2 py-1 bg-white border border-slate-200 rounded text-xs focus:ring-1 focus:ring-indigo-500 transition-all"
                >
                  <option :value="25">25</option>
                  <option :value="50">50</option>
                  <option :value="100">100</option>
                  <option :value="250">250</option>
                </select>
              </div>
              <p class="text-xs text-slate-500">
                Показано {{ pagination.offset + 1 }}-{{ Math.min(pagination.offset + pagination.limit, total) }} из {{ total }} услуг
              </p>
              <div class="flex items-center gap-2">
                <button
                  @click="handlePageChange(-1)"
                  :disabled="pagination.offset === 0"
                  class="p-2 rounded-lg hover:bg-white hover:shadow-sm disabled:opacity-30 transition-all"
                >
                  <ChevronLeft class="h-4 w-4" />
                </button>
                <span class="text-xs font-bold text-slate-700">Страница {{ currentPage }}</span>
                <button
                  @click="handlePageChange(1)"
                  :disabled="pagination.offset + pagination.limit >= total"
                  class="p-2 rounded-lg hover:bg-white hover:shadow-sm disabled:opacity-30 transition-all"
                >
                  <ChevronRight class="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="specialists">
          <div class="space-y-0.5 border border-slate-200 rounded-lg overflow-hidden bg-card">
            <div class="p-5 border-b border-slate-200 space-y-4">
              <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <h3 class="text-lg font-bold text-slate-900">Специалисты</h3>
                <div class="flex flex-wrap items-center gap-3">
                  <div class="relative">
                    <Search class="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                    <Input
                      v-model="specialistSearch"
                      placeholder="Поиск специалистов..."
                      class="pl-9 w-64 md:w-72 rounded-md"
                    />
                  </div>
                  <span class="text-sm text-slate-500">Всего: {{ specialists.length }}</span>
                </div>
              </div>
            </div>

            <Table wrapper-class="rounded-none border-0 bg-transparent">
                <TableHeader>
                  <TableRow>
                    <TableHead>
                      <button @click="toggleSort(specialistsTable, 'name')" class="inline-flex items-center gap-1.5 hover:text-slate-900 transition-colors">
                        Имя
                        <ArrowUpDown class="h-3.5 w-3.5 text-slate-400" />
                      </button>
                    </TableHead>
                    <TableHead>
                      <button @click="toggleSort(specialistsTable, 'role')" class="inline-flex items-center gap-1.5 hover:text-slate-900 transition-colors">
                        Роль
                        <ArrowUpDown class="h-3.5 w-3.5 text-slate-400" />
                      </button>
                    </TableHead>
                    <TableHead>
                      <button @click="toggleSort(specialistsTable, 'services')" class="inline-flex items-center gap-1.5 hover:text-slate-900 transition-colors">
                        Услуг
                        <ArrowUpDown class="h-3.5 w-3.5 text-slate-400" />
                      </button>
                    </TableHead>
                    <TableHead>
                      <button @click="toggleSort(specialistsTable, 'active')" class="inline-flex items-center gap-1.5 hover:text-slate-900 transition-colors">
                        Активен
                        <ArrowUpDown class="h-3.5 w-3.5 text-slate-400" />
                      </button>
                    </TableHead>
                    <TableHead>
                      <button @click="toggleSort(specialistsTable, 'information')" class="inline-flex items-center gap-1.5 hover:text-slate-900 transition-colors">
                        Информация
                        <ArrowUpDown class="h-3.5 w-3.5 text-slate-400" />
                      </button>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow v-if="isSpecialistsLoading" v-for="i in 5" :key="`spec-skel-${i}`" class="animate-pulse">
                    <TableCell><div class="h-4 w-24 bg-slate-100 rounded"></div></TableCell>
                    <TableCell><div class="h-4 w-32 bg-slate-100 rounded"></div></TableCell>
                    <TableCell><div class="h-4 w-16 bg-slate-100 rounded"></div></TableCell>
                    <TableCell><div class="h-6 w-10 bg-slate-100 rounded-full"></div></TableCell>
                    <TableCell><div class="h-8 w-40 bg-slate-100 rounded"></div></TableCell>
                  </TableRow>
                  <TableRow v-else-if="filteredSpecialists.length === 0">
                    <TableCell :colspan="5" className="p-12 text-center text-slate-400 italic">
                      Специалисты не найдены
                    </TableCell>
                  </TableRow>
                  <TableRow
                    v-else
                    v-for="specialist in sortedSpecialists"
                    :key="specialist.id"
                    :class="[
                      'hover:bg-slate-50/50 transition-colors',
                      isSpecialistEnabled(specialist) ? 'bg-emerald-50/30' : ''
                    ]"
                  >
                    <TableCell>
                      <p class="text-sm font-bold text-slate-900">{{ specialist.name }}</p>
                      <p class="text-[10px] text-slate-500 mt-0.5">
                        {{ specialist.email || specialist.phone || '' }}
                      </p>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary" class="font-medium">
                        {{ specialist.role || 'Специалист' }}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <span class="text-sm text-slate-600">{{ specialist.services_count ?? specialist.linked_services ?? '-' }}</span>
                    </TableCell>
                    <TableCell>
                      <div class="flex items-center">
                        <Switch
                          :model-value="isSpecialistEnabled(specialist)"
                          :disabled="togglingSpecialistIds.has(specialist.id)"
                          @update:model-value="() => handleToggleSpecialistActive(specialist)"
                        />
                      </div>
                    </TableCell>
                    <TableCell>
                      <div class="flex items-center justify-between gap-2">
                        <p class="text-xs text-slate-500 line-clamp-1">
                          {{ specialist.information || '—' }}
                        </p>
                        <Button
                          @click="openSpecialistInformationSheet(specialist)"
                          variant="outline"
                          size="sm"
                          class="h-8 w-8 rounded-md p-0"
                          aria-label="Редактировать информацию"
                          title="Редактировать информацию"
                        >
                          <Pencil class="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>

            <div class="p-4 border-t border-slate-100 bg-slate-50/30 text-xs text-slate-500">
              {{ filteredSpecialists.length }} из {{ specialists.length }} специалистов отображаются
            </div>
          </div>
        </TabsContent>

        <TabsContent value="categories">
          <div class="space-y-0.5 border border-slate-200 rounded-lg overflow-hidden">
            <div class="p-6 border-b border-slate-100 space-y-4">
              <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <h3 class="text-lg font-bold text-slate-900">Категории</h3>
                <div class="flex flex-wrap items-center gap-3">
                  <div class="relative">
                    <Search class="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                    <input
                      v-model="categorySearch"
                      type="text"
                      placeholder="Поиск категории..."
                      class="pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all w-64"
                    />
                  </div>
                  <label class="flex items-center gap-2 cursor-pointer">
                    <input
                      v-model="showOnlyEnabledCategories"
                      type="checkbox"
                      class="w-4 h-4 text-indigo-600 border-slate-300 rounded focus:ring-indigo-500"
                    />
                    <span class="text-sm text-slate-600">Только включенные</span>
                  </label>
                </div>
              </div>
            </div>

            <Table wrapper-class="rounded-none border-0 bg-transparent">
                <TableHeader>
                  <TableRow>
                    <TableHead>
                      <button @click="toggleSort(categoriesTable, 'name')" class="inline-flex items-center gap-1.5 hover:text-slate-900 transition-colors">
                        Категория
                        <ArrowUpDown class="h-3.5 w-3.5 text-slate-400" />
                      </button>
                    </TableHead>
                    <TableHead>
                      <button @click="toggleSort(categoriesTable, 'services')" class="inline-flex items-center gap-1.5 hover:text-slate-900 transition-colors">
                        Услуг
                        <ArrowUpDown class="h-3.5 w-3.5 text-slate-400" />
                      </button>
                    </TableHead>
                    <TableHead>
                      <button @click="toggleSort(categoriesTable, 'status')" class="inline-flex items-center gap-1.5 hover:text-slate-900 transition-colors">
                        Статус
                        <ArrowUpDown class="h-3.5 w-3.5 text-slate-400" />
                      </button>
                    </TableHead>
                    <TableHead>
                      <button @click="toggleSort(categoriesTable, 'priority')" class="inline-flex items-center gap-1.5 hover:text-slate-900 transition-colors">
                        Приоритет
                        <ArrowUpDown class="h-3.5 w-3.5 text-slate-400" />
                      </button>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow v-if="isCategoriesLoading" v-for="i in 5" :key="`cat-skel-${i}`" class="animate-pulse">
                    <TableCell><div class="h-4 w-32 bg-slate-100 rounded"></div></TableCell>
                    <TableCell><div class="h-4 w-16 bg-slate-100 rounded"></div></TableCell>
                    <TableCell><div class="h-4 w-12 bg-slate-100 rounded"></div></TableCell>
                    <TableCell><div class="h-4 w-10 bg-slate-100 rounded"></div></TableCell>
                  </TableRow>
                  <TableRow v-else-if="filteredCategories.length === 0">
                    <TableCell :colspan="4" className="p-12 text-center text-slate-400 italic">
                      Категории не найдены
                    </TableCell>
                  </TableRow>
                  <TableRow
                    v-else
                    v-for="cat in sortedCategories"
                    :key="cat.id"
                    class="hover:bg-slate-50/50 transition-colors"
                  >
                    <TableCell>
                      <p class="text-sm font-bold text-slate-900">{{ cat.name }}</p>
                      <p v-if="cat.description" class="text-[10px] text-slate-500 mt-0.5 line-clamp-1">
                        {{ cat.description }}
                      </p>
                    </TableCell>
                    <TableCell>
                      <span class="text-sm text-slate-600">{{ cat.services_count ?? '—' }}</span>
                    </TableCell>
                    <TableCell>
                      <button
                        @click="handleToggleCategory(cat)"
                        class="relative inline-flex h-5 w-9 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none"
                        :class="[cat.is_enabled ? 'bg-emerald-500' : 'bg-slate-200']"
                      >
                        <span
                          aria-hidden="true"
                          class="pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow transition duration-200 ease-in-out"
                          :class="[cat.is_enabled ? 'translate-x-4' : 'translate-x-0']"
                        />
                      </button>
                    </TableCell>
                    <TableCell>
                      <input
                        type="number"
                        v-model.number="cat.priority"
                        @blur="handleUpdateCategoryPriority(cat)"
                        class="w-16 px-2 py-1 bg-slate-50 border border-slate-200 rounded text-xs font-mono focus:ring-1 focus:ring-indigo-500 focus:bg-white transition-all"
                        min="0"
                        max="100"
                      />
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>

            <div class="p-4 border-t border-slate-100 bg-slate-50/30 text-xs text-slate-500">
              {{ filteredCategories.length }} из {{ categories.length }} категорий отображаются
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>

    <Sheet
      :open="specialistInformationSheetOpen"
      @update:open="(open) => { if (!open) closeSpecialistInformationSheet() }"
    >
      <SheetContent side="right" class-name="w-full sm:max-w-xl flex flex-col">
        <SheetHeader>
          <SheetTitle>Информация о специалисте</SheetTitle>
        </SheetHeader>

        <div class="flex-1 overflow-y-auto p-6 space-y-4">
          <p v-if="selectedSpecialistForInformation" class="text-sm text-slate-600">
            {{ selectedSpecialistForInformation.name }}
          </p>
          <div class="space-y-2">
            <label class="text-sm font-medium text-slate-700">Информация</label>
            <Textarea
              v-model="specialistInformationDraft"
              rows="8"
              placeholder="Введите информацию о сотруднике"
              class="resize-none"
            />
          </div>
        </div>

        <div class="border-t border-slate-200 bg-white px-6 py-4 flex items-center justify-end gap-2">
          <button
            @click="closeSpecialistInformationSheet"
            class="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-md transition-colors"
            :disabled="Boolean(savingSpecialistInformationForId)"
          >
            Отмена
          </button>
          <button
            @click="handleSaveSpecialistInformation"
            class="px-5 py-2 bg-indigo-600 text-white rounded-md text-sm font-bold hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors inline-flex items-center gap-1.5"
            :disabled="Boolean(savingSpecialistInformationForId)"
          >
            <Loader2 v-if="savingSpecialistInformationForId" class="h-4 w-4 animate-spin" />
            {{ savingSpecialistInformationForId ? 'Сохранение...' : 'Сохранить' }}
          </button>
        </div>
      </SheetContent>
    </Sheet>

    <Sheet
      :open="toolEditorOpen"
      @update:open="(open) => { if (!open) closeToolEditor() }"
    >
      <SheetContent side="right" class-name="w-full sm:max-w-xl flex flex-col">
        <SheetHeader>
          <SheetTitle>Настройка инструмента SQNS</SheetTitle>
        </SheetHeader>

        <div class="flex-1 overflow-y-auto p-6 space-y-6">
          <div v-if="selectedTool" class="space-y-1">
            <h4 class="text-lg font-bold text-slate-900">{{ selectedTool.displayName || selectedTool.name }}</h4>
            <p class="text-xs font-mono text-slate-400 uppercase tracking-wider">{{ selectedTool.name }}</p>
          </div>

          <div class="space-y-2">
            <div class="flex items-center justify-between">
              <label class="text-sm font-bold text-slate-700">Описание для ИИ-агента</label>
              <button
                v-if="toolDescriptionDraft.trim() !== ''"
                @click="toolDescriptionDraft = ''"
                class="text-[10px] font-bold text-indigo-600 hover:text-indigo-800 uppercase tracking-tight"
              >
                Сбросить к дефолтному
              </button>
            </div>
            <Textarea
              v-model="toolDescriptionDraft"
              rows="12"
              placeholder="Введите описание инструмента, которое будет видеть ИИ-агент..."
              class="resize-none leading-relaxed border-slate-200 focus:border-indigo-400 focus:ring-4 focus:ring-indigo-500/10 transition-all"
            />
            <p class="text-xs text-slate-500 italic">
              * Оставьте поле пустым, чтобы использовать описание по умолчанию от сервера.
            </p>
          </div>

          <div v-if="selectedTool?.requiredFields.length" class="space-y-3 p-4 bg-slate-50 rounded-xl border border-slate-100">
            <p class="text-xs font-bold text-slate-500 uppercase tracking-widest">Обязательные поля</p>
            <div class="flex flex-wrap gap-2">
              <span
                v-for="field in selectedTool.requiredFields"
                :key="field"
                class="px-2.5 py-1 bg-white border border-slate-200 text-slate-600 rounded-md text-[10px] font-bold shadow-sm"
              >
                {{ field }}
              </span>
            </div>
          </div>
        </div>

        <div class="border-t border-slate-200 bg-white px-6 py-4 flex items-center justify-end gap-3">
          <button
            @click="closeToolEditor"
            class="px-4 py-2 text-sm font-bold text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg transition-all"
            :disabled="isSavingTool"
          >
            Отмена
          </button>
          <button
            @click="handleSaveTool"
            class="px-6 py-2 bg-indigo-600 text-white rounded-lg text-sm font-bold hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-md shadow-indigo-200 inline-flex items-center gap-2"
            :disabled="isSavingTool"
          >
            <Loader2 v-if="isSavingTool" class="h-4 w-4 animate-spin" />
            {{ isSavingTool ? 'Сохранение...' : 'Сохранить изменения' }}
          </button>
        </div>
      </SheetContent>
    </Sheet>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import {
  useVueTable,
  getCoreRowModel,
  getSortedRowModel,
  type ColumnDef,
  type SortingState,
} from '@tanstack/vue-table'
import { 
  Link, 
  RefreshCw, 
  AlertTriangle, 
  ArrowUpDown,
  X, 
  Search, 
  Pencil,
  Loader2,
  ChevronLeft, 
  ChevronRight
} from 'lucide-vue-next'
import { useAgents, type SqnsServiceEmployeeLink, type SqnsSpecialist, type SqnsTool } from '../composables/useAgents'
import { useAgentEditorStore } from '../composables/useAgentEditorStore'
import { useToast } from '../composables/useToast'
import { getReadableErrorMessage } from '~/utils/api-errors'
import { valueUpdater } from '~/lib/utils'
import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHeader,
  TableHead,
  TableRow,
} from './ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs'
import { Input } from './ui/input'
import { Switch } from './ui/switch'
import { Button } from './ui/button'
import { Badge } from './ui/badge'
import { Textarea } from './ui/textarea'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from './ui/sheet'

const props = defineProps<{
  agentId: string
  status: 'active' | 'error'
  lastSyncAt?: string
  warning?: string | null
}>()

const emit = defineEmits<{
  (e: 'close-warning'): void
  (e: 'sync-complete'): void
}>()

const store = useAgentEditorStore()
const { 
  syncSqns, 
  fetchSqnsServicesCached, 
  updateSqnsService, 
  bulkUpdateSqnsServices,
  fetchSqnsCategories,
  fetchSqnsSpecialists,
  fetchSqnsServiceEmployeeLinks,
  updateSqnsSpecialist,
  updateSqnsCategory
} = useAgents()
const { success: toastSuccess, error: toastError } = useToast()

// State
const isLoading = ref(false)
const services = ref<any[]>([])
const total = ref(0)
const categories = ref<any[]>([])
const selectedIds = ref<string[]>([])
const isCategoriesLoading = ref(false)
const categorySearch = ref('')
const showOnlyEnabledCategories = ref(false)
const activeTab = ref<'tools' | 'all-records' | 'services' | 'specialists' | 'categories'>('tools')
const specialists = ref<SqnsSpecialist[]>([])
const isSpecialistsLoading = ref(false)
const allRecords = ref<SqnsServiceEmployeeLink[]>([])
const allRecordsTotal = ref(0)
const isAllRecordsLoading = ref(false)
const allRecordsSearch = ref('')
const allRecordsPageSize = ref(50)
const allRecordsPageOffset = ref(0)
const specialistSearch = ref('')
const specialistInformationSheetOpen = ref(false)
const selectedSpecialistForInformation = ref<SqnsSpecialist | null>(null)
const specialistInformationDraft = ref('')
const savingSpecialistInformationForId = ref<string | null>(null)
const togglingSpecialistIds = ref<Set<string>>(new Set())

// Tools State
const toolSearch = ref('')
const toolEditorOpen = ref(false)
const selectedTool = ref<(SqnsTool & { displayName?: string }) | null>(null)
const toolDescriptionDraft = ref('')
const isSavingTool = ref(false)
const pendingToolNames = ref<Set<string>>(new Set())

const filters = ref({
  search: '',
  category: null as string | null,
  is_enabled: null as boolean | null
})

const pagination = ref({
  limit: 50,
  offset: 0
})

const getActiveTabStorageKey = () => `sqns-active-tab:${props.agentId}`
const isValidActiveTab = (value: string): value is 'tools' | 'all-records' | 'services' | 'specialists' | 'categories' =>
  value === 'tools' || value === 'all-records' || value === 'services' || value === 'specialists' || value === 'categories'

const currentPage = computed(() => Math.floor(pagination.value.offset / pagination.value.limit) + 1)

const serviceIdKey = (id: unknown) => String(id)
const isServiceRowSelected = (id: unknown) => selectedIds.value.includes(serviceIdKey(id))

const isAllSelected = computed(
  () =>
    services.value.length > 0 &&
    services.value.every((s) => selectedIds.value.includes(serviceIdKey(s.id)))
)

const formattedSyncAt = computed(() => {
  if (!props.lastSyncAt) return 'нет данных'
  const date = new Date(props.lastSyncAt)
  return date.toLocaleString('ru-RU', { dateStyle: 'medium', timeStyle: 'short' })
})

const sqnsToolsList = computed(() => {
  const tools = store.sqnsStatus?.sqnsTools ?? []
  const nameMap: Record<string, string> = {
    'sqns_list_resources': 'Сотрудники',
    'sqns_list_services': 'Услуги',
    'sqns_find_client': 'Поиск клиента',
    'sqns_list_slots': 'Поиск слотов',
    'sqns_find_booking_options': 'Поиск вариантов записи',
    'sqns_create_visit': 'Создание записи'
  }
  return tools.map(tool => ({
    ...tool,
    displayName: nameMap[tool.name] || tool.name
  }))
})

const filteredTools = computed(() => {
  const query = toolSearch.value.trim().toLowerCase()
  if (!query) return sqnsToolsList.value

  return sqnsToolsList.value.filter((tool) => {
    const haystack = `${tool.name} ${tool.displayName || ''} ${tool.description || ''}`.toLowerCase()
    return haystack.includes(query)
  })
})

const filteredCategories = computed(() => {
  const query = categorySearch.value.trim().toLowerCase()
  return categories.value.filter((cat) => {
    if (showOnlyEnabledCategories.value && !cat.is_enabled) return false
    if (!query) return true
    return cat.name?.toLowerCase().includes(query) ?? false
  })
})

const filteredSpecialists = computed(() => {
  const query = specialistSearch.value.trim().toLowerCase()
  if (!query) return specialists.value

  return specialists.value.filter((specialist) => {
    const haystack = `${specialist.name ?? ''} ${specialist.role ?? ''} ${specialist.email ?? ''} ${specialist.phone ?? ''}`.toLowerCase()
    return haystack.includes(query)
  })
})

const filteredAllRecords = computed(() => {
  const query = allRecordsSearch.value.trim().toLowerCase()
  if (!query) return allRecords.value
  return allRecords.value.filter((row) => {
    const haystack = `${row.service ?? ''} ${row.employee ?? ''} ${row.category ?? ''}`.toLowerCase()
    return haystack.includes(query)
  })
})

const allRecordsCurrentPage = computed(() =>
  Math.floor(allRecordsPageOffset.value / allRecordsPageSize.value) + 1
)

const pagedAllRecords = computed(() =>
  filteredAllRecords.value.slice(allRecordsPageOffset.value, allRecordsPageOffset.value + allRecordsPageSize.value)
)

watch(allRecordsSearch, () => { allRecordsPageOffset.value = 0 })
watch(allRecordsPageSize, () => { allRecordsPageOffset.value = 0 })

const isSpecialistEnabled = (specialist: SqnsSpecialist) => specialist.active ?? specialist.is_active ?? false
const parseServicePrice = (service: any) => {
  if (typeof service?.price === 'number' && Number.isFinite(service.price)) return service.price
  if (typeof service?.price_range !== 'string') return 0
  const numeric = Number(service.price_range.replace(/[^\d]/g, ''))
  return Number.isFinite(numeric) ? numeric : 0
}
const servicesSorting = ref<SortingState>([])
const specialistsSorting = ref<SortingState>([])
const categoriesSorting = ref<SortingState>([])
const allRecordsSorting = ref<SortingState>([{ id: 'updated_at', desc: true }])

const servicesColumns: ColumnDef<any>[] = [
  { id: 'name', accessorFn: (row) => row.name ?? '' },
  { id: 'category', accessorFn: (row) => row.category ?? '' },
  { id: 'price', accessorFn: (row) => parseServicePrice(row) },
  { id: 'duration', accessorFn: (row) => row.duration ?? 0 },
  { id: 'status', accessorFn: (row) => Boolean(row.is_enabled) },
  { id: 'priority', accessorFn: (row) => row.priority ?? 0 },
]

const specialistsColumns: ColumnDef<SqnsSpecialist>[] = [
  { id: 'name', accessorFn: (row) => row.name ?? '' },
  { id: 'role', accessorFn: (row) => row.role ?? '' },
  { id: 'services', accessorFn: (row) => row.services_count ?? row.linked_services ?? 0 },
  { id: 'active', accessorFn: (row) => isSpecialistEnabled(row) },
  { id: 'information', accessorFn: (row) => row.information ?? '' },
]

const categoriesColumns: ColumnDef<any>[] = [
  { id: 'name', accessorFn: (row) => row.name ?? '' },
  { id: 'services', accessorFn: (row) => row.services_count ?? 0 },
  { id: 'status', accessorFn: (row) => Boolean(row.is_enabled) },
  { id: 'priority', accessorFn: (row) => row.priority ?? 0 },
]

const allRecordsColumns: ColumnDef<SqnsServiceEmployeeLink>[] = [
  { id: 'service', accessorFn: (row) => row.service ?? '' },
  { id: 'employee', accessorFn: (row) => row.employee ?? '' },
  { id: 'category', accessorFn: (row) => row.category ?? '' },
  {
    id: 'updated_at',
    accessorFn: (row) => {
      if (!row.updated_at) return 0
      const ts = new Date(row.updated_at).getTime()
      return Number.isFinite(ts) ? ts : 0
    }
  },
]

// Передаём Ref/ComputedRef в data — иначе isRef(initialOptions.data) === false и TanStack Table
// не подписывается на обновления (после bulk/reload строки остаются со старым is_enabled).
const servicesTable = useVueTable({
  data: services,
  columns: servicesColumns,
  state: {
    get sorting() { return servicesSorting.value },
  },
  onSortingChange: (updater) => valueUpdater(updater, servicesSorting),
  getCoreRowModel: getCoreRowModel(),
  getSortedRowModel: getSortedRowModel(),
})

const specialistsTable = useVueTable({
  data: filteredSpecialists,
  columns: specialistsColumns,
  state: {
    get sorting() { return specialistsSorting.value },
  },
  onSortingChange: (updater) => valueUpdater(updater, specialistsSorting),
  getCoreRowModel: getCoreRowModel(),
  getSortedRowModel: getSortedRowModel(),
})

const categoriesTable = useVueTable({
  data: filteredCategories,
  columns: categoriesColumns,
  state: {
    get sorting() { return categoriesSorting.value },
  },
  onSortingChange: (updater) => valueUpdater(updater, categoriesSorting),
  getCoreRowModel: getCoreRowModel(),
  getSortedRowModel: getSortedRowModel(),
})

const allRecordsTable = useVueTable({
  data: filteredAllRecords,
  columns: allRecordsColumns,
  state: {
    get sorting() { return allRecordsSorting.value },
  },
  onSortingChange: (updater) => valueUpdater(updater, allRecordsSorting),
  getCoreRowModel: getCoreRowModel(),
  getSortedRowModel: getSortedRowModel(),
})

const sortedServices = computed(() => servicesTable.getRowModel().rows.map((row) => row.original))
const sortedSpecialists = computed(() => specialistsTable.getRowModel().rows.map((row) => row.original))
const sortedCategories = computed(() => categoriesTable.getRowModel().rows.map((row) => row.original))
const sortedAllRecords = computed(() => allRecordsTable.getRowModel().rows.map((row) => row.original))

const toggleSort = (table: any, columnId: string) => {
  const column = table.getColumn(columnId)
  if (!column) return
  column.toggleSorting(column.getIsSorted() === 'asc')
}

/** Когда включён фильтр «только включённые / только выключенные», строка после переключения может не подходить — убираем без запроса к серверу. */
const pruneServicesToMatchEnabledFilter = () => {
  const fe = filters.value.is_enabled
  if (fe === null || fe === undefined) return
  const before = services.value.length
  services.value = services.value.filter((s) => Boolean(s.is_enabled) === fe)
  const removed = before - services.value.length
  if (removed > 0) total.value = Math.max(0, total.value - removed)
}

// Actions
const loadServices = async (silent = false) => {
  try {
    if (!silent) isLoading.value = true
    const response = await fetchSqnsServicesCached(props.agentId, {
      ...filters.value,
      ...pagination.value,
      category: filters.value.category ?? undefined,
      is_enabled: filters.value.is_enabled ?? undefined
    })
    services.value = response.services
    total.value = response.total
  } catch (err) {
    console.error('Failed to load services:', err)
  } finally {
    if (!silent) isLoading.value = false
  }
}

const loadCategories = async (silent = false) => {
  try {
    if (!silent) isCategoriesLoading.value = true
    categories.value = await fetchSqnsCategories(props.agentId)
  } catch (err) {
    console.error('Failed to load categories:', err)
  } finally {
    if (!silent) isCategoriesLoading.value = false
  }
}

const loadSpecialists = async (silent = false) => {
  try {
    if (!silent) isSpecialistsLoading.value = true
    specialists.value = await fetchSqnsSpecialists(props.agentId, {
      limit: 1000,
      offset: 0
    })
  } catch (err) {
    console.error('Failed to load specialists:', err)
  } finally {
    if (!silent) isSpecialistsLoading.value = false
  }
}

const loadAllRecords = async (silent = false) => {
  try {
    if (!silent) isAllRecordsLoading.value = true
    const response = await fetchSqnsServiceEmployeeLinks(props.agentId, { limit: 2000, offset: 0 })
    allRecords.value = response.items ?? []
    allRecordsTotal.value = response.total ?? allRecords.value.length
  } catch (err) {
    console.error('Failed to load service-employee links:', err)
  } finally {
    if (!silent) isAllRecordsLoading.value = false
  }
}

const formatRecordUpdatedAt = (value: string | null) => {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleString('ru-RU', { dateStyle: 'medium', timeStyle: 'short' })
}

const handleToggleService = async (service: any) => {
  const originalState = Boolean(service.is_enabled)
  const nextState = !originalState
  const sid = serviceIdKey(service.id)

  service.is_enabled = nextState

  try {
    await updateSqnsService(props.agentId, service.id, { is_enabled: nextState })
    // Новый массив/объекты — иначе TanStack Table не пересчитывает строки (свитч «залипает»).
    services.value = services.value.map((s) =>
      serviceIdKey(s.id) === sid ? { ...s, is_enabled: nextState } : s
    )
    pruneServicesToMatchEnabledFilter()
    toastSuccess('Статус обновлен', `Услуга "${service.name}" ${nextState ? 'включена' : 'отключена'}`)
  } catch (err: any) {
    services.value = services.value.map((s) =>
      serviceIdKey(s.id) === sid ? { ...s, is_enabled: originalState } : s
    )
    toastError('Ошибка', getReadableErrorMessage(err, 'Не удалось изменить статус услуги'))
    await loadServices(true)
  }
}

const handleUpdatePriority = async (service: any) => {
  const nextPriority = Number(service.priority)
  if (!Number.isFinite(nextPriority) || nextPriority < 0) {
    toastError('Ошибка', 'Приоритет должен быть числом >= 0')
    loadServices()
    return
  }

  try {
    await updateSqnsService(props.agentId, service.id, { priority: nextPriority })
    toastSuccess('Приоритет обновлен', `Для услуги "${service.name}" установлен приоритет ${nextPriority}`)
  } catch (err: any) {
    toastError('Ошибка', getReadableErrorMessage(err, 'Не удалось обновить приоритет услуги'))
    await loadServices(true)
  }
}

const bulkServicesInFlight = ref(false)

const handleBulkUpdate = async (is_enabled: boolean) => {
  const count = selectedIds.value.length
  if (!confirm(`Вы уверены? ${count} услуг будут ${is_enabled ? 'включены' : 'отключены'}`)) return
  if (bulkServicesInFlight.value) return

  const idSet = new Set(selectedIds.value.map(serviceIdKey))
  const idsForApi = [...selectedIds.value]
  // Снимок для отката: свитчи обновляем сразу (новый массив — TanStack/Vue видят изменение).
  const snapshot = services.value.map((s) => ({ ...s }))

  services.value = services.value.map((s) =>
    idSet.has(serviceIdKey(s.id)) ? { ...s, is_enabled } : s
  )

  bulkServicesInFlight.value = true
  try {
    await bulkUpdateSqnsServices(props.agentId, {
      ids: idsForApi,
      is_enabled
    })
    selectedIds.value = []
    pruneServicesToMatchEnabledFilter()
    toastSuccess('Массовое обновление', `Успешно обновлено ${count} услуг`)
  } catch (err: any) {
    services.value = snapshot.map((s) => ({ ...s }))
    toastError('Ошибка', getReadableErrorMessage(err, 'Не удалось выполнить массовое обновление'))
    await loadServices(true)
  } finally {
    bulkServicesInFlight.value = false
  }
}

const handleToggleCategory = async (cat: any) => {
  const originalState = cat.is_enabled
  const nextState = !originalState
  
  // Оптимистичное обновление UI
  cat.is_enabled = nextState
  
  try {
    await updateSqnsCategory(props.agentId, cat.id, { is_enabled: nextState })
    toastSuccess('Статус категории обновлен', `Категория "${cat.name}" ${nextState ? 'включена' : 'отключена'}`)
  } catch (err: any) {
    cat.is_enabled = originalState
    toastError('Ошибка', getReadableErrorMessage(err, 'Не удалось изменить статус категории'))
    await loadCategories(true)
  }
}

const handleUpdateCategoryPriority = async (cat: any) => {
  const nextPriority = Number(cat.priority)
  if (!Number.isFinite(nextPriority) || nextPriority < 0) {
    toastError('Ошибка', 'Приоритет должен быть числом >= 0')
    await loadCategories(true)
    return
  }

  try {
    await updateSqnsCategory(props.agentId, cat.id, { priority: nextPriority })
    toastSuccess('Приоритет категории обновлен', `Для категории "${cat.name}" установлен приоритет ${nextPriority}`)
  } catch (err: any) {
    toastError('Ошибка', getReadableErrorMessage(err, 'Не удалось обновить приоритет категории'))
    await loadCategories(true)
  }
}

const handleToggleSpecialistActive = async (specialist: SqnsSpecialist) => {
  const specialistId = specialist.id
  if (!specialistId || togglingSpecialistIds.value.has(specialistId)) return

  const originalState = isSpecialistEnabled(specialist)
  const nextState = !originalState
  specialist.active = nextState
  togglingSpecialistIds.value.add(specialistId)

  try {
    await updateSqnsSpecialist(props.agentId, specialistId, { active: nextState })
    toastSuccess('Статус специалиста обновлен', `Сотрудник "${specialist.name}" ${nextState ? 'включен' : 'отключен'}`)
  } catch (err: any) {
    specialist.active = originalState
    toastError('Ошибка', getReadableErrorMessage(err, 'Не удалось изменить статус специалиста'))
  } finally {
    togglingSpecialistIds.value.delete(specialistId)
  }
}

const openSpecialistInformationSheet = (specialist: SqnsSpecialist) => {
  selectedSpecialistForInformation.value = specialist
  specialistInformationDraft.value = specialist.information ?? ''
  specialistInformationSheetOpen.value = true
}

const closeSpecialistInformationSheet = () => {
  specialistInformationSheetOpen.value = false
  selectedSpecialistForInformation.value = null
  specialistInformationDraft.value = ''
}

const handleSaveSpecialistInformation = async () => {
  const specialist = selectedSpecialistForInformation.value
  if (!specialist?.id) return

  const infoValue = specialistInformationDraft.value.trim()
  savingSpecialistInformationForId.value = specialist.id

  try {
    await updateSqnsSpecialist(props.agentId, specialist.id, {
      information: infoValue || null
    })
    specialist.information = infoValue || null
    toastSuccess('Информация обновлена', `Для сотрудника "${specialist.name}" сохранено описание`)
    closeSpecialistInformationSheet()
  } catch (err: any) {
    toastError('Ошибка', getReadableErrorMessage(err, 'Не удалось сохранить информацию о специалисте'))
  } finally {
    savingSpecialistInformationForId.value = null
  }
}

// Tools Handlers
const openToolEditor = (tool: SqnsTool & { displayName?: string }) => {
  selectedTool.value = tool
  toolDescriptionDraft.value = tool.description || ''
  toolEditorOpen.value = true
}

const closeToolEditor = () => {
  toolEditorOpen.value = false
  selectedTool.value = null
  toolDescriptionDraft.value = ''
}

const handleToggleTool = async (tool: SqnsTool, enabled: boolean) => {
  if (pendingToolNames.value.has(tool.name)) return
  
  const originalState = tool.isEnabled
  tool.isEnabled = enabled
  pendingToolNames.value.add(tool.name)

  try {
    await store.updateSqnsToolForAgent(tool.name, { enabled })
    toastSuccess(enabled ? 'Инструмент включен' : 'Инструмент выключен')
  } catch (err: any) {
    tool.isEnabled = originalState
    toastError('Ошибка', getReadableErrorMessage(err, 'Не удалось изменить статус инструмента'))
  } finally {
    pendingToolNames.value.delete(tool.name)
  }
}

const handleSaveTool = async () => {
  if (!selectedTool.value) return
  
  const tool = selectedTool.value
  const description = toolDescriptionDraft.value.trim()
  isSavingTool.value = true
  pendingToolNames.value.add(tool.name)

  try {
    await store.updateSqnsToolForAgent(tool.name, { description })
    tool.description = description
    toastSuccess('Описание обновлено')
    closeToolEditor()
  } catch (err: any) {
    toastError('Ошибка', getReadableErrorMessage(err, 'Не удалось обновить описание инструмента'))
  } finally {
    isSavingTool.value = false
    pendingToolNames.value.delete(tool.name)
  }
}

const toggleSelect = (id: unknown) => {
  const key = serviceIdKey(id)
  const index = selectedIds.value.indexOf(key)
  if (index === -1) selectedIds.value.push(key)
  else selectedIds.value.splice(index, 1)
}

const toggleSelectAll = () => {
  if (isAllSelected.value) {
    const onPage = new Set(services.value.map((s) => serviceIdKey(s.id)))
    selectedIds.value = selectedIds.value.filter((id) => !onPage.has(id))
  } else {
    for (const s of services.value) {
      const key = serviceIdKey(s.id)
      if (!selectedIds.value.includes(key)) selectedIds.value.push(key)
    }
  }
}

const handlePageChange = (delta: number) => {
  pagination.value.offset += delta * pagination.value.limit
  loadServices()
}

const handleServicesPageSizeChange = () => {
  pagination.value.offset = 0
  loadServices()
}

// Watchers
let debounceTimer: any = null
watch(() => filters.value.search, () => {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    pagination.value.offset = 0
    loadServices()
  }, 300)
})

watch([() => filters.value.category, () => filters.value.is_enabled], () => {
  pagination.value.offset = 0
  loadServices()
})

watch(activeTab, (tab) => {
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(getActiveTabStorageKey(), tab)
  }
  if (tab === 'specialists' && specialists.value.length === 0) {
    loadSpecialists()
  }
  if (tab === 'categories' && categories.value.length === 0) {
    loadCategories()
  }
  if (tab === 'services' && services.value.length === 0) {
    loadServices()
  }
  if (tab === 'all-records' && allRecords.value.length === 0) {
    loadAllRecords()
  }
})

onMounted(() => {
  if (typeof window !== 'undefined') {
    const savedTab = window.localStorage.getItem(getActiveTabStorageKey())
    if (savedTab && isValidActiveTab(savedTab)) {
      activeTab.value = savedTab
    }
  }
  
  // Load data based on current tab
  if (activeTab.value === 'services') loadServices()
  else if (activeTab.value === 'categories') loadCategories()
  else if (activeTab.value === 'specialists') loadSpecialists()
  else if (activeTab.value === 'all-records') loadAllRecords()
  
  // Always ensure status is loaded for tools
  store.ensureSqnsStatusLoaded()
})
</script>
