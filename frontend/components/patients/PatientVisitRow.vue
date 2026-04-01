<template>
  <div
    class="flex flex-col gap-2 border-b border-slate-100 px-4 py-4 transition-colors last:border-b-0 sm:flex-row sm:items-center sm:gap-4 sm:px-6"
    :class="rowHighlightClass(visit)"
  >
    <div class="w-full shrink-0 sm:w-[130px]">
      <div class="text-sm font-bold text-slate-900">{{ formatVisitDate(visit) }}</div>
      <div class="text-xs font-medium text-slate-400">{{ formatVisitTime(visit) }}</div>
    </div>
    <div class="min-w-0 flex-1">
      <div class="break-words text-sm font-bold text-slate-900">
        {{ visit.service_name || '—' }}
      </div>
      <div class="flex items-center gap-1.5 text-xs text-slate-500">
        <User class="h-3.5 w-3.5 shrink-0" />
        <span class="truncate">{{ visit.specialist_name || '—' }}</span>
      </div>
    </div>
    <div
      class="flex items-center justify-between gap-3 sm:w-[120px] sm:flex-col sm:items-end sm:justify-center sm:text-right"
    >
      <div class="text-sm font-bold text-slate-900">{{ visitPriceMain(visit) }}</div>
      <div class="text-xs text-slate-400">{{ visitPriceSub(visit) }}</div>
    </div>
    <div class="sm:flex sm:w-[110px] sm:justify-end">
      <Badge v-bind="visitStatusBadgeAttrs(visit)">
        <component :is="visitStatusIcon(visit)" class="h-3 w-3" />
        {{ visitStatusLabel(visit) }}
      </Badge>
    </div>
  </div>
</template>

<script setup lang="ts">
import { User } from 'lucide-vue-next'
import Badge from '~/components/ui/badge/Badge.vue'
import type { SqnsClientCachedVisitItem } from '~/types/patient-directory'
import {
  formatVisitDate,
  formatVisitTime,
  rowHighlightClass,
  visitPriceMain,
  visitPriceSub,
  visitStatusBadgeAttrs,
  visitStatusIcon,
  visitStatusLabel,
} from '~/utils/patientDetailFormat'

defineProps<{
  visit: SqnsClientCachedVisitItem
}>()
</script>
