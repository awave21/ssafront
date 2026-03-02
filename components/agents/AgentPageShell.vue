<template>
  <div class="px-5 py-5 lg:h-full">
    <div class="flex flex-col lg:h-full">
      <!-- Auth Status Banner -->
    <div v-if="!isAuthenticated" class="mb-6 bg-yellow-50 border border-yellow-200 rounded-lg p-4">
      <div class="flex items-center justify-between">
        <div class="flex items-center">
          <AlertCircle class="h-5 w-5 text-yellow-400 mr-3" />
          <div>
            <h3 class="text-sm font-medium text-yellow-800">
              Требуется аутентификация
            </h3>
            <p class="text-sm text-yellow-700 mt-1">
              Войдите в систему для редактирования агента
            </p>
          </div>
        </div>
        <button
          @click="showAuthModal = true"
          class="px-4 py-2 bg-yellow-600 text-white text-sm font-medium rounded-lg hover:bg-yellow-700 transition-colors"
        >
          Войти
        </button>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="isLoading" class="flex justify-center py-12">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
    </div>

    <div v-else class="flex flex-col flex-1 min-h-0 gap-4">
      <slot />
    </div>

    <AuthModal
      :is-open="showAuthModal"
      @close="showAuthModal = false"
      @authenticated="handleAuthenticated"
    />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { navigateTo } from '#app'
import { storeToRefs } from 'pinia'
import { AlertCircle, Check, Loader2 } from 'lucide-vue-next'
import { useAuth } from '~/composables/useAuth'
import { usePermissions } from '~/composables/usePermissions'
import { useAgentEditorStore } from '~/composables/useAgentEditorStore'
import AuthModal from '~/components/AuthModal.vue'

type Props = {
  title: string
  hideActions?: boolean
}

const props = defineProps<Props>()

const showAuthModal = ref(false)
const route = useRoute()
const store = useAgentEditorStore()
const { agent, isLoading, isSaving } = storeToRefs(store)
const { isAuthenticated } = useAuth()
const { canEditAgents } = usePermissions()

// Sync breadcrumb data to layout via shared state
import { useLayoutState } from '~/composables/useLayoutState'
const { breadcrumbTitle, breadcrumbAgentName, hideTopBarActions } = useLayoutState()
breadcrumbTitle.value = props.title
hideTopBarActions.value = !!props.hideActions

watch(() => agent.value?.name, (name) => {
  breadcrumbAgentName.value = name || ''
}, { immediate: true })

onUnmounted(() => {
  breadcrumbTitle.value = ''
  breadcrumbAgentName.value = ''
  hideTopBarActions.value = false
})

const resolveAgentId = (value: string | string[] | undefined) =>
  Array.isArray(value) ? value[0] : value

watch(
  () => route.params.id,
  (id) => {
    const resolved = resolveAgentId(id as string | string[] | undefined)
    if (resolved) {
      store.ensureAgentLoaded(resolved)
    }
  },
  { immediate: true }
)

const handleSave = async () => {
  await store.saveAgent()
}

const handleCancel = () => {
  navigateTo('/agents')
}

const handleAuthenticated = () => {
  showAuthModal.value = false
  window.location.reload()
}
</script>
