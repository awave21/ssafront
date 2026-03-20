<template>
  <div 
    class="rounded-md border transition-all duration-300"
    :class="[
      status === 'active' || status === 'error'
        ? 'border-indigo-100 bg-indigo-50/30 p-6' 
        : 'border-border bg-background p-5 hover:border-slate-200'
    ]"
  >
    <div class="flex items-center justify-between gap-4">
      <div class="flex items-center gap-4">
        <div 
          class="w-10 h-10 rounded-md flex items-center justify-center flex-shrink-0"
          :class="[
            status === 'active' || status === 'error' ? 'bg-indigo-600 text-white' : 'bg-slate-50 text-slate-400 border border-border',
            status === 'soon' ? 'opacity-50' : ''
          ]"
        >
          <component :is="resolvedIcon" class="w-6 h-6" />
        </div>
        <div>
          <div class="flex items-center gap-2">
            <h4 class="font-bold text-slate-900">{{ title }}</h4>
            <span 
              v-if="statusLabel"
              class="text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded-full"
              :class="[
                status === 'error' ? 'bg-red-50 text-red-600' : (status === 'active' ? 'bg-emerald-50 text-emerald-600' : 'bg-slate-100 text-slate-400')
              ]"
            >
              {{ statusLabel }}
            </span>
          </div>
          <p class="text-xs text-slate-500 mt-0.5">
            {{ description }}
          </p>
        </div>
      </div>

      <div class="flex items-center gap-3">
        <button
          v-if="status === 'active' || status === 'error'"
          @click="$emit('sync')"
          :disabled="isSyncing"
          class="flex items-center gap-2 px-3 py-1.5 bg-slate-50 text-slate-700 border border-slate-200 rounded-md text-xs font-medium hover:bg-slate-100 transition-all disabled:opacity-50"
          title="Обновить данные из CRM"
        >
          <RefreshCw class="h-3.5 w-3.5" :class="{ 'animate-spin': isSyncing }" />
          <span>{{ isSyncing ? 'Обновление...' : 'Обновить' }}</span>
        </button>

        <button
          v-if="status === 'inactive'"
          @click="$emit('enable')"
          class="px-4 py-1.5 bg-indigo-600 text-white rounded-md text-sm font-medium hover:bg-indigo-700 transition-all"
        >
          Подключить
        </button>
        <button
          v-else-if="status === 'active' || status === 'error'"
          @click="$emit('disable')"
          class="px-4 py-1.5 bg-white border border-red-200 text-red-600 rounded-md text-sm font-medium hover:bg-red-50 transition-all"
        >
          Отключить
        </button>
        <span 
          v-else-if="status === 'soon'"
          class="px-4 py-1.5 bg-slate-50 text-slate-400 rounded-md text-xs font-medium border border-border cursor-default"
        >
          В разработке
        </span>
      </div>
    </div>

    <!-- Warning Alert -->
    <div v-if="warning" class="mt-4 bg-yellow-50 border border-yellow-200 rounded-lg p-3 flex items-start gap-3">
      <AlertTriangle class="h-4 w-4 text-yellow-500 flex-shrink-0 mt-0.5" />
      <div class="flex-1">
        <p class="text-[11px] text-yellow-800 font-bold uppercase tracking-wider">Внимание</p>
        <p class="text-xs text-yellow-700 mt-0.5 leading-relaxed">{{ warning }}</p>
      </div>
    </div>

    <!-- Info Grid for Active/Error State -->
    <div v-if="(status === 'active' || status === 'error') && (host || lastSync || error)" class="mt-6 pt-6 border-t border-indigo-100/50 space-y-4">
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div v-if="host" class="bg-white/50 rounded-md p-3 border border-indigo-100/30">
          <p class="text-[10px] uppercase tracking-widest text-slate-400 font-bold">Host</p>
          <p class="text-xs text-slate-700 mt-1 font-medium truncate">{{ host }}</p>
        </div>
        <div v-if="lastSync" class="bg-white/50 rounded-md p-3 border border-indigo-100/30">
          <p class="text-[10px] uppercase tracking-widest text-slate-400 font-bold">Синхронизация</p>
          <p class="text-xs text-slate-700 mt-1 font-medium">{{ lastSync }}</p>
        </div>
      </div>
      
      <!-- Slot for additional content (like tools list) -->
      <slot name="extra"></slot>

      <p class="text-[10px] text-slate-400 leading-relaxed italic">
        Безопасное соединение активно. Ключ хранится на сервере. Все запросы используют Bearer-авторизацию.
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, toRefs } from 'vue'
import type { Component } from 'vue'
import { Link, RefreshCw, AlertTriangle } from 'lucide-vue-next'

interface Props {
  title: string
  description: string
  status: 'active' | 'inactive' | 'soon' | 'error'
  icon?: Component
  statusLabel?: string
  host?: string
  lastSync?: string
  error?: string
  warning?: string | null
  isSyncing?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  icon: () => Link,
  isSyncing: false
})

const { title, description, status, icon, statusLabel, host, lastSync, error, warning, isSyncing } = toRefs(props)

const resolvedIcon = computed(() => icon.value || Link)

defineEmits<{
  (e: 'enable'): void
  (e: 'disable'): void
  (e: 'sync'): void
}>()
</script>
