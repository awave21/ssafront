<template>
  <component
    :is="subHref ? resolveComponent('NuxtLink') : 'div'"
    :to="subHref ?? undefined"
    class="group relative overflow-hidden rounded-3xl border border-slate-100 bg-white p-6 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-all hover:-translate-y-0.5 hover:shadow-[0_20px_40px_-12px_rgba(0,0,0,0.08)] duration-500 block"
    :class="[accentBg, subHref ? 'cursor-pointer' : '']"
  >
    <div class="absolute -right-8 -top-8 h-28 w-28 rounded-full opacity-10 transition-transform duration-700 group-hover:scale-150" :class="accentCircle"></div>
    <div class="relative flex items-start justify-between gap-3">
      <div class="min-w-0 flex-1">
        <div class="text-[11px] font-black uppercase tracking-wider text-slate-400">{{ label }}</div>
        <div class="mt-2 text-3xl font-black leading-tight tabular-nums text-slate-900">{{ displayValue }}</div>
        <div v-if="sub" class="mt-1 inline-flex items-center gap-0.5 text-xs font-medium" :class="subHref ? 'text-amber-500' : 'text-slate-400'">
          {{ sub }}<span v-if="subHref"> →</span>
        </div>
      </div>
      <div class="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl" :class="accentIcon">
        <component :is="icon" class="h-5 w-5" />
      </div>
    </div>
  </component>
</template>

<script setup lang="ts">
import { resolveComponent } from 'vue'
import type { Component } from 'vue'

const props = defineProps<{
  label: string
  value: number | string
  icon: Component
  accent?: 'primary' | 'amber' | 'rose' | 'emerald' | 'slate'
  sub?: string
  subHref?: string
  format?: 'number' | 'pct' | 'money' | 'ms' | 'raw'
}>()

const accentBg = {
  primary: '',
  amber: '',
  rose: '',
  emerald: '',
  slate: '',
}[props.accent ?? 'primary']

const accentCircle = {
  primary: 'bg-primary',
  amber: 'bg-amber-500',
  rose: 'bg-rose-500',
  emerald: 'bg-emerald-500',
  slate: 'bg-slate-500',
}[props.accent ?? 'primary']

const accentIcon = {
  primary: 'bg-primary/10 text-primary',
  amber: 'bg-amber-50 text-amber-600',
  rose: 'bg-rose-50 text-rose-600',
  emerald: 'bg-emerald-50 text-emerald-600',
  slate: 'bg-slate-100 text-slate-600',
}[props.accent ?? 'primary']

const displayValue = (() => {
  const v = props.value
  if (typeof v === 'string') return v
  if (props.format === 'pct') return v + '%'
  if (props.format === 'money') {
    if (Math.abs(v) >= 1_000_000) return (v / 1_000_000).toFixed(1) + ' млн ₽'
    if (Math.abs(v) >= 10_000) return Math.round(v / 1000) + ' тыс ₽'
    return Math.round(v).toLocaleString('ru-RU') + ' ₽'
  }
  if (props.format === 'ms') {
    if (v >= 1000) return (v / 1000).toFixed(1) + ' с'
    return Math.round(v) + ' мс'
  }
  return typeof v === 'number' ? v.toLocaleString('ru-RU') : v
})()
</script>
