<template>
  <div class="h-full min-w-0 rounded-md border border-slate-200 bg-slate-50">
    <div class="border-b border-slate-200 p-4">
      <div class="mb-3 flex items-center justify-between">
        <span class="text-sm font-semibold text-slate-900">Функции</span>
        <div class="flex items-center gap-1">
          <Button
            v-if="canEdit"
            variant="ghost"
            size="icon"
            class="h-8 w-8 text-slate-500 hover:text-slate-700"
            title="Отключить все правила"
            @click="$emit('kill-switch')"
          >
            <Power class="h-4 w-4" />
          </Button>
          <Button
            v-if="canEdit"
            variant="ghost"
            size="icon"
            class="h-8 w-8 text-indigo-600"
            @click="$emit('create')"
          >
            <Plus class="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div class="relative mb-2">
        <Search class="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" />
        <Input
          v-model="searchQuery"
          placeholder="Filter..."
          class="h-9 pl-8 text-xs"
        />
      </div>

      <div class="grid gap-2 sm:grid-cols-2">
        <Select :model-value="conditionTypeFilter" @update:model-value="$emit('update:conditionTypeFilter', $event as string)">
          <SelectTrigger class="h-8 text-xs">
            <SelectValue placeholder="Тип условия" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Все</SelectItem>
            <SelectItem value="keywords">Ключевые слова</SelectItem>
            <SelectItem value="regex">Регулярное выражение</SelectItem>
            <SelectItem value="semantic">По смыслу</SelectItem>
            <SelectItem value="always">Всегда</SelectItem>
          </SelectContent>
        </Select>

        <Select :model-value="enabledFilter" @update:model-value="$emit('update:enabledFilter', $event as string)">
          <SelectTrigger class="h-8 text-xs">
            <SelectValue placeholder="Статус" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Все</SelectItem>
            <SelectItem value="enabled">Только включенные</SelectItem>
            <SelectItem value="disabled">Только выключенные</SelectItem>
          </SelectContent>
        </Select>
      </div>
    </div>

    <ScrollArea class="max-h-[60vh]">
      <div class="space-y-0.5 p-2">
        <div
          v-for="rule in filteredRules"
          :key="rule.id"
          class="cursor-pointer rounded-md border border-transparent p-2.5 transition-colors hover:bg-slate-100"
          @click="$emit('edit', rule.id)"
        >
          <div class="flex items-start gap-2.5">
            <Badge
              variant="secondary"
              class="min-w-[54px] text-center text-[9px] font-bold uppercase"
              :class="getConditionClass(rule.condition_type)"
            >
              {{ rule.condition_type }}
            </Badge>
            <div class="min-w-0 flex-1">
              <div class="truncate text-[13px] font-medium text-slate-900">{{ rule.name }}</div>
              <div class="truncate font-mono text-[11px] text-slate-500">
                priority={{ rule.priority }} • {{ formatDate(rule.updated_at) }}
              </div>
            </div>
            <div class="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full" :class="rule.enabled ? 'bg-emerald-500' : 'bg-slate-300'" />
          </div>
          <div class="mt-2 flex flex-wrap items-center gap-1.5" @click.stop>
            <Switch
              :model-value="rule.enabled"
              :disabled="!canEdit"
              @update:model-value="$emit('toggle', rule.id, !!$event)"
            />
            <Button :disabled="!canEdit" variant="outline" size="sm" class="h-7 px-2 text-[11px]" @click="$emit('edit', rule.id)">
              Ред.
            </Button>
            <Button v-if="canEdit" variant="destructive" size="sm" class="h-7 px-2 text-[11px]" @click="$emit('remove', rule.id)">
              Удалить
            </Button>
          </div>
        </div>
        <div v-if="filteredRules.length === 0" class="p-6 text-center text-sm text-slate-500">
          Сценарии не найдены
        </div>
      </div>
    </ScrollArea>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Plus, Power, Search } from 'lucide-vue-next'
import { Button } from '~/components/ui/button'
import { Input } from '~/components/ui/input'
import { Badge } from '~/components/ui/badge'
import { ScrollArea } from '~/components/ui/scroll-area'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '~/components/ui/select'
import { Switch } from '~/components/ui/switch'
import type { FunctionRule } from '~/types/functionRule'

const props = defineProps<{
  rules: FunctionRule[]
  conditionTypeFilter: string
  enabledFilter: string
  canEdit: boolean
}>()

defineEmits<{
  create: []
  'kill-switch': []
  edit: [id: string]
  remove: [id: string]
  toggle: [id: string, enabled: boolean]
  'update:conditionTypeFilter': [value: string]
  'update:enabledFilter': [value: string]
}>()

const formatDate = (value?: string) => {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString()
}

const searchQuery = ref('')

const filteredRules = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  if (!query) return props.rules
  return props.rules.filter(rule =>
    rule.name.toLowerCase().includes(query) ||
    rule.condition_type.toLowerCase().includes(query),
  )
})

const getConditionClass = (conditionType: string) => {
  switch (conditionType) {
    case 'semantic': return 'bg-indigo-100 text-indigo-700'
    case 'regex': return 'bg-slate-200 text-slate-700'
    case 'keywords': return 'bg-slate-100 text-slate-700'
    case 'always': return 'bg-slate-100 text-slate-700'
    default: return 'bg-slate-100 text-slate-700'
  }
}
</script>
