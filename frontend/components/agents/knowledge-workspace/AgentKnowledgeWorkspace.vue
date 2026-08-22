<template>
  <div class="flex flex-col gap-6 lg:flex-row lg:items-start">
    <div v-if="agentId" class="lg:sticky lg:top-4">
      <AgentKnowledgeSubNav
        :agent-id="agentId"
        :counts="counts"
        :show-sqns="showSqns"
      />
    </div>

    <div class="min-w-0 flex-1">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AgentKnowledgeSubNav from './AgentKnowledgeSubNav.vue'
import { useLayoutState } from '~/composables/useLayoutState'

const props = defineProps<{
  counts?: {
    directQuestions?: number
    directories?: number
    tables?: number
    sqns?: number
  }
  showSqns?: boolean
}>()

const route = useRoute()
const agentId = computed(() => {
  const id = route.params.id
  return Array.isArray(id) ? id[0] : id
})
</script>
