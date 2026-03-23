<template>
  <div class="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
    <!-- Заголовок секции -->
    <div class="flex items-center gap-2 border-b border-border/60 bg-muted/30 px-4 py-2.5">
      <component :is="section.icon" class="h-3.5 w-3.5 text-primary/60" />
      <span class="text-[11px] font-bold uppercase tracking-widest text-foreground">
        {{ section.label }}
      </span>
      <Badge variant="secondary" class="ml-auto h-4 rounded-full px-1.5 text-[9px] font-bold">
        {{ section.items.length }}
      </Badge>
    </div>

    <!-- Список рекомендаций -->
    <div class="divide-y divide-border/40">
      <div
        v-for="rec in section.items"
        :key="rec.id"
        class="flex gap-3 p-3 transition-colors hover:bg-muted/20"
        :class="rec.status === 'rejected' ? 'opacity-50' : ''"
      >
        <!-- Контент рекомендации -->
        <div class="min-w-0 flex-1 space-y-1">
          <div class="flex items-start justify-between gap-2">
            <p class="text-xs font-semibold leading-snug text-foreground">{{ rec.title }}</p>
            <Badge
              v-if="rec.status === 'accepted'"
              variant="outline"
              class="h-4 shrink-0 border-emerald-200 bg-emerald-50 px-1 text-[9px] text-emerald-700"
            >
              Принято
            </Badge>
            <Badge
              v-else-if="rec.status === 'rejected'"
              variant="outline"
              class="h-4 shrink-0 border-slate-200 bg-slate-50 px-1 text-[9px] text-slate-500"
            >
              Отклонено
            </Badge>
          </div>
          <p
            v-if="rec.suggestion"
            class="line-clamp-3 text-[11px] italic text-muted-foreground"
          >
            {{ rec.suggestion }}
          </p>
          <p
            v-if="rec.reasoning && !rec.suggestion"
            class="line-clamp-2 text-[10px] text-muted-foreground/70"
          >
            {{ rec.reasoning }}
          </p>
          <div
            v-if="(rec.evidence_dialog_ids || []).length"
            class="flex flex-wrap gap-1 pt-0.5"
          >
            <span
              v-for="dialogId in (rec.evidence_dialog_ids || []).slice(0, 3)"
              :key="dialogId"
              class="rounded border border-border/50 bg-muted px-1 py-0.5 font-mono text-[8px] text-muted-foreground"
            >
              #{{ dialogId.split('-')[0] }}
            </span>
            <span
              v-if="(rec.evidence_dialog_ids || []).length > 3"
              class="self-center text-[8px] text-muted-foreground"
            >
              +{{ rec.evidence_dialog_ids!.length - 3 }}
            </span>
          </div>
        </div>

        <!-- Кнопки принять / отклонить -->
        <div class="flex shrink-0 flex-col gap-1">
          <Button
            v-if="rec.status !== 'accepted'"
            variant="ghost"
            size="icon-sm"
            class="h-6 w-6 hover:bg-emerald-50 hover:text-emerald-600"
            :disabled="Boolean(reviewBusyById[rec.id])"
            title="Принять"
            @click="emit('review', rec.id, 'accepted')"
          >
            <Check class="h-3 w-3" />
          </Button>
          <Button
            v-if="rec.status !== 'rejected'"
            variant="ghost"
            size="icon-sm"
            class="h-6 w-6 hover:bg-red-50 hover:text-red-500"
            :disabled="Boolean(reviewBusyById[rec.id])"
            title="Отклонить"
            @click="emit('review', rec.id, 'rejected')"
          >
            <X class="h-3 w-3" />
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Check, X } from 'lucide-vue-next'
import Badge from '~/components/ui/badge/Badge.vue'
import Button from '~/components/ui/button/Button.vue'
import type { AnalysisReviewStatus } from '~/types/agent-analysis'
import type { PromptSection } from './constants'

defineProps<{
  section: PromptSection
  reviewBusyById: Record<string, boolean>
}>()

const emit = defineEmits<{
  review: [id: string, decision: Exclude<AnalysisReviewStatus, 'pending'>]
}>()
</script>
