<template>
  <Dialog :open="open" @update:open="$emit('update:open', $event)">
    <DialogContent class="max-w-2xl">
      <DialogHeader>
        <DialogTitle class="flex items-center gap-2">
          <Terminal class="w-5 h-5 text-indigo-600" />
          Импорт из cURL
        </DialogTitle>
        <DialogDescription>
          Вставьте cURL команду, и мы автоматически заполним URL, метод, заголовки и тело запроса.
        </DialogDescription>
      </DialogHeader>

      <div class="space-y-4 py-2">
        <Textarea
          :model-value="curlInput"
          @update:model-value="$emit('update:curlInput', $event)"
          placeholder="curl -X POST https://api.example.com/endpoint \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer token' \
  -d '{&quot;key&quot;: &quot;value&quot;}'"
          class="h-[200px] font-mono text-[13px] bg-slate-50 resize-none"
          @keydown.meta.enter="$emit('import')"
          @keydown.ctrl.enter="$emit('import')"
        />

        <Alert v-if="error" variant="destructive">
          <X class="h-4 w-4" />
          <AlertTitle>Ошибка</AlertTitle>
          <AlertDescription>{{ error }}</AlertDescription>
        </Alert>
      </div>

      <DialogFooter>
        <Button
          variant="outline"
          @click="$emit('update:open', false)"
        >
          Отмена
        </Button>
        <Button
          @click="$emit('import')"
          :disabled="!curlInput.trim()"
        >
          <Terminal class="w-4 h-4 mr-2" />
          Импортировать
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { Terminal, X } from 'lucide-vue-next'
import { Button } from '~/components/ui/button'
import { Textarea } from '~/components/ui/textarea'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '~/components/ui/dialog'
import { Alert, AlertDescription, AlertTitle } from '~/components/ui/alert'

defineProps<{
  open: boolean
  curlInput: string
  error: string
}>()

defineEmits<{
  'update:open': [value: boolean]
  'update:curlInput': [value: string]
  'import': []
}>()
</script>
