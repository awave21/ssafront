<template>
  <div class="space-y-3 min-w-0">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h4 class="text-sm font-semibold text-slate-900">Действия</h4>
      <Button v-if="canEdit" size="sm" @click="$emit('add')">Добавить действие</Button>
    </div>

    <div class="overflow-x-auto rounded-md border border-slate-200">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Тип</TableHead>
            <TableHead>Когда</TableHead>
            <TableHead>Вкл</TableHead>
            <TableHead>Порядок</TableHead>
            <TableHead class="w-[170px]">Управление</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-for="action in actions" :key="action.id">
            <TableCell>{{ action.action_type }}</TableCell>
            <TableCell>{{ action.on_status }}</TableCell>
            <TableCell>
              <Switch :model-value="action.enabled" disabled />
            </TableCell>
            <TableCell>{{ action.order_index }}</TableCell>
            <TableCell>
              <div class="flex flex-wrap items-center gap-1">
                <Button :disabled="!canEdit" variant="outline" size="sm" @click="$emit('move-up', action.id)">Вверх</Button>
                <Button :disabled="!canEdit" variant="outline" size="sm" @click="$emit('move-down', action.id)">Вниз</Button>
                <Button :disabled="!canEdit" variant="outline" size="sm" @click="$emit('edit', action.id)">Изм.</Button>
                <Button :disabled="!canEdit" variant="destructive" size="sm" @click="$emit('remove', action.id)">Удалить</Button>
              </div>
            </TableCell>
          </TableRow>
          <TableRow v-if="actions.length === 0">
            <TableCell colspan="5" class="text-center text-sm text-slate-500">
              Действия не добавлены
            </TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Button } from '~/components/ui/button'
import { Switch } from '~/components/ui/switch'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '~/components/ui/table'
import type { FunctionRuleAction } from '~/types/ruleAction'

defineProps<{
  actions: FunctionRuleAction[]
  canEdit: boolean
}>()

defineEmits<{
  add: []
  edit: [id: string]
  remove: [id: string]
  'move-up': [id: string]
  'move-down': [id: string]
}>()
</script>
