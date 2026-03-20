<template>
  <div>
    <!-- Mode Toggle -->
    <div class="flex items-center justify-between mb-3">
      <label class="block text-xs font-medium text-slate-900">Параметры запроса</label>
      <div class="inline-flex bg-slate-100 rounded-md p-0.5">
        <Button
          variant="ghost"
          size="sm"
          :class="viewMode === 'fields' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500'"
          @click="$emit('update:viewMode', 'fields')"
          class="px-3 py-1 text-xs h-7"
        >
          Fields
        </Button>
        <Button
          variant="ghost"
          size="sm"
          :class="viewMode === 'json' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500'"
          @click="$emit('update:viewMode', 'json')"
          class="px-3 py-1 text-xs h-7"
        >
          JSON
        </Button>
      </div>
    </div>

    <!-- Fields View -->
    <div v-if="viewMode === 'fields'">
      <div class="rounded-md overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead class="w-[25%]">Ключ</TableHead>
              <TableHead class="w-[15%]">Расположение</TableHead>
              <TableHead class="w-[15%]">Тип</TableHead>
              <TableHead>Переменная</TableHead>
              <TableHead class="w-[36px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            <TableRow 
              v-for="(param, index) in parameters"
              :key="param.id"
            >
              <TableCell>
                <Input
                  :model-value="param.key"
                  @update:model-value="$emit('update-parameter', index, 'key', $event)"
                  placeholder="parameter_name"
                  class="h-8 text-[13px]"
                />
              </TableCell>
              <TableCell>
                <Select
                  :model-value="param.location"
                  @update:model-value="$emit('update-parameter', index, 'location', $event)"
                >
                  <SelectTrigger class="h-8 text-xs font-semibold">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="body">Body</SelectItem>
                    <SelectItem value="path">Path</SelectItem>
                    <SelectItem value="query">Query</SelectItem>
                  </SelectContent>
                </Select>
              </TableCell>
              <TableCell>
                <Select
                  :model-value="param.type"
                  @update:model-value="$emit('update-parameter', index, 'type', $event)"
                >
                  <SelectTrigger class="h-8 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="string">String</SelectItem>
                    <SelectItem value="number">Number</SelectItem>
                    <SelectItem value="boolean">Boolean</SelectItem>
                    <SelectItem value="array">Array</SelectItem>
                    <SelectItem value="object">Object</SelectItem>
                  </SelectContent>
                </Select>
              </TableCell>
              <TableCell>
                <div class="flex items-start gap-1.5">
                  <!-- Static value input -->
                  <div v-if="!param.fromAI" class="relative flex-1">
                    <Input
                      :model-value="param.value"
                      @update:model-value="$emit('update-parameter', index, 'value', $event)"
                      placeholder="значение или {{from_context}}"
                      class="h-8 text-[13px] font-mono pr-8 text-indigo-600"
                    />
                    
                    <!-- Variable Picker -->
                    <div v-if="variables.length > 0" class="absolute right-1 top-1/2 -translate-y-1/2">
                      <Popover>
                        <PopoverTrigger as-child>
                          <Button variant="ghost" size="icon" class="h-6 w-6 text-slate-400 hover:text-indigo-600">
                            <Braces class="w-3 h-3" />
                          </Button>
                        </PopoverTrigger>
                        <PopoverContent class="w-48 p-1" align="end">
                          <div class="text-[10px] font-semibold text-slate-500 px-2 py-1.5 border-b border-slate-100 mb-1">
                            Вставить переменную
                          </div>
                          <ScrollArea class="max-h-[200px]">
                            <Button
                              v-for="v in variables"
                              :key="v.name"
                              variant="ghost"
                              size="sm"
                              @click="$emit('update-parameter', index, 'value', `{{${v.name}}}`)"
                              class="w-full justify-between text-[11px] font-mono h-8"
                            >
                              <span>{{ v.name }}</span>
                              <span v-if="v.value" class="text-[9px] text-slate-400 max-w-[80px] truncate">{{ v.value }}</span>
                            </Button>
                          </ScrollArea>
                        </PopoverContent>
                      </Popover>
                    </div>
                  </div>

                  <!-- AI configuration -->
                  <div v-else class="flex-1 space-y-1.5">
                    <div class="text-[10px] font-medium text-violet-700">Описание для модели</div>
                    <Input
                      :model-value="param.aiDescription"
                      @update:model-value="$emit('update-parameter', index, 'aiDescription', $event)"
                      placeholder="Что модель должна передать в этот параметр (напр: Имя пользователя)"
                      class="h-8 text-[13px] text-violet-700 border-violet-200 bg-violet-50/50"
                    />
                    <div class="text-[10px] font-medium text-slate-500">Fallback-значение</div>
                    <Input
                      :model-value="param.aiDefaultValue"
                      @update:model-value="$emit('update-parameter', index, 'aiDefaultValue', $event)"
                      placeholder="Используется, если модель не передала значение"
                      class="h-7 text-[11px] font-mono text-slate-500"
                    />
                  </div>
                </div>
              </TableCell>
              <TableCell class="text-center">
                <Button
                  variant="ghost"
                  size="icon"
                  @click="$emit('remove-parameter', index)"
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
        @click="$emit('add-parameter')"
        class="mt-3 text-[13px] text-indigo-600 hover:text-indigo-700"
      >
        <Plus class="w-3.5 h-3.5 mr-1.5" />
        Добавить поле
      </Button>
    </div>

    <!-- JSON View -->
    <div v-else>
      <Textarea
        :model-value="jsonValue"
        @update:model-value="$emit('update:jsonValue', $event)"
        placeholder="{}"
        class="font-mono text-xs min-h-[300px]"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { Plus, X, Braces } from 'lucide-vue-next'
import { Button } from '~/components/ui/button'
import { Input } from '~/components/ui/input'
import { Textarea } from '~/components/ui/textarea'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '~/components/ui/table'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '~/components/ui/select'
import { Popover, PopoverContent, PopoverTrigger } from '~/components/ui/popover'
import { ScrollArea } from '~/components/ui/scroll-area'
import type { BodyParameter } from '~/utils/function-schema'

defineProps<{
  parameters: BodyParameter[]
  variables: Array<{ name: string; value: string; description: string }>
  viewMode: 'fields' | 'json'
  jsonValue: string
}>()

defineEmits<{
  'update:viewMode': [mode: 'fields' | 'json']
  'update:jsonValue': [value: string]
  'update-parameter': [index: number, field: keyof BodyParameter, value: any]
  'add-parameter': []
  'remove-parameter': [index: number]
}>()
</script>
