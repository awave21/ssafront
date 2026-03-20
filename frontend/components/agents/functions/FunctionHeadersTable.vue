<template>
  <div>
    <div class="text-sm text-slate-500 mb-4">
      Добавьте пользовательские HTTP заголовки к запросу (например, Authorization, X-API-Key, Content-Type).
    </div>
    
    <div v-if="headers.length > 0" class="rounded-md overflow-hidden mb-3">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead class="w-[35%]">Название</TableHead>
            <TableHead>Значение</TableHead>
            <TableHead class="w-[36px]"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow 
            v-for="(header, index) in headers"
            :key="index"
          >
            <TableCell>
              <Input
                :model-value="header.key"
                @update:model-value="$emit('update-header', index, 'key', $event)"
                placeholder="Authorization"
                class="h-8 text-[13px]"
              />
            </TableCell>
            <TableCell>
              <Input
                :model-value="header.value"
                @update:model-value="$emit('update-header', index, 'value', $event)"
                placeholder="Bearer {{token}}"
                class="h-8 text-[13px] font-mono"
              />
            </TableCell>
            <TableCell class="text-center">
              <Button
                variant="ghost"
                size="icon"
                @click="$emit('remove-header', index)"
                class="h-7 w-7 text-slate-400 hover:text-red-500"
              >
                <X class="w-3.5 h-3.5" />
              </Button>
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>
    
    <Button
      variant="ghost"
      @click="$emit('add-header')"
      class="text-[13px] text-indigo-600 hover:text-indigo-700"
    >
      <Plus class="w-3.5 h-3.5 mr-1.5" />
      Добавить заголовок
    </Button>
  </div>
</template>

<script setup lang="ts">
import { Plus, X } from 'lucide-vue-next'
import { Button } from '~/components/ui/button'
import { Input } from '~/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '~/components/ui/table'

type Header = {
  key: string
  value: string
}

defineProps<{
  headers: Header[]
}>()

defineEmits<{
  'add-header': []
  'remove-header': [index: number]
  'update-header': [index: number, field: 'key' | 'value', value: string]
}>()
</script>
