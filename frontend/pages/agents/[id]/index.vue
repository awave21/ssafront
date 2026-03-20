<script setup lang="ts">
definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth'
})

import { useRoute } from 'vue-router'
import { navigateTo } from '#app'

const route = useRoute()
navigateTo(`/agents/${route.params.id}/prompt`)
</script>

