<template>
  <div class="px-6 py-4 border-b border-slate-200">
    <Input
      :model-value="displayName"
      @update:model-value="$emit('update:displayName', $event)"
      placeholder="Название функции (наприем get_.../create...)"
      class="text-xl font-semibold border-none outline-none bg-transparent p-0 h-auto focus-visible:ring-0 focus-visible:ring-offset-0"
    />
    
    <div class="flex items-center gap-2 mt-0.5">
      <Badge variant="secondary" class="text-[11px] font-mono font-normal">
        {{ functionName || 'function_name' }}
      </Badge>
      <span class="text-[11px] font-mono text-slate-300">
        ID: {{ functionId }}
      </span>
    </div>
    
    <div v-if="!functionName && !displayName" class="text-[11px] text-slate-400 mt-1">
      Напр: get_patient_list, create_appointment, send_notification
    </div>
    
    <div v-if="functionType === 'http_webhook'" class="mt-3 grid gap-1.5 max-w-[320px]">
      <span class="text-xs font-medium text-slate-600">Режим webhook</span>
      <Select :model-value="functionScope" @update:model-value="$emit('update:functionScope', String($event))">
        <SelectTrigger class="h-8 text-xs">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="tool">Прямой вызов</SelectItem>
          <SelectItem value="function_only">Через функции</SelectItem>
        </SelectContent>
      </Select>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Input } from '~/components/ui/input'
import { Badge } from '~/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '~/components/ui/select'

defineProps<{
  displayName: string
  functionName: string
  functionId: string
  functionType: 'internal' | 'http_webhook'
  functionScope: 'tool' | 'function_only'
}>()

defineEmits<{
  'update:displayName': [value: string]
  'update:functionScope': [value: string]
}>()
</script>
