<template>
  <div class="max-w-full space-y-6 overflow-hidden">
    <!-- Две большие CTA-карточки — как в разделе функций -->
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <button
        type="button"
        class="group flex items-center gap-4 rounded-2xl border-2 border-dashed border-primary/40 bg-primary/[0.04] p-5 text-left transition-all duration-300 hover:-translate-y-0.5 hover:border-primary/70 hover:bg-primary/[0.08]"
        @click="$emit('open-catalog')"
      >
        <div class="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-white text-primary shadow-[0_2px_8px_-2px_rgba(59,130,246,0.15)] transition-transform group-hover:scale-105">
          <LayoutGrid class="h-5 w-5" />
        </div>
        <div class="min-w-0">
          <div class="text-sm font-semibold text-primary">+ Добавить готовый</div>
          <div class="mt-1 text-xs leading-relaxed text-slate-600">
            Выберите готовый сценарий из каталога — популярные кейсы, минимум настроек
          </div>
        </div>
      </button>

      <button
        type="button"
        class="group flex items-center gap-4 rounded-2xl border-2 border-dashed border-slate-200 bg-white p-5 text-left transition-all duration-300 hover:-translate-y-0.5 hover:border-primary/40 hover:bg-slate-50"
        @click="$emit('create')"
      >
        <div class="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-500 transition-colors group-hover:bg-primary/10 group-hover:text-primary">
          <Plus class="h-5 w-5" />
        </div>
        <div class="min-w-0">
          <div class="text-sm font-semibold text-slate-900 transition-colors group-hover:text-primary">+ Создать свой</div>
          <div class="mt-1 text-xs leading-relaxed text-slate-600">
            Добавьте свой сценарий, самостоятельно настроив триггер и действия
          </div>
        </div>
      </button>
    </div>

    <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-end">
      <div v-if="scenarios.length > 0" class="relative min-w-0 grow sm:grow-0">
        <Search class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Поиск по названию..."
          class="h-10 w-full min-w-0 rounded-xl border border-slate-200 bg-slate-50 py-2 pl-9 pr-4 text-sm transition-all duration-300 outline-none focus:border-indigo-400 focus:bg-white focus:ring-4 focus:ring-indigo-500/10 sm:w-64"
        />
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="loading" class="flex justify-center py-12">
      <Loader2 class="w-8 h-8 animate-spin text-indigo-600" />
    </div>

    <!-- Error State -->
    <div 
      v-else-if="error"
      class="rounded-3xl border border-red-200 bg-red-50 p-8 text-center"
    >
      <div class="max-w-md mx-auto">
        <div class="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <AlertCircle class="h-8 w-8 text-red-500" />
        </div>
        <h3 class="text-lg font-bold text-red-900">Ошибка загрузки</h3>
        <p class="text-red-600 mt-2 mb-4">{{ error }}</p>
        <button
          @click="$emit('retry')"
          class="rounded-xl bg-red-600 px-5 py-2.5 text-sm font-bold text-white transition-colors hover:bg-red-700"
        >
          Повторить
        </button>
      </div>
    </div>

    <!-- Empty State -->
    <div 
      v-else-if="scenarios.length === 0" 
      class="rounded-3xl border-2 border-dashed border-slate-100 bg-white p-12 text-center"
    >
      <div class="max-w-md mx-auto">
        <div class="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <ListTree class="h-8 w-8 text-slate-400" />
        </div>
        <h3 class="text-lg font-bold text-slate-900">Сценариев пока нет</h3>
        <p class="text-slate-500 mt-2">
          Создайте сценарии для автоматизации ответов агента на основе различных событий и условий.
        </p>
      </div>
    </div>

    <!-- No Results -->
    <div 
      v-else-if="filteredScenarios.length === 0" 
      class="rounded-3xl border border-slate-100 bg-white p-8 text-center"
    >
      <p class="text-slate-500">Ничего не найдено по запросу "{{ searchQuery }}"</p>
    </div>

    <!-- Scenarios Grid -->
    <div v-else class="flex w-full min-w-0 flex-col gap-4">
      <ScenarioCard
        v-for="scenario in filteredScenarios"
        :key="scenario.id"
        :scenario="scenario"
        @click="$emit('select', scenario)"
        @toggle="(enabled) => $emit('toggle', scenario.id, enabled)"
        @settings="$emit('settings', scenario)"
        @delete="$emit('delete', scenario)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Plus, Search, Loader2, ListTree, AlertCircle, LayoutGrid } from 'lucide-vue-next'
import ScenarioCard from './ScenarioCard.vue'
import type { Scenario } from '~/types/scenario'

const props = defineProps<{
  scenarios: Scenario[]
  loading?: boolean
  error?: string | null
}>()

defineEmits<{
  (e: 'create'): void
  (e: 'open-catalog'): void
  (e: 'select', scenario: Scenario): void
  (e: 'toggle', id: string, enabled: boolean): void
  (e: 'settings', scenario: Scenario): void
  (e: 'delete', scenario: Scenario): void
  (e: 'retry'): void
}>()

const searchQuery = ref('')

const filteredScenarios = computed(() => {
  if (!searchQuery.value.trim()) {
    return props.scenarios
  }
  const query = searchQuery.value.toLowerCase()
  return props.scenarios.filter(s => 
    s.name.toLowerCase().includes(query)
  )
})
</script>
