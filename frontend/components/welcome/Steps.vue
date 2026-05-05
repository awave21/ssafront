<script setup lang="ts">
import { Check } from 'lucide-vue-next'
import { useReveal } from '~/composables/useReveal'
import { WELCOME_STEPS } from '~/composables/welcomeData'

const { el: revealEl, isVisible } = useReveal()
</script>

<template>
  <section id="steps" ref="revealEl" :class="['py-24 md:py-32 reveal', { 'is-visible': isVisible }]" style="background: var(--w-paper);">
    <div class="max-w-[1280px] mx-auto px-6 lg:px-10">
      <div class="grid grid-cols-12 gap-8 mb-16">
        <div class="col-span-12 md:col-span-6">
          <div class="mono text-[var(--w-ink-soft)] mb-6">— раздел 04</div>
          <h2 class="display text-[clamp(26px,8vw,80px)] leading-[1.02]">
            <span style="font-style: normal; font-variation-settings: 'opsz' 96, 'SOFT' 30; font-weight: 350;">Как проходит</span><br />
            <span style="background: var(--w-brand-gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">внедрение.</span>
          </h2>
        </div>
        <div class="col-span-12 md:col-span-5 md:col-start-8 self-end">
          <p class="text-[16px] leading-[1.55] text-[var(--w-ink-soft)]">
            Каждый этап — это конкретный артефакт: документ, дашборд или
            работающий канал. Никаких «скоро будет». Полный цикл
            занимает 3–6 недель в зависимости от размера клиники.
          </p>
        </div>
      </div>

      <!-- Vertical timeline -->
      <div class="relative grid grid-cols-12 gap-x-4 md:gap-x-8">
        <!-- Rail — только md+ -->
        <div
          aria-hidden="true"
          class="hidden md:block absolute left-[calc(16.66%+8px)] top-0 bottom-0 timeline-rail"
        />
        <div
          aria-hidden="true"
          :class="['hidden md:block absolute left-[calc(16.66%+8px)] top-0 timeline-rail-fill']"
          :style="{ height: '100%', transform: isVisible ? 'scaleY(1)' : 'scaleY(0)' }"
        />

        <article
          v-for="(s, i) in WELCOME_STEPS"
          :key="s.n"
          class="col-span-12 grid grid-cols-12 gap-x-4 md:gap-x-8 py-10 md:py-12 first:pt-0 last:pb-0 border-b border-[var(--w-rule)] last:border-b-0"
        >
          <div class="col-span-3 md:col-span-2 relative">
            <div
              class="numeral text-[var(--w-peach-deep)]"
              style="font-size: clamp(56px, 10vw, 168px); line-height: 0.9;"
            >
              {{ s.n }}
            </div>
            <div
              class="absolute left-[calc(100%-8px)] top-[42px] md:top-[58px] h-3 w-3 rounded-full bg-[var(--w-peach)] ring-4 ring-[var(--w-paper)] hidden md:block"
            />
          </div>
          <div class="col-span-9 md:col-span-10 md:pl-12 lg:pl-16" :class="i % 2 === 1 ? 'md:translate-y-6' : ''">
            <div class="mono text-[var(--w-ink-soft)] mb-3">этап · {{ s.n }} / {{ WELCOME_STEPS.length }}</div>
            <h3 class="serif text-[clamp(24px,2.6vw,38px)] leading-[1.15] mb-4" style="font-variation-settings: 'opsz' 96; font-weight: 500;">
              {{ s.title }}
            </h3>
            <p class="text-[16px] leading-[1.6] text-[var(--w-ink-soft)] max-w-[680px] mb-6">{{ s.body }}</p>
            <ul class="grid grid-cols-1 sm:grid-cols-3 gap-3 max-w-[820px]">
              <li
                v-for="b in s.bullets"
                :key="b"
                class="flex items-start gap-2.5 rounded-xl bg-[var(--w-surface)] border border-[var(--w-rule)]/60 px-4 py-3"
              >
                <Check :size="14" class="text-[var(--w-peach-deep)] mt-1 shrink-0" />
                <span class="text-[14px] leading-snug">{{ b }}</span>
              </li>
            </ul>
          </div>
        </article>
      </div>

      <!-- CTA block -->
      <div class="mt-16 rounded-2xl md:rounded-3xl bg-[var(--w-ink)] text-[var(--w-paper)] p-6 sm:p-10 md:p-14 relative overflow-hidden">
        <div aria-hidden="true" class="absolute -right-20 -bottom-20 h-72 w-72 rounded-full bg-[var(--w-peach)]/10 blur-3xl" />
        <div class="relative z-10 flex flex-col md:grid md:grid-cols-12 md:gap-8 items-start md:items-center gap-6">
          <div class="md:col-span-7">
            <div class="mono text-[var(--w-peach)] mb-4">Готовы начать?</div>
            <h3 class="serif text-[clamp(22px,5vw,48px)] leading-[1.15]" style="font-variation-settings:'opsz' 96; font-weight:500;">
              Запустите ChatMedBot в вашей клинике — от заявки до первого диалога.
            </h3>
          </div>
          <div class="md:col-span-5 flex flex-col sm:flex-row md:flex-col lg:flex-row gap-3 w-full md:w-auto">
            <a
              href="https://t.me/order_chatmedbot"
              target="_blank"
              rel="noopener"
              class="cta-peach inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-full font-medium text-center"
            >
              Запросить демо
            </a>
            <a
              href="https://t.me/order_chatmedbot"
              target="_blank"
              rel="noopener"
              class="inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-full font-medium border border-[var(--w-paper)]/30 text-[var(--w-paper)] hover:border-[var(--w-paper)]/60 transition-colors text-center"
            >
              Получить консультацию
            </a>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
