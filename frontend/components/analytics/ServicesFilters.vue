<template>
  <div class="bg-white rounded-3xl border border-slate-100 p-6 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
    <div class="grid grid-cols-1 gap-6 lg:grid-cols-12">
      <div class="lg:col-span-3">
        <label class="mb-2 block text-[10px] font-black uppercase tracking-widest text-slate-400">Агент</label>
        <Select :model-value="selectedAgentId" @update:model-value="onAgentChange">
          <SelectTrigger class="h-11 bg-slate-50/50 border-slate-100 focus:ring-2 focus:ring-primary/20 transition-all rounded-xl">
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
        <label class="mb-2 block text-[10px] font-black uppercase tracking-widest text-slate-400">Дата с</label>
        <Input
          :model-value="query.dateFrom"
          type="date"
          class="h-11 bg-slate-50/50 border-slate-100 focus:ring-2 focus:ring-primary/20 transition-all rounded-xl"
          @update:model-value="value => emitUpdate({ dateFrom: String(value) })"
        />
      </div>

      <div class="lg:col-span-2">
        <label class="mb-2 block text-[10px] font-black uppercase tracking-widest text-slate-400">Дата по</label>
        <Input
          :model-value="query.dateTo"
          type="date"
          class="h-11 bg-slate-50/50 border-slate-100 focus:ring-2 focus:ring-primary/20 transition-all rounded-xl"
          @update:model-value="value => emitUpdate({ dateTo: String(value) })"
        />
      </div>

      <div class="lg:col-span-3">
        <label class="mb-2 block text-[10px] font-black uppercase tracking-widest text-slate-400">Сотрудник</label>
        <Select :model-value="query.resourceExternalId === null ? '__all__' : String(query.resourceExternalId)" @update:model-value="onResourceChange">
          <SelectTrigger class="h-11 bg-slate-50/50 border-slate-100 focus:ring-2 focus:ring-primary/20 transition-all rounded-xl">
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

      <div class="lg:col-span-2">
        <label class="mb-2 block text-[10px] font-black uppercase tracking-widest text-slate-400">Канал</label>
        <Select :model-value="query.channel || '__all__'" @update:model-value="onChannelChange">
          <SelectTrigger class="h-11 bg-slate-50/50 border-slate-100 focus:ring-2 focus:ring-primary/20 transition-all rounded-xl">
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
        <label class="mb-2 block text-[10px] font-black uppercase tracking-widest text-slate-400">Теги</label>
        <Input
          v-model="tagsInput"
          class="h-11 bg-slate-50/50 border-slate-100 focus:ring-2 focus:ring-primary/20 transition-all rounded-xl"
          placeholder="vip, семейный..."
        />
      </div>

      <div class="flex items-end gap-2 lg:col-span-3">
        <Button 
          variant="ghost" 
          class="flex-1 h-11 text-slate-400 hover:bg-slate-50 hover:text-slate-900 transition-colors rounded-xl font-bold text-xs"
          :disabled="loading" 
          @click="emit('reset')"
        >
          Сброс
        </Button>
        <Button 
          class="flex-1 h-11 bg-primary hover:bg-primary/90 shadow-lg shadow-primary/20 transition-all active:scale-95 rounded-xl font-bold text-xs text-white"
          :disabled="loading" 
          @click="emit('refresh')"
        >
          Обновить
        </Button>
        <div class="flex gap-2">
          <Button 
            variant="secondary" 
            size="icon"
            class="h-11 w-11 rounded-xl bg-slate-50 border-slate-100 hover:bg-slate-100 transition-all shrink-0"
            :disabled="loading" 
            title="CSV (страница)"
            @click="emit('export-current')"
          >
            <FileText class="h-4 w-4 text-slate-500" />
          </Button>
          <Button 
            variant="secondary" 
            size="icon"
            class="h-11 w-11 rounded-xl bg-slate-50 border-slate-100 hover:bg-slate-100 transition-all shrink-0"
            :disabled="loading" 
            title="CSV (все)"
            @click="emit('export-all')"
          >
            <Download class="h-4 w-4 text-slate-500" />
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { watch, ref } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import { FileText, Download } from 'lucide-vue-next'
import Button from '~/components/ui/button/Button.vue'
import Input from '~/components/ui/input/Input.vue'
import Select from '~/components/ui/select/Select.vue'
import SelectContent from '~/components/ui/select/SelectContent.vue'
import SelectItem from '~/components/ui/select/SelectItem.vue'
import SelectTrigger from '~/components/ui/select/SelectTrigger.vue'
import SelectValue from '~/components/ui/select/SelectValue.vue'
import type { AnalyticsFilterOption, AnalyticsResourceOption, ServicesTableQuery } from '~/types/analytics'

const props = defineProps<{
  query: ServicesTableQuery
  agents: { id: string; name: string }[]
  selectedAgentId: string
  channels: AnalyticsFilterOption[]
  resources: AnalyticsResourceOption[]
  loading: boolean
}>()

const emit = defineEmits<{
  (e: 'update-query', patch: Partial<ServicesTableQuery>): void
  (e: 'update-agent-id', agentId: string): void
  (e: 'refresh'): void
  (e: 'reset'): void
  (e: 'export-current'): void
  (e: 'export-all'): void
}>()

const emitUpdate = (patch: Partial<ServicesTableQuery>) => emit('update-query', patch)

const onAgentChange = (value: string | number) => {
  emit('update-agent-id', String(value))
}

const onResourceChange = (value: string | number) => {
  const normalized = String(value)
  const numeric = Number(normalized)
  emitUpdate({
    resourceExternalId: normalized === '__all__'
      ? null
      : Number.isFinite(numeric)
        ? numeric
        : normalized,
  })
}

const onChannelChange = (value: string | number) => {
  const normalized = String(value)
  emitUpdate({
    channel: normalized === '__all__' ? '' : normalized,
  })
}

const tagsInput = ref(props.query.clientTags.join(', '))
watch(
  () => props.query.clientTags,
  (next) => {
    tagsInput.value = next.join(', ')
  },
  { deep: true },
)

const applyTagsDebounced = useDebounceFn((value: string) => {
  const parsed = Array.from(new Set(value.split(',').map(item => item.trim().toLowerCase()).filter(Boolean)))
  emitUpdate({ clientTags: parsed })
}, 400)

watch(tagsInput, (value) => {
  applyTagsDebounced(value)
})
</script>
