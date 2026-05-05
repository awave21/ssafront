<script setup lang="ts">
import { ArrowUpRight } from 'lucide-vue-next'
const TG = 'https://t.me/order_chatmedbot'
</script>

<template>
  <section class="py-20 md:py-28">
    <div class="max-w-[1280px] mx-auto px-6 lg:px-10">
      <div class="relative rounded-[32px] bg-[var(--w-peach-tint)] overflow-hidden border border-[var(--w-peach)]/30">
        <div class="absolute inset-0 welcome-grid-bg opacity-60" aria-hidden="true" />
        <div
          aria-hidden="true"
          class="absolute -top-32 -right-24 h-80 w-80 rounded-full bg-[var(--w-peach)]/30 blur-3xl"
        />
        <div
          aria-hidden="true"
          class="display absolute -bottom-20 -left-6 text-[280px] leading-none text-[var(--w-peach)]/30 select-none"
          style="font-style: italic;"
        >&rdquo;</div>

        <div class="relative grid grid-cols-12 gap-8 px-8 md:px-14 py-14 md:py-20">
          <div class="col-span-12 md:col-span-7">
            <div class="mono text-[var(--w-peach-deep)] mb-6">готовы начать?</div>
            <h2 class="display text-[clamp(40px,6vw,92px)] leading-[1]">
              <span style="font-style: normal; font-variation-settings: 'opsz' 144, 'SOFT' 30; font-weight: 350;">Один разговор —</span><br />
              и ваш агент<br />
              <span style="background: var(--w-brand-gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">в работе.</span>
            </h2>
          </div>
          <div class="col-span-12 md:col-span-5 self-end">
            <p class="serif text-[18px] leading-[1.5] text-[var(--w-ink)] mb-8 max-w-[420px]">
              Мы покажем демо на вашей реальной переписке и обсудим, что можно
              автоматизировать в первую очередь — без обязательств.
            </p>
            <div class="flex flex-wrap gap-3">
              <a
                :href="TG"
                target="_blank"
                rel="noopener"
                class="cta-peach inline-flex items-center gap-2 px-7 py-4 rounded-full font-medium text-[16px]"
              >
                Запросить демо
                <ArrowUpRight :size="17" />
              </a>
              <a
                :href="TG"
                target="_blank"
                rel="noopener"
                class="cta-outline inline-flex items-center gap-2 px-7 py-4 rounded-full font-medium text-[16px]"
              >
                Получить консультацию
              </a>
            </div>
            <div class="mt-6 mono text-[var(--w-ink-soft)]">
              без обязательств · ответ в течение 12 минут
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
