<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Menu } from 'lucide-vue-next'
import DashboardSidebar from '~/components/DashboardSidebar.vue'
import DashboardTopBar from '~/components/DashboardTopBar.vue'
import { useLayoutState } from '~/composables/useLayoutState'

const { initSidebarState, pageTitle } = useLayoutState()
const isMobileSidebarOpen = ref(false)

onMounted(() => {
  initSidebarState()
})
</script>

<template>
  <div class="h-screen flex overflow-hidden bg-muted">
    <!-- Desktop Sidebar (закреплен) -->
    <DashboardSidebar class="hidden lg:flex" />

    <!-- Mobile Sidebar Overlay -->
    <Teleport to="body">
      <Transition
        enter-active-class="transition-opacity duration-300"
        enter-from-class="opacity-0"
        enter-to-class="opacity-100"
        leave-active-class="transition-opacity duration-200"
        leave-from-class="opacity-100"
        leave-to-class="opacity-0"
      >
        <div
          v-if="isMobileSidebarOpen"
          class="lg:hidden fixed inset-0 z-40 bg-black/50"
          @click="isMobileSidebarOpen = false"
        />
      </Transition>

      <Transition
        enter-active-class="transition-transform duration-300 ease-out"
        enter-from-class="-translate-x-full"
        enter-to-class="translate-x-0"
        leave-active-class="transition-transform duration-200 ease-in"
        leave-from-class="translate-x-0"
        leave-to-class="-translate-x-full"
      >
        <DashboardSidebar
          v-if="isMobileSidebarOpen"
          class="lg:hidden fixed inset-y-0 left-0 z-50"
          @close="isMobileSidebarOpen = false"
        />
      </Transition>
    </Teleport>

    <!-- Основная область -->
    <div class="flex-1 flex flex-col min-w-0 overflow-hidden">
      <!-- Верхний хедер (закреплен, не скроллится) -->
      <DashboardTopBar>
        <template #left>
          <!-- Заголовок страницы -->
          <h1 v-if="pageTitle" class="text-xl font-bold text-foreground">
            {{ pageTitle }}
          </h1>
        </template>
        <template #right>
          <div id="topbar-actions" class="contents" />
          <!-- Кнопка мобильного меню (только на планшете/мобиле) -->
          <button
            class="lg:hidden p-2 rounded-lg text-foreground hover:bg-muted"
            @click="isMobileSidebarOpen = true"
          >
            <Menu class="w-5 h-5" />
          </button>
        </template>
      </DashboardTopBar>

      <!-- Прокручиваемый контент -->
      <main class="flex-1 overflow-y-auto bg-muted">
        <slot />
      </main>
    </div>
  </div>
</template>