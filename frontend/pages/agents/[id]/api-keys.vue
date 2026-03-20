<template>
  <AgentPageShell title="API-ключи" :hide-actions="true">
    <template v-if="canManageApiKeys">
      <AgentApiKeysPanel />
    </template>
    <div v-else class="bg-background rounded-md border border-border p-6 text-center">
      <ShieldAlert class="h-10 w-10 text-slate-300 mx-auto mb-3" />
      <h4 class="text-base font-medium text-slate-900 mb-1">Нет доступа</h4>
      <p class="text-sm text-slate-500">
        Управление API-ключами доступно только владельцам и администраторам.
      </p>
    </div>
  </AgentPageShell>
</template>

<script setup lang="ts">
import { ShieldAlert } from 'lucide-vue-next'
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import AgentApiKeysPanel from '~/components/agents/AgentApiKeysPanel.vue'
import { usePermissions } from '~/composables/usePermissions'

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth'
})

const { canManageApiKeys } = usePermissions()
</script>
