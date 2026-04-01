<template>
  <div
    class="group relative cursor-pointer overflow-hidden rounded-3xl border border-slate-100 bg-white p-5 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-all duration-500 hover:-translate-y-1 hover:shadow-[0_20px_40px_-12px_rgba(0,0,0,0.08)]"
    @click="$emit('click')"
  >
    <div
      class="pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full bg-indigo-500/5 transition-transform duration-700 group-hover:scale-150"
    />
    <div class="flex items-center justify-between gap-4">
      <div class="flex items-center gap-4 min-w-0">
        <div class="h-11 w-11 flex-shrink-0 rounded-xl bg-indigo-50 flex items-center justify-center transition-colors group-hover:bg-indigo-100">
          <component :is="templateIcon" class="w-5 h-5 text-indigo-600" />
        </div>
        <div class="min-w-0">
          <h4 class="font-bold text-slate-900 truncate">{{ directory.name }}</h4>
          <p class="text-xs text-slate-500 mt-0.5">
            <span class="font-mono text-slate-400">{{ directory.tool_name }}</span>
            <span class="mx-1.5">•</span>
            <span>{{ directory.items_count }} {{ itemsLabel }}</span>
          </p>
        </div>
      </div>

      <div class="flex items-center gap-3" @click.stop>
        <button
          @click="$emit('settings')"
          class="rounded-xl p-2 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-600"
          title="Настройки"
        >
          <Settings class="w-4 h-4" />
        </button>
        <button
          type="button"
          @click="$emit('delete')"
          class="rounded-xl p-2 text-slate-400 transition-colors hover:bg-red-50 hover:text-red-600"
          title="Удалить справочник"
        >
          <Trash2 class="w-4 h-4" />
        </button>
        <Switch
          :model-value="directory.is_enabled"
          @update:model-value="(val: boolean) => $emit('toggle', val)"
          :title="directory.is_enabled ? 'Выключить' : 'Включить'"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { 
  HelpCircle, 
  Tag, 
  Package, 
  Building2, 
  List,
  Settings,
  Trash2
} from 'lucide-vue-next'
import type { Directory } from '~/types/directories'
import { Switch } from '~/components/ui/switch'
import { pluralize } from '~/utils/pluralize'

const props = defineProps<{
  directory: Directory
}>()

const emit = defineEmits<{
  (e: 'click'): void
  (e: 'toggle', enabled: boolean): void
  (e: 'settings'): void
  (e: 'delete'): void
}>()

const templateIcon = computed(() => {
  const icons: Record<string, any> = {
    qa: HelpCircle,
    service_catalog: Tag,
    product_catalog: Package,
    company_info: Building2,
    custom: List
  }
  return icons[props.directory.template] || List
})

const itemsLabel = computed(() =>
  pluralize(props.directory.items_count, ['запись', 'записи', 'записей'])
)

</script>
