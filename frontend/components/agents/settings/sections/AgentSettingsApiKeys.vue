<template>
  <div class="flex flex-col gap-5">
    <div class="flex items-center justify-between gap-3 border-b border-slate-100 pb-4">
      <div class="flex items-center gap-2.5">
        <div class="flex h-8 w-8 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <KeyRound class="h-4 w-4" />
        </div>
        <h1 class="text-lg font-semibold text-slate-900">API-ключи</h1>
      </div>
    </div>

    <template v-if="canManageApiKeys">
      <AgentApiKeysPanel />
    </template>
    <div
      v-else
      class="rounded-2xl border border-dashed border-slate-200 bg-slate-100 p-8 text-center"
    >
      <div class="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-slate-400 shadow-[0_2px_8px_-4px_rgba(0,0,0,0.06)]">
        <ShieldAlert class="h-5 w-5" />
      </div>
      <div class="mb-1 text-sm font-semibold text-slate-700">Нет доступа</div>
      <p class="mx-auto max-w-md text-xs leading-relaxed text-slate-500">
        Управление API-ключами доступно только владельцам и администраторам.
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { KeyRound, ShieldAlert } from 'lucide-vue-next'
import AgentApiKeysPanel from '~/components/agents/AgentApiKeysPanel.vue'
import { usePermissions } from '~/composables/usePermissions'

const { canManageApiKeys } = usePermissions()
</script>
