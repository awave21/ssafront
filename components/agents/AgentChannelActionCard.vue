<template>
  <div
    class="p-4 border rounded-lg transition-all"
    :class="[
      connected
        ? 'border-indigo-100 bg-indigo-50/30'
        : 'border-slate-100 bg-white hover:border-slate-200'
    ]"
  >
    <div class="flex items-start justify-between gap-4">
      <div class="flex gap-4 min-w-0">
        <div class="w-12 h-12 rounded-md flex items-center justify-center" :class="iconClass">
          <component :is="icon" class="w-6 h-6 text-white" />
        </div>
        <div class="min-w-0">
          <h4 class="font-bold text-slate-900">{{ title }}</h4>
          <p class="text-sm text-slate-500 mt-1">{{ description }}</p>
          <div v-if="connected" class="mt-3 flex flex-wrap items-center gap-2">
            <span class="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-green-100 text-green-700">
              Подключен
            </span>
            <label
              v-if="showAuthorizationState"
              class="inline-flex items-center gap-2 px-2 py-0.5 rounded-full text-[10px] font-bold uppercase"
              :class="isAuthorized ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'"
            >
              <input
                type="checkbox"
                class="w-3 h-3 accent-emerald-600 cursor-not-allowed"
                :checked="Boolean(isAuthorized)"
                disabled
              >
              <span>{{ isAuthorized ? 'Авторизован' : 'Ожидает авторизацию' }}</span>
            </label>
          </div>
        </div>
      </div>

      <div v-if="canEdit" class="flex flex-col items-end gap-2">
        <button
          :disabled="loading"
          class="px-4 py-2 rounded-md text-sm font-bold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          :class="connected
            ? 'bg-red-50 text-red-600 hover:bg-red-100'
            : 'bg-slate-100 text-slate-600 hover:bg-slate-200'"
          @click="handleAction"
        >
          <span v-if="loading" class="inline-flex items-center gap-2">
            <Loader2 class="w-4 h-4 animate-spin" />
            {{ connected ? 'Отключение...' : 'Подключение...' }}
          </span>
          <span v-else>{{ connected ? disconnectLabel : connectLabel }}</span>
        </button>
        <button
          v-if="connected && showAuthorizeButton"
          :disabled="authorizeLoading"
          class="px-4 py-2 rounded-md text-sm font-bold bg-indigo-600 text-white hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          @click="handleAuthorize"
        >
          <span v-if="authorizeLoading" class="inline-flex items-center gap-2">
            <Loader2 class="w-4 h-4 animate-spin" />
            Запрос QR...
          </span>
          <span v-else>{{ authorizeLabel }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Component } from 'vue'
import { Loader2 } from 'lucide-vue-next'

const props = withDefaults(defineProps<{
  title: string
  description: string
  icon: Component
  iconClass: string
  connected: boolean
  loading?: boolean
  canEdit?: boolean
  connectLabel?: string
  disconnectLabel?: string
  showAuthorizeButton?: boolean
  authorizeLoading?: boolean
  authorizeLabel?: string
  showAuthorizationState?: boolean
  isAuthorized?: boolean
}>(), {
  loading: false,
  canEdit: true,
  connectLabel: 'Подключить',
  disconnectLabel: 'Отключить',
  showAuthorizeButton: false,
  authorizeLoading: false,
  authorizeLabel: 'Авторизоваться по QR',
  showAuthorizationState: false,
  isAuthorized: false
})

const emit = defineEmits<{
  (e: 'connect'): void
  (e: 'disconnect'): void
  (e: 'authorize'): void
}>()

const handleAction = () => {
  if (props.loading) return
  if (props.connected) {
    emit('disconnect')
    return
  }
  emit('connect')
}

const handleAuthorize = () => {
  if (props.authorizeLoading) return
  emit('authorize')
}
</script>
