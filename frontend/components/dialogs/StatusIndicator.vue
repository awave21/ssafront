<template>
  <span
    class="inline-flex items-center justify-center flex-shrink-0"
    :class="containerClass"
  >
    <!-- IN_PROGRESS: Spinner -->
    <Loader2 v-if="status === 'IN_PROGRESS'" class="w-3.5 h-3.5 animate-spin text-indigo-600" />
    
    <!-- ERROR: Alert icon -->
    <AlertCircle v-else-if="status === 'ERROR'" class="w-3.5 h-3.5 text-red-500" />
    
    <!-- UNREAD: Badge with count -->
    <span
      v-else-if="status === 'UNREAD'"
      class="min-w-[18px] h-[18px] px-1 bg-indigo-600 text-white text-[10px] font-bold rounded-full flex items-center justify-center"
    >
      {{ displayCount }}
    </span>
    
    <!-- NEW: Badge -->
    <span
      v-else-if="status === 'NEW'"
      class="px-1.5 py-0.5 bg-green-100 text-green-700 text-[10px] font-semibold rounded-full uppercase tracking-wide"
    >
      Новый
    </span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Loader2, AlertCircle } from 'lucide-vue-next'
import type { DialogStatus } from '../../types/dialogs'

const props = defineProps<{
  status: DialogStatus
  count?: number
}>()

const containerClass = computed(() => {
  switch (props.status) {
    case 'IN_PROGRESS':
    case 'ERROR':
      return ''
    case 'UNREAD':
    case 'NEW':
      return ''
    default:
      return ''
  }
})

const displayCount = computed(() => {
  if (!props.count) return '0'
  return props.count > 99 ? '99+' : String(props.count)
})
</script>
