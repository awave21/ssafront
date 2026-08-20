<template>
  <AgentPageShell title="Настройки" :hide-actions="true">
    <AgentSettingsWorkspace v-if="newInterface" />
    <template v-else>
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
    </template>
  </AgentPageShell>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ShieldAlert } from 'lucide-vue-next'
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import AgentApiKeysPanel from '~/components/agents/AgentApiKeysPanel.vue'
import AgentSettingsWorkspace from '~/components/agents/settings/AgentSettingsWorkspace.vue'
import { useLayoutState } from '~/composables/useLayoutState'
import { usePermissions } from '~/composables/usePermissions'

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth'
})

const { canManageApiKeys } = usePermissions()
const { newInterface } = useLayoutState()
const route = useRoute()
const router = useRouter()

// В новом интерфейсе — редирект на /settings?section=apikeys, чтобы sub-nav
// сразу подсветил нужный пункт. В классическом виде остаёмся на /api-keys.
onMounted(() => {
  if (newInterface.value && !route.query.section) {
    router.replace({ path: route.path.replace(/\/api-keys$/, '/settings'), query: { section: 'apikeys' } })
  }
})
</script>
