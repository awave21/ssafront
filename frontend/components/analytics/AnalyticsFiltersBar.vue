<template>
  <div class="bg-white rounded-3xl border border-slate-100 p-6 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
    <div
      v-if="loading && !agents.length"
      class="grid grid-cols-1 gap-6 lg:grid-cols-12"
      aria-hidden="true"
    >
      <div class="lg:col-span-2 space-y-2">
        <Skeleton diagonal-shimmer :shimmer-delay-ms="0" class="h-3 w-14" />
        <Skeleton diagonal-shimmer :shimmer-delay-ms="40" class="h-11 w-full rounded-xl" />
      </div>
      <div class="lg:col-span-2 space-y-2">
        <Skeleton diagonal-shimmer :shimmer-delay-ms="100" class="h-3 w-16" />
        <Skeleton diagonal-shimmer :shimmer-delay-ms="140" class="h-11 w-full rounded-xl" />
      </div>
      <div class="lg:col-span-2 space-y-2">
        <Skeleton diagonal-shimmer :shimmer-delay-ms="200" class="h-3 w-20" />
        <Skeleton diagonal-shimmer :shimmer-delay-ms="240" class="h-11 w-full rounded-xl" />
      </div>
      <div class="lg:col-span-4 space-y-2">
        <Skeleton diagonal-shimmer :shimmer-delay-ms="300" class="h-3 w-24" />
        <Skeleton diagonal-shimmer :shimmer-delay-ms="340" class="h-11 w-full rounded-xl" />
      </div>
      <div class="lg:col-span-2 flex items-end gap-2">
        <Skeleton diagonal-shimmer :shimmer-delay-ms="420" class="h-11 flex-1 rounded-xl" />
        <Skeleton diagonal-shimmer :shimmer-delay-ms="460" class="h-11 flex-1 rounded-xl" />
      </div>
    </div>

    <div v-else class="grid grid-cols-1 gap-6 lg:grid-cols-12">
      <div class="lg:col-span-2">
        <label class="mb-2 block text-[10px] font-black uppercase tracking-widest text-slate-400">Агент</label>
        <Select :model-value="filters.agentId" @update:model-value="onAgentChange">
          <SelectTrigger class="w-full bg-slate-50/50 border-slate-100 h-11 focus:ring-2 focus:ring-primary/20 transition-all rounded-xl">
            <SelectValue placeholder="Выберите агента" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem
              v-for="agent in agents"
              :key="agent.id"
              :value="agent.id"
            >
              {{ agent.name }}
            </SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div class="lg:col-span-2">
        <label class="mb-2 block text-[10px] font-black uppercase tracking-widest text-slate-400">Период</label>
        <Select :model-value="filters.periodPreset" @update:model-value="onPresetChange">
          <SelectTrigger class="w-full bg-slate-50/50 border-slate-100 h-11 focus:ring-2 focus:ring-primary/20 transition-all rounded-xl">
            <SelectValue placeholder="Период" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="7d">7 дней</SelectItem>
            <SelectItem value="30d">30 дней</SelectItem>
            <SelectItem value="90d">90 дней</SelectItem>
            <SelectItem value="custom">Свой период</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div class="lg:col-span-2">
        <label class="mb-2 block text-[10px] font-black uppercase tracking-widest text-slate-400">Теги клиента</label>
        <div class="relative group">
          <Input
            v-model="tagsInput"
            placeholder="vip, семейный..."
            class="h-11 bg-slate-50/50 border-slate-100 focus:ring-2 focus:ring-primary/20 transition-all pl-4 rounded-xl"
            @keydown.enter.prevent="applyTags"
            @blur="applyTags"
          />
        </div>
      </div>

      <div v-if="SHOW_CHANNEL_FILTER" class="lg:col-span-2">
        <label class="mb-2 block text-[10px] font-black uppercase tracking-widest text-slate-400">Канал</label>
        <Select :model-value="filters.channel || '__all__'" @update:model-value="onChannelChange">
          <SelectTrigger class="w-full bg-slate-50/50 border-slate-100 h-11 focus:ring-2 focus:ring-primary/20 transition-all rounded-xl">
            <SelectValue placeholder="Все каналы" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__all__">Все каналы</SelectItem>
            <SelectItem
              v-for="channel in channels"
              :key="channel.value"
              :value="channel.value"
            >
              {{ channel.label }}
            </SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div :class="SHOW_CHANNEL_FILTER ? 'lg:col-span-2' : 'lg:col-span-4'">
        <label class="mb-2 block text-[10px] font-black uppercase tracking-widest text-slate-400">Сотрудник</label>
        <Select
          :model-value="filters.resourceExternalId === null ? '__all__' : String(filters.resourceExternalId)"
          @update:model-value="onResourceChange"
        >
          <SelectTrigger class="w-full bg-slate-50/50 border-slate-100 h-11 focus:ring-2 focus:ring-primary/20 transition-all rounded-xl">
            <SelectValue placeholder="Все сотрудники" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__all__">Все сотрудники</SelectItem>
            <SelectItem
              v-for="resource in resources"
              :key="resource.id"
              :value="String(resource.id)"
            >
              {{ resource.name }}
            </SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div class="flex items-end gap-2 lg:col-span-2">
        <Button
          variant="ghost"
          class="flex-1 h-11 text-slate-400 hover:bg-slate-50 hover:text-slate-900 transition-colors rounded-xl font-bold text-xs"
          :disabled="loading"
          @click="emit('reset')"
        >
          Сброс
        </Button>
        <Button
          class="flex-1 h-11 bg-primary hover:bg-primary/90 shadow-lg shadow-primary/20 transition-all active:scale-95 rounded-xl font-bold text-xs"
          :disabled="loading || !filters.agentId"
          @click="emit('refresh')"
        >
          <span v-if="!loading">Обновить</span>
          <div v-else class="h-4 w-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
        </Button>
      </div>
    </div>


    <div
      v-if="filters.periodPreset === 'custom'"
      class="mt-6 pt-6 border-t border-slate-100 grid grid-cols-1 gap-6 md:grid-cols-2 lg:max-w-xl animate-in fade-in slide-in-from-top-2 duration-300"
    >
      <div>
        <label class="mb-2 block text-[11px] font-semibold uppercase tracking-wider text-slate-400">Дата с</label>
        <Input
          :model-value="filters.dateFrom"
          type="date"
          class="h-11 bg-slate-50 border-none focus:ring-2 focus:ring-primary/20 transition-all"
          @update:model-value="value => emit('update-filters', { dateFrom: String(value) })"
        />
      </div>
      <div>
        <label class="mb-2 block text-[11px] font-semibold uppercase tracking-wider text-slate-400">Дата по</label>
        <Input
          :model-value="filters.dateTo"
          type="date"
          class="h-11 bg-slate-50 border-none focus:ring-2 focus:ring-primary/20 transition-all"
          @update:model-value="value => emit('update-filters', { dateTo: String(value) })"
        />
      </div>
    </div>

    <div
      v-if="tags.length"
      class="mt-6 flex flex-wrap items-center gap-2 pt-6 border-t border-slate-100"
    >
      <span class="text-[11px] font-bold uppercase tracking-wider text-slate-400 mr-2">Быстрые теги:</span>
      <Badge
        v-for="tag in quickTagOptions"
        :key="tag.value"
        variant="secondary"
        class="cursor-pointer transition-all px-3 py-1.5 border-none"
        :class="isTagSelected(tag.value)
          ? 'bg-primary text-white scale-105 shadow-md shadow-primary/20'
          : 'bg-slate-100 text-slate-600 hover:bg-slate-200'"
        @click="toggleQuickTag(tag.value)"
      >
        {{ tag.label }}
      </Badge>
    </div>

    <div class="mt-6 flex flex-wrap items-center gap-x-6 gap-y-2 pt-6 border-t border-slate-100">
      <span class="text-[10px] font-black uppercase tracking-widest text-slate-400">Способ оплаты:</span>
      <label
        v-for="option in PAYMENT_METHOD_OPTIONS"
        :key="option.value"
        class="flex cursor-pointer items-center gap-2 select-none"
        @click.prevent="togglePaymentMethod(option.value)"
      >
        <span
          class="flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-all"
          :class="isPaymentMethodSelected(option.value)
            ? 'border-primary bg-primary text-white'
            : 'border-slate-300 bg-white'"
        >
          <svg v-if="isPaymentMethodSelected(option.value)" viewBox="0 0 10 8" class="h-2.5 w-2.5 fill-none stroke-current stroke-[1.8]">
            <polyline points="1,4 3.5,6.5 9,1" />
          </svg>
        </span>
        <span class="text-sm font-medium text-slate-700">{{ option.label }}</span>
      </label>
    </div>

    <div class="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-slate-100 pt-4">
      <span class="text-[10px] font-black uppercase tracking-widest text-slate-400">Тип выручки:</span>
      <label
        v-for="option in REVENUE_CATEGORY_OPTIONS"
        :key="option.value"
        class="flex cursor-pointer items-center gap-2 select-none"
        @click.prevent="toggleRevenueCategory(option.value)"
      >
        <span
          class="flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-all"
          :class="isRevenueCategorySelected(option.value)
            ? 'border-primary bg-primary text-white'
            : 'border-slate-300 bg-white'"
        >
          <svg v-if="isRevenueCategorySelected(option.value)" viewBox="0 0 10 8" class="h-2.5 w-2.5 fill-none stroke-current stroke-[1.8]">
            <polyline points="1,4 3.5,6.5 9,1" />
          </svg>
        </span>
        <span class="text-sm font-medium text-slate-700">{{ option.label }}</span>
      </label>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

