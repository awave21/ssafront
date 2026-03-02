<script setup lang="ts">
import { PanelLeftOpen } from 'lucide-vue-next'
import { useLayoutState } from '~/composables/useLayoutState'

const { toggleSidebar } = useLayoutState()
</script>

<template>
  <header class="h-[60px] bg-background border-b border-border flex items-center justify-between px-6 shrink-0">
    <div class="flex items-center gap-3">
      <!-- Кнопка сворачивания сайдбара -->
      <button
        @click="toggleSidebar"
        class="hidden lg:flex w-8 h-8 rounded-md items-center justify-center bg-muted text-muted-foreground hover:text-foreground transition-colors"
        aria-label="Свернуть/развернуть сайдбар"
      >
        <PanelLeftOpen class="w-[18px] h-[18px]" />
      </button>
      <!-- Слот для хлебных крошек / заголовка -->
      <slot name="left" />
    </div>
    <div class="flex items-center gap-3">
      <!-- Слот для кнопок действий -->
      <slot name="right" />
    </div>
  </header>
</template>
