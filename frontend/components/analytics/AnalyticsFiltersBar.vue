<template>
  <div class="bg-white rounded-3xl border border-slate-100 p-6 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
    <div class="grid grid-cols-1 gap-6 lg:grid-cols-12">
      <div class="lg:col-span-3">
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

      <div class="lg:col-span-3">
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
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Badge } from '~/components/ui/badge'
import Button from '~/components/ui/button/Button.vue'
import Input from '~/components/ui/input/Input.vue'
import Select from '~/components/ui/select/Select.vue'
import SelectContent from '~/components/ui/select/SelectContent.vue'
import SelectItem from '~/components/ui/select/SelectItem.vue'
import SelectTrigger from '~/components/ui/select/SelectTrigger.vue'
import SelectValue from '~/components/ui/select/SelectValue.vue'
import type { AnalyticsAgentOption, AnalyticsFilterOption, AnalyticsFilters, AnalyticsPeriodPreset } from '~/types/analytics'

type FiltersPatch = Partial<AnalyticsFilters>

const props = defineProps<{
  filters: AnalyticsFilters
  agents: AnalyticsAgentOption[]
  channels: AnalyticsFilterOption[]
  tags: AnalyticsFilterOption[]
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
</script>
