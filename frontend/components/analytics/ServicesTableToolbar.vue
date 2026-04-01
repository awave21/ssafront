<template>
  <div class="bg-white rounded-3xl border border-slate-100 p-6 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
    <div class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <div class="w-full lg:max-w-md">
        <label class="mb-2 block text-[10px] font-black uppercase tracking-widest text-slate-400">Сотрудник</label>
        <Select
          :model-value="resourceExternalId === null ? '__all__' : String(resourceExternalId)"
          @update:model-value="onResourceChange"
        >
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

      <div class="flex gap-2 shrink-0">
        <Button
          variant="secondary"
          size="icon"
          class="h-11 w-11 rounded-xl bg-slate-50 border-slate-100 hover:bg-slate-100 transition-all"
          :disabled="loading"
          title="CSV (страница)"
          @click="emit('export-current')"
        >
          <FileText class="h-4 w-4 text-slate-500" />
        </Button>
        <Button
          variant="secondary"
          size="icon"
          class="h-11 w-11 rounded-xl bg-slate-50 border-slate-100 hover:bg-slate-100 transition-all"
          :disabled="loading"
          title="CSV (все)"
          @click="emit('export-all')"
        >
          <Download class="h-4 w-4 text-slate-500" />
        </Button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { FileText, Download } from 'lucide-vue-next'
import Button from '~/components/ui/button/Button.vue'
import Select from '~/components/ui/select/Select.vue'
import SelectContent from '~/components/ui/select/SelectContent.vue'
import SelectItem from '~/components/ui/select/SelectItem.vue'
import SelectTrigger from '~/components/ui/select/SelectTrigger.vue'
import SelectValue from '~/components/ui/select/SelectValue.vue'
import type { AnalyticsResourceOption } from '~/types/analytics'

const props = defineProps<{
  resourceExternalId: number | string | null
  resources: AnalyticsResourceOption[]
  loading: boolean
}>()

const emit = defineEmits<{
  (e: 'update-resource', patch: { resourceExternalId: number | string | null }): void
  (e: 'export-current'): void
  (e: 'export-all'): void
}>()

const onResourceChange = (value: string | number) => {
  const normalized = String(value)
  const numeric = Number(normalized)
  emit('update-resource', {
    resourceExternalId: normalized === '__all__'
      ? null
      : Number.isFinite(numeric)
        ? numeric
        : normalized,
  })
}
</script>
