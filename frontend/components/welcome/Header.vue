<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { WELCOME_NAV } from '~/composables/welcomeData'

const HEADER_H = 64

const scrolled = ref(false)
const mobileOpen = ref(false)

const onScroll = () => { scrolled.value = window.scrollY > 8 }

onMounted(() => {
  onScroll()
  window.addEventListener('scroll', onScroll, { passive: true })
})
onBeforeUnmount(() => window.removeEventListener('scroll', onScroll))

const scrollTo = (e: MouseEvent, href: string) => {
  e.preventDefault()
  mobileOpen.value = false
  const id = href.replace('#', '')
  const el = id === 'top' ? document.body : document.getElementById(id)
  if (!el) return
  const top = id === 'top' ? 0 : el.getBoundingClientRect().top + window.scrollY - HEADER_H
  window.scrollTo({ top, behavior: 'smooth' })
}
</script>

<template>
  <header
    :class="[
      'sticky top-0 z-40 transition-[background,border-color,backdrop-filter] duration-300',
      scrolled || mobileOpen
        ? 'bg-[var(--w-paper)]/95 backdrop-blur-md border-b border-[var(--w-rule)]/70'
        : 'bg-transparent border-b border-transparent',
    ]"
  >
    <div class="max-w-[1280px] mx-auto px-6 lg:px-10 h-16 flex items-center gap-6">
      <!-- Логотип -->
      <a href="#top" class="flex items-baseline gap-1 select-none shrink-0" @click="scrollTo($event, '#top')">
        <span class="display text-[24px] md:text-[26px] leading-none">chatmedbot</span>
        <span class="h-1.5 w-1.5 rounded-full translate-y-[-6px]" style="background: var(--w-brand-gradient)" />
      </a>

      <!-- Десктоп-навигация -->
      <nav class="hidden md:flex items-center gap-7 ml-2">
        <a
          v-for="n in WELCOME_NAV"
          :key="n.href"
          :href="n.href"
          class="mono text-[var(--w-ink-soft)] hover:text-[var(--w-ink)] transition-colors"
          @click="scrollTo($event, n.href)"
        >
          {{ n.label }}
        </a>
      </nav>

      <div class="ml-auto flex items-center gap-3">
        <span class="mono hidden sm:inline text-[var(--w-ink-soft)]">v 2026.05</span>

        <!-- Войти — ссылка на ЛК -->
        <a
          href="https://lk.chatmedbot.ru"
          class="mono px-3 py-2 rounded-full border border-[var(--w-rule)] text-[var(--w-ink-soft)] hover:text-[var(--w-ink)] hover:border-[var(--w-ink)] transition-colors inline-flex items-center gap-2"
        >
          <span class="h-1.5 w-1.5 rounded-full" style="background: var(--w-brand-gradient)" />
          войти
        </a>

        <!-- Гамбургер (только мобилка) -->
        <button
          type="button"
          class="md:hidden flex flex-col gap-1.5 p-1 -mr-1"
          :aria-label="mobileOpen ? 'Закрыть меню' : 'Открыть меню'"
          @click="mobileOpen = !mobileOpen"
        >
          <span :class="['block h-px w-6 bg-[var(--w-ink)] transition-all duration-300 origin-center', mobileOpen ? 'translate-y-[7px] rotate-45' : '']" />
          <span :class="['block h-px w-6 bg-[var(--w-ink)] transition-all duration-300', mobileOpen ? 'opacity-0 scale-x-0' : '']" />
          <span :class="['block h-px w-6 bg-[var(--w-ink)] transition-all duration-300 origin-center', mobileOpen ? '-translate-y-[7px] -rotate-45' : '']" />
        </button>
      </div>
    </div>

    <!-- Мобильное меню -->
    <Transition
      enter-active-class="transition-all duration-300 ease-out"
      enter-from-class="opacity-0 -translate-y-2"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition-all duration-200 ease-in"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 -translate-y-2"
    >
      <nav v-if="mobileOpen" class="md:hidden border-t border-[var(--w-rule)]/60 px-6 py-5 flex flex-col gap-1">
        <a
          v-for="n in WELCOME_NAV"
          :key="n.href"
          :href="n.href"
          class="mono text-[var(--w-ink-soft)] hover:text-[var(--w-ink)] transition-colors py-3 border-b border-[var(--w-rule)]/40 last:border-b-0"
          @click="scrollTo($event, n.href)"
        >
          {{ n.label }}
        </a>
        <a
          href="https://t.me/order_chatmedbot"
          target="_blank"
          rel="noopener"
          class="mt-3 cta-peach inline-flex items-center justify-center gap-2 px-6 py-3 rounded-full font-medium text-[14px]"
        >
          Запросить демо
        </a>
      </nav>
    </Transition>
  </header>
</template>
