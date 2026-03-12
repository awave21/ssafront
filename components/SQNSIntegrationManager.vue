<template>
  <div class="space-y-6">
    <div class="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-5">
      <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div class="flex items-center gap-4">
          <div 
            class="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0"
            :class="[
              status === 'error' ? 'bg-red-50 text-red-600' : 'bg-emerald-50 text-emerald-600'
            ]"
          >
            <Link class="w-6 h-6" />
          </div>
          <div>
            <div class="flex items-center gap-2">
              <h3 class="text-lg font-bold text-slate-900">SQNS Интеграция</h3>
              <span 
                class="text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded-full"
                :class="[
                  status === 'error' ? 'bg-red-50 text-red-600' : 'bg-emerald-50 text-emerald-600'
                ]"
              >
                {{ status === 'error' ? 'Ошибка' : 'Активна' }}
              </span>
            </div>
            <p class="text-sm text-slate-500 mt-0.5">
              Последняя синхронизация: {{ formattedSyncAt }}
            </p>
          </div>
        </div>
        
        <div class="flex items-center gap-3">
          <button
            @click="handleSync"
            :disabled="isSyncing"
            class="flex items-center gap-2 px-4 py-2 bg-slate-50 text-slate-700 border border-slate-200 rounded-lg text-sm font-medium hover:bg-slate-100 transition-all disabled:opacity-50"
          >
            <RefreshCw class="h-4 w-4" :class="{ 'animate-spin': isSyncing }" />
            {{ isSyncing ? 'Синхронизация...' : 'Обновить данные' }}
          </button>
        </div>
      </div>

      <div v-if="warning" class="mt-6 bg-yellow-50 border border-yellow-200 rounded-xl p-4 flex items-start gap-3">
        <AlertTriangle class="h-5 w-5 text-yellow-500 flex-shrink-0 mt-0.5" />
        <div class="flex-1">
          <p class="text-sm text-yellow-800 font-medium">Внимание</p>
          <p class="text-sm text-yellow-700 mt-0.5">{{ warning }}</p>
        </div>
        <button @click="$emit('close-warning')" class="text-yellow-500 hover:text-yellow-600">
          <X class="h-4 w-4" />
        </button>
      </div>
    </div>

    <div class="bg-white rounded-2xl border border-slate-200 p-6 shadow-sm space-y-6">
      <Tabs v-model:value="activeTab">
        <TabsList className="bg-slate-50/70 p-1 rounded-xl">
          <TabsTrigger value="services">Услуги</TabsTrigger>
          <TabsTrigger value="specialists">Специалисты</TabsTrigger>
          <TabsTrigger value="categories">Категории</TabsTrigger>
        </TabsList>

        <TabsContent value="services">
          <div class="space-y-0.5 border border-slate-100 rounded-2xl overflow-hidden">
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
                      @click="handleBulkUpdate(true)"
                      class="text-xs font-bold text-indigo-600 hover:text-indigo-800 transition-colors"
                    >
                      Включить выбранные
                    </button>
                    <button
                      @click="handleBulkUpdate(false)"
                      class="text-xs font-bold text-red-600 hover:text-red-800 transition-colors"
                    >
                      Отключить выбранные
                    </button>
                  </div>
                </div>
                <button
                  @click="selectedIds = []"
                  class="text-xs font-medium text-slate-500 hover:text-slate-700"
                >
                  Сбросить выбор
                </button>
              </div>
            </Transition>

            <div class="overflow-x-auto bg-white">
              <Table>
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
                    <TableHead>Услуга</TableHead>
                    <TableHead>Категория</TableHead>
                    <TableHead>Цена</TableHead>
                    <TableHead>Длительность</TableHead>
                    <TableHead>Статус</TableHead>
                    <TableHead className="w-24">Приоритет</TableHead>
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
                    v-for="service in services"
                    :key="service.id"
                    :class="[
                      'hover:bg-slate-50/50 transition-colors',
                      selectedIds.includes(service.id) ? 'bg-indigo-50/20' : ''
                    ]"
                  >
                    <TableCell>
                      <input
                        type="checkbox"
                        :checked="selectedIds.includes(service.id)"
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
            </div>

            <div class="p-4 border-t border-slate-100 bg-slate-50/30 flex items-center justify-between">
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
          <div class="space-y-0.5 border border-slate-100 rounded-2xl overflow-hidden">
            <div class="p-6 border-b border-slate-100 space-y-4">
              <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <h3 class="text-lg font-bold text-slate-900">Специалисты</h3>
                <div class="flex flex-wrap items-center gap-3">
                  <div class="relative">
                    <Search class="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                    <input
                      v-model="specialistSearch"
                      type="text"
                      placeholder="Поиск специалистов..."
                      class="pl-9 pr-4 py-2 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-indigo-500 focus:bg-white transition-all w-64"
                    />
                  </div>
                  <span class="text-sm text-slate-500">Всего: {{ specialists.length }}</span>
                </div>
              </div>
            </div>

            <div class="overflow-x-auto bg-white">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Имя</TableHead>
                    <TableHead>Роль</TableHead>
                    <TableHead>Услуг</TableHead>
                    <TableHead>Статус</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow v-if="isSpecialistsLoading" v-for="i in 5" :key="`spec-skel-${i}`" class="animate-pulse">
                    <TableCell><div class="h-4 w-24 bg-slate-100 rounded"></div></TableCell>
                    <TableCell><div class="h-4 w-32 bg-slate-100 rounded"></div></TableCell>
                    <TableCell><div class="h-4 w-16 bg-slate-100 rounded"></div></TableCell>
                    <TableCell><div class="h-4 w-12 bg-slate-100 rounded"></div></TableCell>
                  </TableRow>
                  <TableRow v-else-if="filteredSpecialists.length === 0">
                    <TableCell :colspan="4" className="p-12 text-center text-slate-400 italic">
                      Специалисты не найдены
                    </TableCell>
                  </TableRow>
                  <TableRow
                    v-else
                    v-for="specialist in filteredSpecialists"
                    :key="specialist.id"
                    :class="[
                      'hover:bg-slate-50/50 transition-colors',
                      specialist.is_active ? 'bg-emerald-50/30' : ''
                    ]"
                  >
                    <TableCell>
                      <p class="text-sm font-bold text-slate-900">{{ specialist.name }}</p>
                      <p class="text-[10px] text-slate-500 mt-0.5">
                        {{ specialist.email || specialist.phone || '' }}
                      </p>
                    </TableCell>
                    <TableCell>
                      <span class="text-sm text-slate-600 capitalize">{{ specialist.role || 'Специалист' }}</span>
                    </TableCell>
                    <TableCell>
                      <span class="text-sm text-slate-600">{{ specialist.services_count ?? specialist.linked_services ?? '-' }}</span>
                    </TableCell>
                    <TableCell>
                      <span
                        class="inline-flex items-center px-3 py-0.5 rounded-full text-xs font-semibold"
                        :class="specialist.is_active ? 'bg-emerald-50 text-emerald-600' : 'bg-slate-100 text-slate-500'"
                      >
                        {{ specialist.is_active ? 'Активен' : 'Отключён' }}
                      </span>
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </div>

            <div class="p-4 border-t border-slate-100 bg-slate-50/30 text-xs text-slate-500">
              {{ filteredSpecialists.length }} из {{ specialists.length }} специалистов отображаются
            </div>
          </div>
        </TabsContent>

        <TabsContent value="categories">
          <div class="space-y-0.5 border border-slate-100 rounded-2xl overflow-hidden">
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

            <div class="overflow-x-auto bg-white">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Категория</TableHead>
                    <TableHead>Услуг</TableHead>
                    <TableHead>Статус</TableHead>
                    <TableHead>Приоритет</TableHead>
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
                    v-for="cat in filteredCategories"
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
            </div>

            <div class="p-4 border-t border-slate-100 bg-slate-50/30 text-xs text-slate-500">
              {{ filteredCategories.length }} из {{ categories.length }} категорий отображаются
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { 
  Link, 
  RefreshCw, 
  AlertTriangle, 
  X, 
  Search, 
  ChevronLeft, 
  ChevronRight
} from 'lucide-vue-next'
import { useAgents } from '../composables/useAgents'
import { useToast } from '../composables/useToast'
import { getReadableErrorMessage } from '~/utils/api-errors'
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

