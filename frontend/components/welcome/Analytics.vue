<script setup lang="ts">
import { computed } from 'vue'
import { useReveal } from '~/composables/useReveal'
import StatNumeral from './StatNumeral.vue'
import { WELCOME_METRICS, WELCOME_AREA_DATA, WELCOME_RADAR_DATA } from '~/composables/welcomeData'

const { el: revealEl, isVisible } = useReveal()

// SVG area chart
const W = 640, H = 220, PADX = 28, PADY = 16
const xs = WELCOME_AREA_DATA.map((_, i) => PADX + (i * (W - 2 * PADX)) / (WELCOME_AREA_DATA.length - 1))
const maxY = Math.max(...WELCOME_AREA_DATA.map((d) => d.created)) * 1.1
const yTo = (v: number) => H - PADY - (v / maxY) * (H - 2 * PADY)

const areaCreated = computed(() => {
  const pts = WELCOME_AREA_DATA.map((d, i) => `${xs[i]},${yTo(d.created)}`).join(' L ')
  return `M ${xs[0]},${H - PADY} L ${pts} L ${xs[xs.length - 1]},${H - PADY} Z`
})
const lineCreated = computed(() =>
  WELCOME_AREA_DATA.map((d, i) => `${i === 0 ? 'M' : 'L'} ${xs[i]},${yTo(d.created)}`).join(' ')
)
const areaCancelled = computed(() => {
  const pts = WELCOME_AREA_DATA.map((d, i) => `${xs[i]},${yTo(d.cancelled)}`).join(' L ')
  return `M ${xs[0]},${H - PADY} L ${pts} L ${xs[xs.length - 1]},${H - PADY} Z`
})
const lineCancelled = computed(() =>
  WELCOME_AREA_DATA.map((d, i) => `${i === 0 ? 'M' : 'L'} ${xs[i]},${yTo(d.cancelled)}`).join(' ')
)

// Radar
const RADAR_R = 88, RADAR_CX = 120, RADAR_CY = 120
const angles = WELCOME_RADAR_DATA.labels.map((_, i, arr) => -Math.PI / 2 + (2 * Math.PI * i) / arr.length)
const radarPoints = computed(() =>
  WELCOME_RADAR_DATA.values.map((v, i) => {
    const r = (v / 100) * RADAR_R
    return `${RADAR_CX + r * Math.cos(angles[i])},${RADAR_CY + r * Math.sin(angles[i])}`
  }).join(' ')
)
const radarRings = [0.25, 0.5, 0.75, 1].map((k) => k * RADAR_R)
const radarLabelPos = WELCOME_RADAR_DATA.labels.map((label, i) => ({
  label,
  x: RADAR_CX + (RADAR_R + 16) * Math.cos(angles[i]),
  y: RADAR_CY + (RADAR_R + 16) * Math.sin(angles[i]),
  anchor: Math.cos(angles[i]) > 0.3 ? 'start' : Math.cos(angles[i]) < -0.3 ? 'end' : 'middle',
}))
</script>

