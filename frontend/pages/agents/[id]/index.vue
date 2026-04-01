<script setup lang="ts">
definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth'
})

import { useRoute } from 'vue-router'
import { navigateTo } from '#app'

const route = useRoute()

const rawId = route.params.id
const agentId = Array.isArray(rawId) ? rawId[0] : rawId
if (!agentId || typeof agentId !== 'string') {
  await navigateTo('/agents')
} else {
  await navigateTo({ path: '/dialogs', query: { agentId } })
}
</script>

