<template>
  <div class="space-y-4 min-w-0">
    <div class="flex flex-wrap items-end gap-2">
      <div class="grid gap-1.5">
        <label class="text-sm font-medium text-slate-900">Session ID</label>
        <Input v-model="sessionId" placeholder="session_123" class="w-full sm:w-[280px]" />
      </div>
      <Button :disabled="loading || !sessionId.trim()" @click="$emit('load', sessionId)">Загрузить теги</Button>
    </div>

    <div class="overflow-x-auto rounded-md border border-slate-200">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Тег</TableHead>
            <TableHead>Источник</TableHead>
            <TableHead>Уверенность</TableHead>
            <TableHead>Дата/время</TableHead>
            <TableHead>Метаданные</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow v-for="(tag, index) in tags" :key="`${tag.tag}-${index}`">
            <TableCell class="font-medium">{{ tag.tag }}</TableCell>
            <TableCell>{{ tag.source }}</TableCell>
            <TableCell>{{ tag.confidence ?? '—' }}</TableCell>
            <TableCell>{{ formatDate(tag.created_at) }}</TableCell>
            <TableCell>
              <details>
                <summary class="cursor-pointer text-indigo-600">Показать</summary>
                <pre class="mt-2 overflow-auto rounded bg-slate-950 p-3 text-xs text-slate-100">{{ JSON.stringify(tag.metadata || {}, null, 2) }}</pre>
              </details>
            </TableCell>
          </TableRow>
          <TableRow v-if="tags.length === 0">
            <TableCell colspan="5" class="text-center text-sm text-slate-500">Тегов пока нет</TableCell>
          </TableRow>
        </TableBody>
      </Table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Button } from '~/components/ui/button'
import { Input } from '~/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '~/components/ui/table'
import type { DialogTag } from '~/types/dialogTags'

defineProps<{
  loading: boolean
  tags: DialogTag[]
}>()

defineEmits<{
  load: [sessionId: string]
}>()

const sessionId = ref('')

const formatDate = (value?: string) => {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString()
}
</script>
