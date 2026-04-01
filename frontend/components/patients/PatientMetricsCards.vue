<template>
  <div class="grid min-w-0 grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
    <div
      class="group relative overflow-hidden rounded-3xl border border-slate-100 bg-white p-5 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_12px_24px_-8px_rgba(0,0,0,0.08)]"
    >
      <div class="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">
        <Wallet class="h-4 w-4" />
        Фактическая выручка
      </div>
      <div class="mt-2 break-words text-xl font-black tracking-tight text-slate-900 sm:text-2xl">
        {{ formatRub(revenueRub) }}
      </div>
      <p class="mt-1 text-[10px] font-medium text-slate-400">LTV по данным интеграции</p>
    </div>
    <div
      class="group relative overflow-hidden rounded-3xl border border-slate-100 bg-white p-5 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_12px_24px_-8px_rgba(0,0,0,0.08)]"
    >
      <div class="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider text-slate-400">
        <Stethoscope class="h-4 w-4" />
        Количество визитов
      </div>
      <div class="mt-2 break-words text-xl font-black tracking-tight text-slate-900 sm:text-2xl">
        {{ visitsCountDisplay }}
      </div>
      <p class="mt-1 text-[10px] font-medium text-slate-400">Записей в кэше визитов</p>
    </div>
    <div
      class="group relative overflow-hidden rounded-3xl border border-primary/20 bg-primary/[0.04] p-5 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_12px_24px_-8px_rgba(0,0,0,0.08)]"
    >
      <div class="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider text-primary">
        <CalendarClock class="h-4 w-4" />
        Ближайший визит
      </div>
      <div class="mt-2 break-words text-xl font-black tracking-tight text-slate-900 sm:text-2xl">
        {{ nextVisit.title }}
      </div>
      <p class="mt-1 break-words text-[10px] font-medium text-primary">{{ nextVisit.sub }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { CalendarClock, Stethoscope, Wallet } from 'lucide-vue-next'
import { formatRub } from '~/utils/patientDetailFormat'

defineProps<{
  revenueRub: number
  visitsCountDisplay: string
  nextVisit: { title: string; sub: string }
}>()
</script>
