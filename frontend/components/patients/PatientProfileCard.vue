<template>
  <div
    class="group relative w-full min-w-0 max-w-full overflow-hidden rounded-3xl border border-slate-100 bg-white p-4 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-all duration-300 hover:-translate-y-0.5 hover:shadow-[0_12px_24px_-8px_rgba(0,0,0,0.08)] sm:p-6"
  >
    <div
      class="absolute -bottom-4 -right-4 h-16 w-16 rounded-full bg-slate-50 transition-all duration-500 group-hover:scale-150 group-hover:bg-primary/5"
    />
    <div class="relative z-10 flex flex-col gap-5">
      <div class="flex items-center gap-4">
        <div
          class="flex h-[72px] w-[72px] shrink-0 items-center justify-center rounded-[20px] bg-gradient-to-br from-primary/20 to-primary/40 text-xl font-black text-primary"
        >
          {{ initials }}
        </div>
        <div class="min-w-0 flex-1">
          <div class="break-words text-lg font-bold leading-tight text-slate-900">
            {{ displayName }}
          </div>
          <div class="text-xs font-medium text-slate-400">ID: {{ externalIdLabel }}</div>
        </div>
      </div>

      <div class="flex flex-wrap gap-2">
        <Badge v-for="(seg, i) in badges" :key="i" v-bind="segmentBadgeAttrs(seg.tone)">
          <Star v-if="seg.icon === 'star'" class="h-3 w-3" />
          {{ seg.label }}
        </Badge>
      </div>

      <div class="space-y-3 border-t border-slate-100 pt-4">
        <div v-for="row in contacts" :key="row.label" class="flex min-w-0 gap-3">
          <component :is="row.icon" class="mt-0.5 h-[18px] w-[18px] shrink-0 text-slate-400" />
          <div class="min-w-0 flex-1">
            <div class="text-[10px] font-black uppercase tracking-widest text-slate-400">
              {{ row.label }}
            </div>
            <div class="break-words text-sm font-medium text-slate-700">{{ row.value }}</div>
          </div>
        </div>
      </div>

      <div class="rounded-2xl border border-primary/15 bg-primary/[0.06] p-4 shadow-sm">
        <div class="mb-2 flex items-center gap-2 text-xs font-bold text-primary">
          <Sparkles class="h-4 w-4 shrink-0" />
          AI Сводка агента
        </div>
        <p class="break-words text-xs font-medium leading-relaxed text-slate-600">
          Краткая сводка появится, когда накопится история диалогов и визитов. Сейчас доступны данные
          интеграции SQNS и список приёмов.
        </p>
      </div>

      <Button
        variant="outline"
        type="button"
        class="h-10 w-full rounded-xl border-slate-100 text-xs font-bold"
        disabled
        title="Скоро"
      >
        <Pencil class="mr-2 h-4 w-4" />
        Редактировать профиль
      </Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Pencil, Sparkles, Star } from 'lucide-vue-next'
import Badge from '~/components/ui/badge/Badge.vue'
import Button from '~/components/ui/button/Button.vue'
import type { ContactRowVm, ProfileBadgeVm } from '~/utils/patientDetailFormat'
import { segmentBadgeAttrs } from '~/utils/patientDetailFormat'

defineProps<{
  displayName: string
  initials: string
  externalIdLabel: string
  badges: ProfileBadgeVm[]
  contacts: ContactRowVm[]
}>()
</script>
