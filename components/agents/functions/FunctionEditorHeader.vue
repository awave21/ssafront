<template>
  <div class="px-6 py-4 border-b border-slate-200">
    <Input
      :model-value="displayName"
      @update:model-value="$emit('update:displayName', $event)"
      placeholder="Название функции (напр: Создать пациента, Get patients)"
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
    
    <Input
      :model-value="description"
      @update:model-value="$emit('update:description', $event)"
      placeholder="Краткое описание функции"
      class="mt-1.5 text-[13px] text-slate-500 border-none bg-transparent p-0 h-auto focus-visible:ring-0 focus-visible:ring-offset-0"
    />
  </div>
</template>

<script setup lang="ts">
import { Input } from '~/components/ui/input'
import { Badge } from '~/components/ui/badge'

defineProps<{
  displayName: string
  functionName: string
  functionId: string
  description: string
}>()

defineEmits<{
  'update:displayName': [value: string]
  'update:description': [value: string]
}>()
</script>