<template>
  <section
    id="analytics"
    ref="revealEl"
    :class="['relative py-24 md:py-32 reveal', { 'is-visible': isVisible }]"
    style="background: var(--w-paper-deep);"
  >
    <div class="absolute inset-0 welcome-grid-bg opacity-50" aria-hidden="true" />

    <div class="relative max-w-[1280px] mx-auto px-6 lg:px-10">
      <!-- Heading -->
      <div class="grid grid-cols-12 gap-8 mb-16">
        <div class="col-span-12 md:col-span-7">
          <div class="mono text-[var(--w-ink-soft)] mb-6">— раздел 02</div>
          <h2 class="display text-[clamp(40px,5.5vw,80px)] leading-[1.02]">
            <span style="font-style:normal; font-variation-settings:'opsz' 96,'SOFT' 30; font-weight:350;">Контроль и аналитика —</span>
            <br /><span style="background: var(--w-brand-gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">в одном интерфейсе.</span>
          </h2>
        </div>
        <div class="col-span-12 md:col-span-4 md:col-start-9 self-end">
          <p class="text-[16px] leading-[1.55] text-[var(--w-ink-soft)]">
            Полная аналитика работы ИИ-агентов в режиме реального времени.
          </p>
        </div>
      </div>

      <!-- KPI grid — 4 per row × 2 rows = 8 cards -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4">
        <div
          v-for="m in WELCOME_METRICS"
          :key="m.id"
          :class="[
            'metric-card rounded-2xl px-5 pt-5 pb-6 border transition-all duration-500',
            m.emphasis
              ? 'bg-[var(--w-ink)] border-transparent md:col-span-1 md:row-span-1'
              : m.color === 'orange'
                ? 'bg-[var(--w-surface)] border-[var(--w-rule)]/60'
                : 'bg-[var(--w-surface)] border-[var(--w-rule)]/60',
          ]"
        >
          <div :class="['mono mb-3 truncate text-[10px]', m.emphasis ? 'text-[var(--w-paper)]/60' : 'text-[var(--w-ink-soft)]']">
            {{ m.source }}
          </div>
          <div :class="m.emphasis ? 'text-[var(--w-peach)]' : 'text-[var(--w-ink)]'">
            <StatNumeral
              :value="m.value"
              :prefix="m.prefix"
              :suffix="m.suffix"
              size="lg"
            />
          </div>
          <div :class="['mt-2 text-[14px] leading-tight', m.emphasis ? 'text-[var(--w-paper)]' : 'text-[var(--w-ink)]']">
            {{ m.label }}
          </div>
          <div class="mt-3 flex items-center gap-1.5">
            <span :class="['h-1 w-3', m.color === 'orange' ? 'bg-[var(--w-peach-deep)]' : m.emphasis ? 'bg-[var(--w-peach)]' : 'bg-[var(--w-green)]']" />
            <span :class="['mono font-medium', m.color === 'orange' ? 'text-[var(--w-peach-deep)]' : m.emphasis ? 'text-[var(--w-peach)]' : 'text-[var(--w-green-deep)]']">
              {{ m.badge }}
            </span>
          </div>
        </div>
      </div>

      <!-- Charts -->
      <div class="mt-10 grid grid-cols-12 gap-6">
        <!-- Area chart -->
        <div class="col-span-12 lg:col-span-7 rounded-2xl bg-[var(--w-surface)] border border-[var(--w-rule)]/60 p-7">
          <div class="flex items-baseline justify-between mb-5">
            <div>
              <div class="mono text-[var(--w-ink-soft)]">динамика записей · неделя</div>
              <h4 class="serif text-[20px] mt-1" style="font-variation-settings:'opsz' 64; font-weight:500;">Созданные и отменённые записи</h4>
            </div>
            <div class="flex items-center gap-4 mono text-[var(--w-ink-soft)]">
              <span class="inline-flex items-center gap-1.5"><span class="h-2 w-2 rounded-full bg-[var(--w-green)]" />созданные</span>
              <span class="inline-flex items-center gap-1.5"><span class="h-2 w-2 rounded-full bg-[#C56666]" />отменённые</span>
            </div>
          </div>
          <svg :viewBox="`0 0 ${W} ${H}`" class="w-full h-[240px]" preserveAspectRatio="none">
            <defs>
              <linearGradient id="gTeal" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#4A9B7F" stop-opacity="0.35"/>
                <stop offset="100%" stop-color="#4A9B7F" stop-opacity="0"/>
              </linearGradient>
              <linearGradient id="gRed" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#C56666" stop-opacity="0.28"/>
                <stop offset="100%" stop-color="#C56666" stop-opacity="0"/>
              </linearGradient>
            </defs>
            <line :x1="PADX" :y1="H-PADY" :x2="W-PADX" :y2="H-PADY" stroke="#D9D2C4" stroke-width="1"/>
            <path :d="areaCreated" fill="url(#gTeal)"/>
            <path :d="lineCreated" fill="none" stroke="#2A6B55" stroke-width="2" stroke-linecap="round"/>
            <path :d="areaCancelled" fill="url(#gRed)"/>
            <path :d="lineCancelled" fill="none" stroke="#C56666" stroke-width="1.5" stroke-dasharray="2 4" stroke-linecap="round"/>
            <circle v-for="(d,i) in WELCOME_AREA_DATA" :key="i" :cx="xs[i]" :cy="yTo(d.created)" r="3" fill="var(--w-paper)" stroke="#2A6B55" stroke-width="1.5"/>
            <text v-for="(d,i) in WELCOME_AREA_DATA" :key="'l'+i" :x="xs[i]" :y="H-2" text-anchor="middle" font-family="JetBrains Mono" font-size="9" fill="#5A5F5C" letter-spacing="0.12em">{{d.week.toUpperCase()}}</text>
          </svg>
        </div>

        <!-- Radar -->
        <div class="col-span-12 lg:col-span-5 rounded-2xl bg-[var(--w-surface)] border border-[var(--w-rule)]/60 p-7">
          <div class="mono text-[var(--w-ink-soft)] mb-1">производительность ии-агента</div>
          <h4 class="serif text-[20px]" style="font-variation-settings:'opsz' 64; font-weight:500;">Метрики качества работы</h4>
          <svg viewBox="0 0 240 260" class="w-full h-[260px] mt-2">
            <circle v-for="(r,i) in radarRings" :key="i" :cx="RADAR_CX" :cy="RADAR_CY" :r="r" fill="none" stroke="#D9D2C4" stroke-width="1" :stroke-dasharray="i < radarRings.length-1 ? '2 3' : ''"/>
            <line v-for="(a,i) in angles" :key="'a'+i" :x1="RADAR_CX" :y1="RADAR_CY" :x2="RADAR_CX+RADAR_R*Math.cos(a)" :y2="RADAR_CY+RADAR_R*Math.sin(a)" stroke="#D9D2C4" stroke-width="1"/>
            <polygon :points="radarPoints" fill="rgba(74,155,127,0.25)" stroke="#2A6B55" stroke-width="1.5"/>
            <text v-for="(l,i) in radarLabelPos" :key="'lab'+i" :x="l.x" :y="l.y" :text-anchor="l.anchor" font-family="JetBrains Mono" font-size="8" fill="#5A5F5C" letter-spacing="0.1em" dominant-baseline="middle">{{l.label.toUpperCase()}}</text>
          </svg>
        </div>
      </div>
    </div>
  </section>
</template>
