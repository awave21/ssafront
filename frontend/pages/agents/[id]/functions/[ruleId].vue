<template>
  <FunctionEditorPage
    :agent-id="agentId"
    :rule-id="ruleId"
    @back="navigateBack"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import FunctionEditorPage from '~/components/agents/function-rules/FunctionEditorPage.vue'

const route = useRoute()
const router = useRouter()
const agentId = computed(() => (route.params.id as string) || '')
const ruleId = computed(() => (route.params.ruleId as string) || '')

const navigateBack = () => {
  router.push(`/agents/${agentId.value}/functions`)
}

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth',
})
</script>
