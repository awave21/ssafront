<template>
  <div class="rounded-md border border-slate-200 p-4">
    <div class="mb-3 flex items-center justify-between">
      <h3 class="text-sm font-semibold text-slate-900">Параметры функции</h3>
      <div class="flex items-center gap-2">
        <Button variant="outline" size="sm" :disabled="loading || previewLoading" @click="$emit('preview')">
          Предпросмотр schema
        </Button>
        <Button size="sm" :disabled="loading || saving" @click="$emit('save')">
          Сохранить параметры
        </Button>
      </div>
    </div>

    <div class="overflow-x-auto rounded-md border border-slate-200">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead class="min-w-[160px]">Имя параметра</TableHead>
            <TableHead class="min-w-[120px]">Тип</TableHead>
            <TableHead class="min-w-[220px]">Инструкция</TableHead>
            <TableHead class="w-[120px]">Необяз.</TableHead>
            <TableHead class="min-w-[140px]">По умолчанию</TableHead>
            <TableHead class="min-w-[160px]">Список значений</TableHead>
            <TableHead class="w-[110px]">x_from_ai</TableHead>
            <TableHead class="w-[130px]">Порядок</TableHead>
            <TableHead class="w-[90px]"></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-for="(parameter, index) in parameters" :key="`${parameter.name}_${index}`">
            <TableCell>
              <Input
                :model-value="parameter.name"
                placeholder="snake_case"
                @update:model-value="$emit('update-parameter', index, 'name', $event)"
              />
            </TableCell>
            <TableCell>
              <Select :model-value="parameter.type" @update:model-value="$emit('update-parameter', index, 'type', $event)">
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="text">Текстовый</SelectItem>
                  <SelectItem value="number">Числовой</SelectItem>
                  <SelectItem value="boolean">Логический</SelectItem>
                </SelectContent>
              </Select>
            </TableCell>
            <TableCell>
              <Input
                :model-value="parameter.instruction"
                placeholder="Инструкция для параметра"
                @update:model-value="$emit('update-parameter', index, 'instruction', $event)"
              />
            </TableCell>
            <TableCell>
              <Switch
                :model-value="parameter.optional"
                @update:model-value="$emit('update-parameter', index, 'optional', !!$event)"
              />
            </TableCell>
            <TableCell>
              <Input
                :model-value="parameter.default_value == null ? '' : String(parameter.default_value)"
                placeholder="опционально"
                @update:model-value="$emit('update-parameter', index, 'default_value', $event)"
              />
            </TableCell>
            <TableCell>
              <Input
                :model-value="(parameter.enum_values || []).join(', ')"
                placeholder="v1, v2"
                @update:model-value="$emit('update-enum-values', index, $event)"
              />
            </TableCell>
            <TableCell>
              <Switch
                :model-value="parameter.x_from_ai"
                @update:model-value="$emit('update-parameter', index, 'x_from_ai', !!$event)"
              />
            </TableCell>
            <TableCell>
              <div class="flex items-center gap-1">
                <Button size="sm" variant="outline" @click="$emit('move-up', index)">↑</Button>
                <Button size="sm" variant="outline" @click="$emit('move-down', index)">↓</Button>
              </div>
            </TableCell>
            <TableCell>
              <Button size="sm" variant="destructive" @click="$emit('remove', index)">Удалить</Button>
            </TableCell>
          </TableRow>
          <TableRow v-if="parameters.length === 0">
            <TableCell colspan="9" class="text-center text-sm text-slate-500">Параметры не добавлены</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>

    <div class="mt-3 flex items-center justify-between">
      <Button variant="outline" size="sm" @click="$emit('add')">Добавить параметр</Button>
      <span class="text-xs text-slate-500">Порядок можно менять кнопками вверх/вниз</span>
    </div>

    <div v-if="previewSchema" class="mt-3 rounded-md border border-slate-200 bg-slate-950 p-3">
      <div class="mb-2 text-xs font-semibold uppercase text-slate-300">JSON schema preview</div>
      <pre class="overflow-auto text-xs text-slate-100">{{ JSON.stringify(previewSchema, null, 2) }}</pre>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Button } from '~/components/ui/button'
import { Input } from '~/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '~/components/ui/select'
import { Switch } from '~/components/ui/switch'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '~/components/ui/table'
import type { ToolParameter } from '~/types/toolParameter'

defineProps<{
  parameters: ToolParameter[]
  loading: boolean
  saving: boolean
  previewLoading: boolean
  previewSchema: Record<string, any> | null
}>()

defineEmits<{
  add: []
  remove: [index: number]
  'move-up': [index: number]
  'move-down': [index: number]
  save: []
  preview: []
  'update-parameter': [index: number, field: keyof ToolParameter, value: any]
  'update-enum-values': [index: number, value: string]
}>()
</script>
