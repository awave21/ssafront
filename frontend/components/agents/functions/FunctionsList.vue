<template>
  <div class="w-[280px] border-r border-slate-200 flex flex-col bg-slate-50">
    <!-- Header -->
    <div class="p-4 border-b border-slate-200">
      <div class="flex justify-between items-center mb-3">
        <span class="font-semibold text-sm text-slate-900">{{ title }}</span>
        <div class="flex items-center gap-0.5">
          <Button
            v-if="showImport"
            variant="ghost"
            size="icon"
            class="h-8 w-8 text-slate-500 hover:text-indigo-600"
            @click="$emit('import-curl')"
            title="Импорт из cURL"
          >
            <Terminal class="w-4 h-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            class="h-8 w-8 text-indigo-600"
            @click="$emit('create')"
          >
            <Plus class="w-4 h-4" />
          </Button>
        </div>
      </div>
      
      <div class="relative">
        <Search class="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
        <Input
          v-model="searchQuery"
          placeholder="Filter..."
          class="pl-8 h-9 text-xs"
        />
      </div>
    </div>
    
    <!-- Function List -->
    <ScrollArea class="flex-1">
      <div class="p-2 space-y-0.5">
        <div 
          v-for="func in filteredFunctions" 
          :key="func.id"
          class="flex items-center gap-2.5 p-2.5 rounded-md cursor-pointer border border-transparent hover:bg-slate-100 transition-colors"
          :class="{ 'bg-slate-100 border-slate-200': selectedId === func.id }"
          @click="$emit('select', func)"
        >
          <Badge
            v-if="showMethod"
            variant="secondary"
            class="text-[9px] font-bold min-w-[38px] text-center uppercase"
            :class="getMethodClass(func.http_method)"
          >
            {{ func.http_method }}
          </Badge>
          <div class="flex-1 min-w-0" :class="!showMethod ? 'pl-0.5' : ''">
            <div class="text-[13px] font-medium text-slate-900 truncate flex items-center gap-1">
              {{ func.input_schema?._displayName || func.name || 'Новая функция' }}
              <span v-if="hasUnsavedChanges(func.id)" class="text-orange-500">●</span>
            </div>
            <div class="text-[11px] text-slate-500 truncate font-mono">{{ func.name || 'function_name' }}</div>
          </div>
          <div 
            class="w-1.5 h-1.5 rounded-full flex-shrink-0" 
            :class="func.status === 'active' ? 'bg-emerald-500' : 'bg-slate-300'"
          />
        </div>
      </div>
    </ScrollArea>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Plus, Search, Terminal } from 'lucide-vue-next'
import { Button } from '~/components/ui/button'
import { Input } from '~/components/ui/input'
import { Badge } from '~/components/ui/badge'
import { ScrollArea } from '~/components/ui/scroll-area'
import type { Tool } from '~/types/tool'

const props = defineProps<{
  functions: Tool[]
  selectedId?: string | null
  unsavedChanges: Set<string>
  title?: string
  showImport?: boolean
  showMethod?: boolean
}>()

defineEmits<{
  select: [func: Tool]
  create: []
  'import-curl': []
}>()

const searchQuery = ref('')

const filteredFunctions = computed(() => {
  if (!searchQuery.value) return props.functions
  
  const query = searchQuery.value.toLowerCase()
  return props.functions.filter(f => 
    (f.name || '').toLowerCase().includes(query) ||
    (f.input_schema?._displayName || '').toLowerCase().includes(query) ||
    (f.description || '').toLowerCase().includes(query)
  )
})

const hasUnsavedChanges = (id: string | undefined) => {
  return id ? props.unsavedChanges.has(id) : false
}

const title = computed(() => props.title || 'Функции')
const showImport = computed(() => props.showImport !== false)
const showMethod = computed(() => props.showMethod !== false)

const getMethodClass = (method: string) => {
  switch (method) {
    case 'GET': return 'text-emerald-600 bg-emerald-100'
    case 'POST': return 'text-blue-600 bg-blue-100'
    case 'PUT': return 'text-amber-600 bg-amber-100'
    case 'DELETE': return 'text-red-600 bg-red-100'
    case 'PATCH': return 'text-purple-600 bg-purple-100'
    default: return 'text-slate-600 bg-slate-100'
  }
}
</script>
