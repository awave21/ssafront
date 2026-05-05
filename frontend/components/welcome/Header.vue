<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { WELCOME_NAV } from '~/composables/welcomeData'

const HEADER_H = 64

const scrolled = ref(false)
const onScroll = () => { scrolled.value = window.scrollY > 8 }

onMounted(() => {
  onScroll()
  window.addEventListener('scroll', onScroll, { passive: true })
})
onBeforeUnmount(() => window.removeEventListener('scroll', onScroll))

const scrollTo = (e: MouseEvent, href: string) => {
  e.preventDefault()
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
      scrolled
        ? 'bg-[var(--w-paper)]/85 backdrop-blur-md border-b border-[var(--w-rule)]/70'
        : 'bg-transparent border-b border-transparent',
    ]"
  >
    <div class="max-w-[1280px] mx-auto px-6 lg:px-10 h-16 flex items-center gap-10">
      <a href="#top" class="flex items-baseline gap-1 select-none" @click="scrollTo($event, '#top')">
        <span class="display text-[26px] leading-none">chatmedbot</span>
        <span class="h-1.5 w-1.5 rounded-full translate-y-[-6px]" style="background: var(--w-brand-gradient)" />
      </a>

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
        <button
          type="button"
          disabled
          class="mono px-3 py-2 rounded-full border border-[var(--w-rule)] text-[var(--w-ink-soft)] cursor-not-allowed inline-flex items-center gap-2"
        >
          <span class="h-1.5 w-1.5 rounded-full" style="background: var(--w-brand-gradient)" />
          войти · скоро
        </button>
      </div>
    </div>
  </header>
</template>
