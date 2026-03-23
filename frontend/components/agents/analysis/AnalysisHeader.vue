<template>
  <div class="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 shadow-sm sm:flex-row sm:items-center sm:justify-between">
    <div class="flex items-center gap-3">
      <div>
        <h2 class="text-base font-bold text-foreground">Центр обучения</h2>
        <p class="text-xs text-muted-foreground">{{ subtitle }}</p>
      </div>
      <Badge
        v-if="currentJob"
        :class="getStatusClasses(currentJob.status)"
        variant="secondary"
        class="shrink-0 text-[10px] uppercase tracking-wider"
      >
        {{ formatStatus(currentJob.status) }}
      </Badge>
    </div>

    <div class="flex flex-wrap items-center gap-2">
      <Button variant="ghost" size="sm" :disabled="isRefreshing" @click="emit('refresh')">
        <RefreshCcw class="h-3.5 w-3.5" :class="isRefreshing ? 'animate-spin' : ''" />
      </Button>
      <Button
        v-if="canCancelCurrentJob"
        variant="outline"
        size="sm"
        :disabled="isCancelling"
        @click="emit('cancel')"
      >
        <Loader2 v-if="isCancelling" class="mr-1.5 h-3.5 w-3.5 animate-spin" />
        <StopCircle v-else class="mr-1.5 h-3.5 w-3.5" />
        Остановить
      </Button>
      <Button size="sm" :disabled="!canStartNewJob" @click="emit('open-dialog')">
        <Play class="mr-1.5 h-3.5 w-3.5" />
        Запустить анализ
      </Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Loader2, Play, RefreshCcw, StopCircle } from 'lucide-vue-next'
import Badge from '~/components/ui/badge/Badge.vue'
import Button from '~/components/ui/button/Button.vue'
import type { AnalysisJob } from '~/types/agent-analysis'
import { formatStatus, getStatusClasses } from './constants'

const props = defineProps<{
  currentJob: AnalysisJob | null
  subtitle: string
  canStartNewJob: boolean
  canCancelCurrentJob: boolean
  isCancelling: boolean
  isRefreshing: boolean
}>()

const emit = defineEmits<{
  'open-dialog': []
  cancel: []
  refresh: []
}>()
</script>
