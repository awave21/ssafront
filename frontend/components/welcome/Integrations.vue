<script setup lang="ts">
import { ref } from 'vue'
import { useReveal } from '~/composables/useReveal'
import { WELCOME_INTEGRATIONS } from '~/composables/welcomeData'

const active = ref(WELCOME_INTEGRATIONS[0].id)
const { el: revealEl, isVisible } = useReveal()
</script>

<template>
  <section
    id="integrations"
    ref="revealEl"
    :class="['py-24 md:py-32 reveal', { 'is-visible': isVisible }]"
  >
    <div class="max-w-[1280px] mx-auto px-6 lg:px-10">
      <div class="grid grid-cols-12 gap-8 mb-14">
        <div class="col-span-12 md:col-span-7">
          <div class="mono text-[var(--w-ink-soft)] mb-6">— раздел 03</div>
          <h2 class="display text-[clamp(26px,8vw,80px)] leading-[1.02]">
            <span style="font-style: normal; font-variation-settings: 'opsz' 96, 'SOFT' 30; font-weight: 350;">Встраивается в ваше</span><br />
            <span style="background: var(--w-brand-gradient); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;">рабочее пространство.</span>
          </h2>
        </div>
        <div class="col-span-12 md:col-span-4 md:col-start-9 self-end">
          <p class="text-[16px] leading-[1.55] text-[var(--w-ink-soft)]">
            Chatmedbot готов встроиться в вашу МИС и обрабатывать запросы
            через привычные мессенджеры и сервисы.
          </p>
        </div>
      </div>

      <!-- Tabs -->
      <div class="flex flex-wrap gap-2 mb-10">
        <button
          v-for="g in WELCOME_INTEGRATIONS"
          :key="g.id"
          type="button"
          @click="active = g.id"
          :class="[
            'mono px-4 py-2 rounded-full border transition-colors duration-300 inline-flex items-center gap-2',
            active === g.id
              ? 'bg-[var(--w-ink)] text-[var(--w-paper)] border-[var(--w-ink)]'
              : 'bg-[var(--w-surface)] text-[var(--w-ink-soft)] border-[var(--w-rule)] hover:text-[var(--w-ink)]',
          ]"
        >
          <span class="text-base">{{ g.emoji }}</span>
          {{ g.label }}
        </button>
      </div>

      <!-- Active group display -->
      <div class="grid grid-cols-12 gap-6">
        <template v-for="g in WELCOME_INTEGRATIONS" :key="g.id">
          <div
            v-show="active === g.id"
            class="col-span-12 grid grid-cols-12 gap-6 items-stretch"
          >
            <!-- Big editorial card -->
            <div class="col-span-12 md:col-span-7 rounded-3xl bg-[var(--w-paper-deep)] p-10 relative overflow-hidden">
              <div class="flex items-start justify-between mb-8">
                <div>
                  <div class="mono text-[var(--w-peach-deep)] mb-3">канал · {{ g.label.toLowerCase() }}</div>
                  <h3 class="serif text-[clamp(28px,3vw,42px)] leading-[1.15]" style="font-variation-settings: 'opsz' 96; font-weight: 500;">
                    {{ g.label }} — без посредников и интеграторов.
                  </h3>
                </div>
                <div class="text-[64px] leading-none">{{ g.emoji }}</div>
              </div>
              <ul class="space-y-3">
                <li
                  v-for="(item, i) in g.items"
                  :key="item"
                  class="flex items-baseline gap-4 border-t border-[var(--w-rule)] pt-3"
                >
                  <span class="numeral text-2xl text-[var(--w-peach-deep)]">{{ String(i + 1).padStart(2, '0') }}</span>
                  <span class="serif text-[18px]">{{ item }}</span>
                  <span class="ml-auto mono text-[var(--w-ink-soft)]">подключено</span>
                </li>
              </ul>
            </div>

            <!-- Side cards -->
            <div class="col-span-12 md:col-span-5 grid grid-rows-2 gap-6">
              <div class="rounded-3xl bg-[var(--w-surface)] border border-[var(--w-rule)]/60 p-7">
                <div class="mono text-[var(--w-ink-soft)] mb-3">примечание редакции</div>
                <p class="serif text-[20px] leading-[1.45]">
                  Агент видит контекст пациента из всех каналов: переписка
                  в Telegram продолжается на сайте без потери истории.
                </p>
              </div>
              <div class="rounded-3xl bg-[var(--w-ink)] text-[var(--w-paper)] p-7 relative overflow-hidden">
                <div class="mono opacity-60 mb-2">SLA внедрения</div>
                <div class="numeral text-[80px] leading-none text-[var(--w-peach)]">3 дня</div>
                <p class="mt-3 text-[14px] opacity-80 max-w-[260px]">
                  От подписания договора до первой реальной записи через агента.
                </p>
                <div
                  aria-hidden="true"
                  class="absolute -right-10 -bottom-12 h-44 w-44 rounded-full bg-[var(--w-peach)]/10 blur-2xl"
                />
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>
  </section>
</template>
