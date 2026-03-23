<template>
  <div class="space-y-4">

    <!-- Сводка анализа -->
    <div v-if="summary" class="rounded-xl border border-border bg-card p-4 shadow-sm">
      <div class="flex items-start gap-3">
        <Quote class="mt-0.5 h-4 w-4 shrink-0 text-primary/40" />
        <p class="text-sm italic leading-relaxed text-foreground/80">{{ summary }}</p>
      </div>
    </div>

    <!-- Скелетон загрузки -->
    <div v-if="isLoading" class="space-y-3">
      <div
        v-for="i in 4"
        :key="i"
        class="space-y-2 rounded-xl border border-border bg-card p-4 shadow-sm"
      >
        <Skeleton class="h-4 w-24" />
        <Skeleton class="h-16 w-full" />
      </div>
    </div>

    <!-- Секции рекомендаций -->
    <template v-else-if="hasRecommendations">
      <AnalysisPromptSection
        v-for="section in promptSections"
        v-show="section.items.length"
        :key="section.key"
        :section="section"
        :review-busy-by-id="reviewBusyById"
        @review="(id, decision) => emit('review', id, decision)"
      />

      <!-- Пагинация -->
      <div class="flex items-center justify-between pt-2">
        <p class="text-[10px] font-medium uppercase tracking-widest text-muted-foreground/60">
          {{ paginationLabel }}
        </p>
        <div class="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            class="h-7 w-7 p-0"
            :disabled="!canPrevPage || isLoading"
            @click="emit('prev-page')"
          >
            <ChevronLeft class="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            class="h-7 w-7 p-0"
            :disabled="!canNextPage || isLoading"
            @click="emit('next-page')"
          >
            <ChevronRight class="h-4 w-4" />
          </Button>
        </div>
      </div>
    </template>

    <!-- Пустое состояние -->
    <div v-else class="py-16 text-center">
      <Sparkles class="mx-auto mb-2 h-8 w-8 text-muted-foreground/20" />
      <p class="text-xs text-muted-foreground">Рекомендации появятся после завершения анализа</p>
    </div>

  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ChevronLeft, ChevronRight, Quote, Sparkles } from 'lucide-vue-next'
import Button from '~/components/ui/button/Button.vue'
import Skeleton from '~/components/ui/skeleton/Skeleton.vue'
import type { AnalysisReviewStatus } from '~/types/agent-analysis'
import type { PromptSection } from './constants'
import AnalysisPromptSection from './AnalysisPromptSection.vue'

const props = defineProps<{
  summary: string | null | undefined
  promptSections: PromptSection[]
  isLoading: boolean
  paginationLabel: string
  canPrevPage: boolean
  canNextPage: boolean
  reviewBusyById: Record<string, boolean>
}>()

const emit = defineEmits<{
  review: [id: string, decision: Exclude<AnalysisReviewStatus, 'pending'>]
  'prev-page': []
  'next-page': []
}>()

const hasRecommendations = computed(() =>
  props.promptSections.some((s) => s.items.length > 0)
)
</script>
