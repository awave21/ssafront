<template>
  <div>
    <div class="text-sm text-slate-500 mb-4">
      Создайте переменные и используйте их в URL, заголовках и параметрах через <code class="px-1.5 py-0.5 bg-amber-50 text-amber-700 rounded text-xs font-mono border border-amber-200" v-text="'{{name}}'"></code>
    </div>
    
    <div v-if="variables.length > 0" class="rounded-md overflow-hidden mb-3">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead class="w-[25%]">Имя</TableHead>
            <TableHead class="w-[35%]">Значение</TableHead>
            <TableHead>Описание</TableHead>
            <TableHead class="w-[70px]"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow 
            v-for="(variable, index) in variables"
            :key="index"
            class="group"
          >
            <TableCell>
              <Input
                :model-value="variable.name"
                @update:model-value="$emit('update-variable', index, 'name', $event)"
                placeholder="patient_id"
                class="h-8 text-[13px] font-mono text-amber-700 font-medium"
              />
            </TableCell>
            <TableCell>
              <Input
                :model-value="variable.value"
                @update:model-value="$emit('update-variable', index, 'value', $event)"
                placeholder="значение или {{from_context}}"
                class="h-8 text-[13px] font-mono"
              />
            </TableCell>
            <TableCell>
              <Input
                :model-value="variable.description"
                @update:model-value="$emit('update-variable', index, 'description', $event)"
                placeholder="Описание для AI"
                class="h-8 text-[13px] text-slate-500"
              />
            </TableCell>
            <TableCell class="text-center">
              <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <Button
                  variant="ghost"
                  size="icon"
                  @click="$emit('copy-variable', variable.name)"
                  title="Копировать {{name}}"
                  class="h-7 w-7 text-slate-400 hover:text-indigo-600"
                >
                  <Copy class="w-3.5 h-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  @click="$emit('remove-variable', index)"
                  class="h-7 w-7 text-slate-400 hover:text-red-500"
                >
                  <X class="w-3.5 h-3.5" />
                </Button>
              </div>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>
    
    <Button
      variant="ghost"
      @click="$emit('add-variable')"
      class="text-[13px] text-indigo-600 hover:text-indigo-700"
    >
      <Plus class="w-3.5 h-3.5 mr-1.5" />
      Добавить переменную
    </Button>
  </div>
</template>

<script setup lang="ts">
import { Plus, X, Copy } from 'lucide-vue-next'
import { Button } from '~/components/ui/button'
import { Input } from '~/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '~/components/ui/table'

type Variable = {
  name: string
  value: string
  description: string
}

defineProps<{
  variables: Variable[]
}>()

defineEmits<{
  'add-variable': []
  'remove-variable': [index: number]
  'update-variable': [index: number, field: 'name' | 'value' | 'description', value: string]
  'copy-variable': [name: string]
}>()
</script>