/** Временно скрыт по продуктовому решению; вернуть true, чтобы снова показать фильтр по каналам. */
const SHOW_CHANNEL_FILTER = false
import { Badge } from '~/components/ui/badge'
import { Skeleton } from '~/components/ui/skeleton'
import Button from '~/components/ui/button/Button.vue'
import Input from '~/components/ui/input/Input.vue'
import Select from '~/components/ui/select/Select.vue'
import SelectContent from '~/components/ui/select/SelectContent.vue'
import SelectItem from '~/components/ui/select/SelectItem.vue'
import SelectTrigger from '~/components/ui/select/SelectTrigger.vue'
import SelectValue from '~/components/ui/select/SelectValue.vue'
import type {
  AnalyticsAgentOption,
  AnalyticsFilterOption,
  AnalyticsFilters,
  AnalyticsPaymentMethod,
  AnalyticsPeriodPreset,
  AnalyticsResourceOption,
  AnalyticsRevenueCategory,
} from '~/types/analytics'

type FiltersPatch = Partial<AnalyticsFilters>

const props = defineProps<{
  filters: AnalyticsFilters
  agents: AnalyticsAgentOption[]
  channels: AnalyticsFilterOption[]
  tags: AnalyticsFilterOption[]
  resources: AnalyticsResourceOption[]
  loading: boolean
}>()

