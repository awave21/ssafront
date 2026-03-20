<template>
  <div class="group bg-white rounded-2xl border border-slate-200 p-6 hover:shadow-xl hover:shadow-slate-200/50 transition-all duration-300 hover:-translate-y-1">
    <!-- Header Section -->
    <div class="flex items-start justify-between mb-6">
      <div class="flex items-start gap-4 flex-1 min-w-0">
        <!-- Avatar with Gradient -->
        <div
          class="relative flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br shrink-0 shadow-lg"
          :class="avatarColor"
        >
          <Bot class="h-8 w-8 text-white" />
          <div class="absolute -bottom-2 -right-2 w-6 h-6 bg-white rounded-full flex items-center justify-center shadow-md">
            <div
              class="w-3 h-3 rounded-full"
              :class="status === 'published' ? 'bg-emerald-500' : 'bg-amber-500'"
            ></div>
          </div>
        </div>

        <!-- Title and Meta -->
        <div class="flex-1 min-w-0">
          <h3 class="text-xl font-bold text-slate-900 mb-2 truncate group-hover:text-indigo-600 transition-colors">
            {{ title }}
          </h3>
          <div class="flex items-center flex-wrap gap-2">
            <!-- Status Badge -->
            <span
              class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold"
              :class="[
                status === 'published'
                  ? 'bg-emerald-50 text-emerald-700'
                  : 'bg-amber-50 text-amber-700'
              ]"
            >
              <div
                class="w-1.5 h-1.5 rounded-full"
                :class="status === 'published' ? 'bg-emerald-500' : 'bg-amber-500'"
              ></div>
              {{ status === 'published' ? 'Активен' : 'Черновик' }}
            </span>

            <!-- Type Badge -->
            <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-100 text-slate-700">
              <Sparkles class="h-3 w-3" />
              {{ type }}
            </span>
          </div>
        </div>
      </div>

      <!-- Action Buttons -->
      <div class="flex items-center gap-2 shrink-0 ml-4">
        <button
          v-if="agentId"
          @click="navigateToAgent"
          class="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-indigo-500 to-purple-600 text-white rounded-lg font-medium hover:from-indigo-600 hover:to-purple-700 transition-all shadow-sm hover:shadow-md"
        >
          <Settings class="h-4 w-4" />
          <span class="hidden sm:inline">Настроить</span>
        </button>
        <button
          class="p-2.5 bg-slate-50 hover:bg-slate-100 rounded-lg transition-colors group/menu"
          @click.stop="toggleMenu"
        >
          <MoreVerticalIcon class="h-5 w-5 text-slate-600 group-hover/menu:text-slate-900" />
        </button>
      </div>
    </div>

    <!-- Stats Grid -->
    <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
      <div
        v-for="stat in stats"
        :key="stat.label"
        class="group/stat relative rounded-xl p-3 bg-gradient-to-br from-slate-50 to-slate-100/50 hover:from-indigo-50 hover:to-purple-50 transition-all duration-300 cursor-default border border-slate-100 hover:border-indigo-200"
        :title="stat.tooltip || undefined"
      >
        <p class="text-sm font-bold text-slate-900 mb-0.5 truncate group-hover/stat:text-indigo-600 transition-colors">
          {{ stat.value }}
        </p>
        <p class="text-xs text-slate-500 font-medium">{{ stat.label }}</p>
        
        <!-- Hover indicator -->
        <div class="absolute inset-0 rounded-xl ring-2 ring-indigo-400 opacity-0 group-hover/stat:opacity-20 transition-opacity pointer-events-none"></div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
// @ts-ignore - navigateTo is auto-imported in Nuxt 3
import { navigateTo } from '#app'
import { Bot, Settings, MoreVerticalIcon, Sparkles } from 'lucide-vue-next'

interface Stat {
  value: string
  label: string
  tooltip?: string
}

interface Props {
  title: string
  icon: string
  avatarColor: string
  borderColor: string
  type: string
  stats: Stat[]
  statsBgColor: string
  statsTextColor: string
  agentId?: string
  status?: 'published' | 'draft'
}

const props = withDefaults(defineProps<Props>(), {
  status: 'draft'
})

const navigateToAgent = () => {
  if (props.agentId) {
    navigateTo(`/agents/${props.agentId}`)
  }
}

const toggleMenu = () => {
  // Placeholder for menu toggle functionality
  console.log('Menu toggled')
}
</script>
