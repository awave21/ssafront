<script setup lang="ts">
definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth'
})

import { useRoute } from 'vue-router'
import { navigateTo } from '#app'
import { usePermissions } from '~/composables/usePermissions'

const route = useRoute()
const { isManager } = usePermissions()

const rawId = route.params.id
const agentId = Array.isArray(rawId) ? rawId[0] : rawId
if (!agentId || typeof agentId !== 'string') {
  await navigateTo('/agents')
} else if (isManager.value) {
  await navigateTo({ path: '/dialogs', query: { agentId } })
} else {
  await navigateTo(`/agents/${agentId}/prompt`)
}
</script>