const emit = defineEmits<{
  (e: 'update-filters', patch: FiltersPatch): void
  (e: 'refresh'): void
  (e: 'reset'): void
}>()

const quickTagOptions = computed(() => props.tags.slice(0, 12))
const tagsInput = ref('')

watch(
  () => props.filters.clientTags,
  (next) => {
    tagsInput.value = next.join(', ')
  },
  { immediate: true, deep: true },
)

const onAgentChange = (value: string | number) => {
  emit('update-filters', { agentId: String(value) })
}

const onPresetChange = (value: string | number) => {
  emit('update-filters', { periodPreset: String(value) as AnalyticsPeriodPreset })
}

const onChannelChange = (value: string | number) => {
  const normalized = String(value)
  emit('update-filters', { channel: normalized === '__all__' ? '' : normalized })
}

const onResourceChange = (value: string | number) => {
  const normalized = String(value)
  if (normalized === '__all__') {
    emit('update-filters', { resourceExternalId: null })
    return
  }
  const numeric = Number(normalized)
  emit('update-filters', {
    resourceExternalId: Number.isFinite(numeric) ? numeric : null,
  })
}

const parseTags = (raw: string) =>
  Array.from(
    new Set(
      raw
        .split(',')
        .map(item => item.trim().toLowerCase())
        .filter(Boolean),
    ),
  )

const applyTags = () => {
  emit('update-filters', { clientTags: parseTags(tagsInput.value) })
}

const isTagSelected = (value: string) => props.filters.clientTags.includes(value)

const toggleQuickTag = (value: string) => {
  const next = new Set(props.filters.clientTags)
  if (next.has(value)) {
    next.delete(value)
  } else {
    next.add(value)
  }
  emit('update-filters', { clientTags: Array.from(next) })
}

const PAYMENT_METHOD_OPTIONS: { value: AnalyticsPaymentMethod; label: string }[] = [
  { value: 'cash', label: 'Наличные' },
  { value: 'card', label: 'Безналичные' },
  { value: 'certificate', label: 'Сертификаты' },
]

const isPaymentMethodSelected = (method: AnalyticsPaymentMethod) => {
  const methods = props.filters.paymentMethods ?? []
  return methods.length === 0 || methods.includes(method)
}

const togglePaymentMethod = (method: AnalyticsPaymentMethod) => {
  const current = props.filters.paymentMethods ?? []
  const allSelected = current.length === 0

  const currentSet: Set<AnalyticsPaymentMethod> = allSelected
    ? new Set(PAYMENT_METHOD_OPTIONS.map(o => o.value))
    : new Set(current)

  if (currentSet.has(method)) {
    currentSet.delete(method)
  } else {
    currentSet.add(method)
  }

  const allMethods = PAYMENT_METHOD_OPTIONS.map(o => o.value)
  const next = allMethods.every(m => currentSet.has(m)) ? [] : Array.from(currentSet)
  emit('update-filters', { paymentMethods: next })
}

const REVENUE_CATEGORY_OPTIONS: { value: AnalyticsRevenueCategory; label: string }[] = [
  { value: 'services', label: 'Услуги' },
  { value: 'commodities', label: 'Товары' },
]

const isRevenueCategorySelected = (cat: AnalyticsRevenueCategory) => {
  const list = props.filters.revenueCategories ?? []
  return list.length === 0 || list.includes(cat)
}

const toggleRevenueCategory = (cat: AnalyticsRevenueCategory) => {
  const current = props.filters.revenueCategories ?? []
  const allSelected = current.length === 0
  const currentSet: Set<AnalyticsRevenueCategory> = allSelected
    ? new Set(REVENUE_CATEGORY_OPTIONS.map(o => o.value))
    : new Set(current)
  if (currentSet.has(cat)) currentSet.delete(cat)
  else currentSet.add(cat)
  const allCats = REVENUE_CATEGORY_OPTIONS.map(o => o.value)
  const next = allCats.every(c => currentSet.has(c)) ? [] : Array.from(currentSet)
  emit('update-filters', { revenueCategories: next })
}
</script>
