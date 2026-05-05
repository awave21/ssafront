<script setup lang="ts">
import { ArrowUpRight } from 'lucide-vue-next'
import ChatMock from './ChatMock.vue'

const TG = 'https://t.me/order_chatmedbot'
</script>

<template>
  <section id="top" class="welcome-hero-bg relative pt-8 md:pt-10 pb-16 md:pb-24 overflow-hidden">
    <div class="max-w-[1280px] mx-auto px-6 lg:px-10 relative z-10">
      <div class="grid grid-cols-12 gap-x-8 gap-y-12">
        <!-- Left column -->
        <div class="col-span-12 lg:col-span-7">
          <!-- Badge -->
          <div class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-[var(--w-paper-deep)] border border-[var(--w-rule)] mb-5">
            <span class="h-1.5 w-1.5 rounded-full shrink-0" style="background: var(--w-brand-gradient)" />
            <span class="mono text-[var(--w-ink-soft)]">Искусственный интеллект для медицины</span>
          </div>

          <!-- H1 -->
          <h1 class="display text-[clamp(48px,6.5vw,112px)]">
            <span class="word-reveal block" style="font-style: normal; font-variation-settings: 'opsz' 144, 'SOFT' 30; font-weight: 350;">
              <span style="animation-delay:0ms; display:inline-block;">Умные</span>
              <span style="animation-delay:80ms; display:inline-block; margin-left:0.18em;">ИИ-агенты</span>
            </span>
            <span class="word-reveal block mt-1" style="color: var(--w-peach-deep);">
              <span style="animation-delay:220ms; display:inline-block;">для</span>
              <span style="animation-delay:300ms; display:inline-block; margin-left:0.18em;">вашей</span>
              <span style="animation-delay:380ms; display:inline-block; margin-left:0.18em;">клиники</span>
            </span>
          </h1>

          <div class="mt-5 max-w-[520px]">
            <div class="hairline mb-5" />
            <p class="text-[17px] leading-[1.55] text-[var(--w-ink-soft)]">
              Автоматизируйте рутинные задачи, улучшите качество диагностики
              и освободите врачей для работы с пациентами.
              Современные AI-решения для современной медицины.
            </p>
          </div>

          <!-- CTAs -->
          <div class="mt-6 flex flex-col sm:flex-row flex-wrap items-stretch sm:items-center gap-3">
            <a :href="TG" target="_blank" rel="noopener" class="cta-peach inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-full font-medium">
              Запросить демо <ArrowUpRight :size="16" />
            </a>
            <a :href="TG" target="_blank" rel="noopener" class="cta-outline inline-flex items-center justify-center gap-2 px-6 py-3.5 rounded-full font-medium">
              Получить консультацию
            </a>
          </div>

          <!-- Quote -->
          <p class="mt-5 text-[15px] text-[var(--w-ink-soft)] italic opacity-70">
            «Наш администратор не может работать 24/7. А этот — может.»
          </p>
        </div>

        <!-- Chat column -->
        <div class="col-span-12 lg:col-span-5 lg:pt-20 lg:translate-y-10 relative z-20">
          <ChatMock />
        </div>
      </div>
    </div>

    <div aria-hidden="true" class="display select-none pointer-events-none absolute -bottom-16 right-[-2vw] text-[260px] md:text-[420px] leading-none text-[var(--w-peach)]/15" style="font-style:italic;">&ldquo;</div>
  </section>
</template>
