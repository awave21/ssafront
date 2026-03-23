<template>
  <!-- Прогресс выполнения -->
  <div
    v-if="currentJob?.status === 'running'"
    class="flex items-center gap-3 rounded-xl border border-border bg-card px-4 py-3 shadow-sm"
  >
    <Activity class="h-4 w-4 shrink-0 animate-pulse text-primary" />
    <span class="min-w-0 flex-1 truncate text-xs font-medium text-foreground">
      {{ currentJob.stage || 'Анализ выполняется...' }}
    </span>
    <div class="flex shrink-0 items-center gap-2">
      <div class="h-1.5 w-28 overflow-hidden rounded-full bg-secondary">
        <div
          class="h-full bg-primary transition-all duration-500"
          :style="{ width: `${progress}%` }"
        />
      </div>
      <span class="font-mono text-[11px] text-muted-foreground">{{ progress }}%</span>
    </div>
  </div>

  <!-- В очереди -->
  <div
    v-else-if="currentJob?.status === 'queued'"
    class="flex items-center gap-2 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-700"
  >
    <Clock class="h-4 w-4 shrink-0" />
    <span>Анализ поставлен в очередь — скоро начнётся</span>
  </div>
</template>

<script setup lang="ts">
import { Activity, Clock } from 'lucide-vue-next'
import type { AnalysisJob } from '~/types/agent-analysis'

defineProps<{
  currentJob: AnalysisJob | null
  progress: number
}>()
</script>