const { 
  syncSqns, 
  fetchSqnsServicesCached, 
  updateSqnsService, 
  bulkUpdateSqnsServices,
  fetchSqnsCategories,
  fetchSqnsSpecialists,
  updateSqnsCategory
} = useAgents()
const { success: toastSuccess, error: toastError } = useToast()

// State
const isSyncing = ref(false)
const isLoading = ref(false)
const services = ref<any[]>([])
const total = ref(0)
const categories = ref<any[]>([])
const selectedIds = ref<string[]>([])
const isCategoriesLoading = ref(false)
const categorySearch = ref('')
const showOnlyEnabledCategories = ref(false)
const activeTab = ref<'services' | 'specialists' | 'categories'>('services')
const specialists = ref<any[]>([])
const isSpecialistsLoading = ref(false)
const specialistSearch = ref('')

const filters = ref({
  search: '',
  category: null as string | null,
  is_enabled: null as boolean | null
})

const pagination = ref({
  limit: 50,
  offset: 0
})

const currentPage = computed(() => Math.floor(pagination.value.offset / pagination.value.limit) + 1)
const isAllSelected = computed(() => services.value.length > 0 && services.value.every(s => selectedIds.value.includes(s.id)))

const formattedSyncAt = computed(() => {
  if (!props.lastSyncAt) return 'нет данных'
  const date = new Date(props.lastSyncAt)
  return date.toLocaleString('ru-RU', { dateStyle: 'medium', timeStyle: 'short' })
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

const handleSync = async () => {
  try {
    isSyncing.value = true
    const result = await syncSqns(props.agentId)
    toastSuccess(
      'Синхронизация завершена',
      `Обновлено: ${result.resources_synced} специалистов, ${result.services_synced} услуг, ${result.categories_synced} категорий`
    )
    emit('sync-complete')
    await Promise.all([
      loadServices(true),
      loadCategories(true),
      loadSpecialists(true)
    ])
  } catch (err: any) {
    toastError('Ошибка синхронизации', getReadableErrorMessage(err, 'Не удалось выполнить синхронизацию'))
  } finally {
    isSyncing.value = false
  }
}

const handleToggleService = async (service: any) => {
  const originalState = Boolean(service.is_enabled)
  const nextState = !originalState
  
  // Оптимистичное обновление UI сразу
  service.is_enabled = nextState
  
  console.log('🔧 Toggle service:', {
    serviceId: service.id,
    serviceIdType: typeof service.id,
    serviceName: service.name,
    originalState,
    nextState,
    payload: { is_enabled: nextState }
  })
  
  try {
    // Отправляем на сервер новое состояние
    await updateSqnsService(props.agentId, service.id, { is_enabled: nextState })
    
    console.log('✅ Toggle успешно, перезагружаем список...')
    
    // Перезагружаем список с сервера для финальной синхронизации (тихо)
    await loadServices(true)
    
    toastSuccess('Статус обновлен', `Услуга "${service.name}" ${nextState ? 'включена' : 'отключена'}`)
  } catch (err: any) {
    // Откатываем UI при ошибке
    service.is_enabled = originalState
    toastError('Ошибка', getReadableErrorMessage(err, 'Не удалось изменить статус услуги'))
    console.error('❌ Toggle error:', err)
    // Перезагружаем список для отката к реальному состоянию
    await loadServices()
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
    await loadServices(true)
    toastSuccess('Приоритет обновлен', `Для услуги "${service.name}" установлен приоритет ${nextPriority}`)
  } catch (err: any) {
    toastError('Ошибка', getReadableErrorMessage(err, 'Не удалось обновить приоритет услуги'))
    await loadServices(true)
  }
}

const handleBulkUpdate = async (is_enabled: boolean) => {
  if (!confirm(`Вы уверены? ${selectedIds.value.length} услуг будут ${is_enabled ? 'включены' : 'отключены'}`)) return
  
  try {
    await bulkUpdateSqnsServices(props.agentId, {
      ids: selectedIds.value,
      is_enabled
    })
    selectedIds.value = []
    await loadServices(true)
    toastSuccess('Массовое обновление', `Успешно обновлено ${selectedIds.value.length} услуг`)
  } catch (err: any) {
    toastError('Ошибка', getReadableErrorMessage(err, 'Не удалось выполнить массовое обновление'))
    await loadServices(true)
  }
}

const handleToggleCategory = async (cat: any) => {
  const originalState = cat.is_enabled
  const nextState = !originalState
  
  // Оптимистичное обновление UI
  cat.is_enabled = nextState
  
  try {
    await updateSqnsCategory(props.agentId, cat.id, { is_enabled: nextState })
    // Тихое обновление данных с сервера
    await loadCategories(true)
    toastSuccess('Статус категории обновлен', `Категория "${cat.name}" ${nextState ? 'включена' : 'отключена'}`)
  } catch (err: any) {
    // Откат при ошибке
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
    // Тихое обновление данных с сервера
    await loadCategories(true)
    toastSuccess('Приоритет категории обновлен', `Для категории "${cat.name}" установлен приоритет ${nextPriority}`)
  } catch (err: any) {
    toastError('Ошибка', getReadableErrorMessage(err, 'Не удалось обновить приоритет категории'))
    await loadCategories(true)
  }
}

const toggleSelect = (id: string) => {
  const index = selectedIds.value.indexOf(id)
  if (index === -1) selectedIds.value.push(id)
  else selectedIds.value.splice(index, 1)
}

const toggleSelectAll = () => {
  if (isAllSelected.value) {
    selectedIds.value = selectedIds.value.filter(id => !services.value.some(s => s.id === id))
  } else {
    services.value.forEach(s => {
      if (!selectedIds.value.includes(s.id)) selectedIds.value.push(s.id)
    })
  }
}

const handlePageChange = (delta: number) => {
  pagination.value.offset += delta * pagination.value.limit
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
  if (tab === 'specialists' && specialists.value.length === 0) {
    loadSpecialists()
  }
  if (tab === 'categories' && categories.value.length === 0) {
    loadCategories()
  }
})

onMounted(() => {
  loadServices()
  loadCategories()
  loadSpecialists()
})
</script>
