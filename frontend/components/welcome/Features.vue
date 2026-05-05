<script setup lang="ts">
import { useReveal } from '~/composables/useReveal'
import { WELCOME_FEATURES } from '~/composables/welcomeData'

const { el: revealEl, isVisible } = useReveal()
</script>

<template>
  <section id="features" ref="revealEl" :class="['py-24 md:py-32 reveal', { 'is-visible': isVisible }]">
    <div class="max-w-[1280px] mx-auto px-6 lg:px-10">
      <!-- Heading -->
      <div class="grid grid-cols-12 gap-8 mb-20">
        <div class="col-span-12 md:col-span-4">
          <div class="mono text-[var(--w-ink-soft)] mb-6">— раздел 01</div>
          <h2 class="display text-[clamp(40px,5.5vw,80px)]">
            <span style="font-style:normal; font-variation-settings:'opsz' 96,'SOFT' 30; font-weight:350;">Почему</span><br />
            <span style="background: var(--w-brand-gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">Chatmedbot</span>?
          </h2>
        </div>
        <div class="col-span-12 md:col-span-7 md:col-start-6 self-end">
          <p class="serif text-[20px] leading-[1.5] text-[var(--w-ink)]">
            Умные ИИ-агенты для вашей клиники. Автоматизируйте рутинные задачи,
            улучшите качество диагностики и освободите врачей для работы с пациентами.
          </p>
        </div>
      </div>

      <!-- 3 cards -->
      <div class="grid grid-cols-12 gap-6">
        <article
          v-for="(f, i) in WELCOME_FEATURES"
          :key="f.n"
          :class="[
            'col-span-12 md:col-span-4 group relative pt-10 pb-8 px-7 rounded-2xl bg-[var(--w-surface)] border border-[var(--w-rule)]/60',
            'transition-all duration-500 hover:-translate-y-1 hover:shadow-[0_24px_60px_-28px_rgba(31,36,33,0.18)]',
          ]"
          :style="{ transitionDelay: i * 80 + 'ms' }"
        >
          <div class="absolute top-7 right-7 numeral text-5xl text-[var(--w-peach)]/35 group-hover:text-[var(--w-peach)] transition-colors duration-500">
            {{ f.n }}
          </div>
          <div class="serif text-[24px] leading-[1.15] mb-4 max-w-[85%]" style="font-variation-settings:'opsz' 64,'SOFT' 30; font-weight:500;">
            {{ f.title }}
          </div>
          <p class="text-[15px] leading-[1.55] text-[var(--w-ink-soft)]">{{ f.body }}</p>

          <div v-if="f.stat" class="mt-6 rounded-lg bg-[var(--w-paper-deep)] px-4 py-3">
            <div class="numeral text-[28px] text-[var(--w-peach-deep)]">{{ f.stat }}</div>
            <div class="text-[13px] text-[var(--w-ink-soft)] mt-0.5">{{ f.statLabel }}</div>
          </div>
          <div v-else class="mt-6 hairline" />
        </article>
      </div>

      <!-- Deep experience block -->
      <div class="mt-24 grid grid-cols-12 gap-8">
        <div class="col-span-12 md:col-span-12 relative pt-10 pb-12 pl-8 md:pl-16 pr-8 rounded-3xl bg-[var(--w-paper-deep)]">
          <div aria-hidden="true" class="display absolute -top-8 left-4 md:left-8 text-[200px] leading-none text-[var(--w-peach)]/35 select-none" style="font-style:italic;">&ldquo;</div>
          <div class="mono text-[var(--w-peach-deep)] mb-4 relative z-10">Глубокий практический опыт</div>
          <h3 class="serif text-[clamp(24px,3vw,40px)] leading-[1.2] mb-5 relative z-10 max-w-[900px]" style="font-variation-settings:'opsz' 96; font-weight:500;">
            Создатели <em>ChatMedBot</em> не понаслышке знают, как работают администраторы,
            операторы, менеджеры продаж и тонкости взаимодействия с МИС.
          </h3>
          <p class="text-[16px] leading-[1.6] text-[var(--w-ink-soft)] max-w-[860px] relative z-10">
            Именно поэтому <strong>ChatMedBot — это не игрушка, а реальный рабочий инструмент</strong>, приносящий выгоды.
          </p>
        </div>
      </div>
    </div>
  </section>
</template>
