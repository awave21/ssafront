<template>
  <Loader2
    v-if="status === 'sending'"
    class="w-3 h-3 text-slate-400 animate-spin"
  />

  <Check
    v-else-if="status === 'sent'"
    class="w-3 h-3 text-slate-400"
  />

  <CheckCheck
    v-else-if="status === 'delivered'"
    class="w-3 h-3 text-slate-400"
  />

  <CheckCheck
    v-else-if="status === 'read'"
    class="w-3 h-3 text-indigo-500"
  />

  <div
    v-else-if="status === 'failed'"
    class="flex items-center gap-1"
  >
    <AlertCircle class="w-3 h-3 text-red-500" />
    <button
      @click="$emit('retry')"
      class="text-[10px] text-red-500 hover:text-red-600 font-medium"
    >
      Повторить
    </button>
  </div>
</template>

<script setup lang="ts">
import { AlertCircle, Check, CheckCheck, Loader2 } from 'lucide-vue-next'
import type { MessageStatus } from '../../types/dialogs'

defineProps<{
  status: MessageStatus
}>()

defineEmits<{
  (e: 'retry'): void
}>()
</script>
