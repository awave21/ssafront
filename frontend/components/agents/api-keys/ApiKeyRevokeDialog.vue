<template>
  <Dialog :open="open" @update:open="$emit('update:open', $event)">
    <DialogContent class="sm:max-w-sm">
      <DialogHeader>
        <DialogTitle class="text-red-600">Отозвать API-ключ</DialogTitle>
        <DialogDescription>
          Ключ перестанет работать немедленно. Это действие необратимо.
        </DialogDescription>
      </DialogHeader>

      <div v-if="apiKey" class="py-2 text-sm text-slate-600">
        <p>
          Вы собираетесь отозвать ключ
          <span class="font-mono font-medium text-slate-800">sk-&#8226;&#8226;&#8226;&#8226;{{ apiKey.last4 }}</span>
          <template v-if="apiKey.name"> &laquo;{{ apiKey.name }}&raquo;</template>.
        </p>
      </div>

      <DialogFooter class="gap-2 sm:gap-0">
        <Button type="button" variant="outline" @click="$emit('update:open', false)">
          Отмена
        </Button>
        <Button
          variant="destructive"
          :disabled="isSubmitting"
          @click="$emit('confirm')"
        >
          <Loader2 v-if="isSubmitting" class="h-4 w-4 animate-spin" />
          {{ isSubmitting ? 'Отзыв...' : 'Отозвать ключ' }}
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { Loader2 } from 'lucide-vue-next'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '~/components/ui/dialog'
import { Button } from '~/components/ui/button'
import type { ApiKey } from '~/types/apiKey'

defineProps<{
  open: boolean
  apiKey: ApiKey | null
  isSubmitting?: boolean
}>()

defineEmits<{
  'update:open': [value: boolean]
  'confirm': []
}>()
</script>
