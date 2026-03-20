<template>
  <div class="w-full px-5 py-5 flex flex-col gap-5">
    <!-- Auth Status Banner -->
    <div v-if="!isAuthenticated" class="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <div class="flex items-center justify-between">
              <div class="flex items-center">
                <AlertCircle class="h-5 w-5 text-yellow-400 mr-3" />
                <div>
                  <h3 class="text-sm font-medium text-yellow-800">
                    Требуется аутентификация
                  </h3>
                  <p class="text-sm text-yellow-700 mt-1">
                    Зарегистрируйтесь или войдите в систему для доступа к пациентам
                  </p>
                </div>
              </div>
              <div class="flex gap-2">
                <button
                  @click="showAuthModal = true"
                  class="px-4 py-2 bg-yellow-600 text-white text-sm font-medium rounded-lg hover:bg-yellow-700 transition-colors"
                >
                  Войти
                </button>
              </div>
            </div>
          </div>


    <!-- Content Placeholder -->
    <div class="bg-background rounded-xl border border-border p-12 text-center">
      <div class="max-w-md mx-auto">
        <div class="w-16 h-16 bg-muted rounded-full flex items-center justify-center mx-auto mb-4">
          <Users class="h-8 w-8 text-muted-foreground" />
        </div>
        <h3 class="text-lg font-semibold text-foreground mb-2">
          Раздел в разработке
        </h3>
        <p class="text-muted-foreground text-sm">
          Функционал управления пациентами будет доступен в ближайшее время
        </p>
      </div>
    </div>

    <!-- Auth Modal -->
    <AuthModal
      :is-open="showAuthModal"
      @close="showAuthModal = false"
      @authenticated="handleAuthenticated"
    />
  </div>
</template>

<script setup lang="ts">
// @ts-ignore - definePageMeta is auto-imported in Nuxt 3
definePageMeta({
  middleware: 'auth'
})

import { ref, onMounted } from 'vue'
import { AlertCircle, PlusIcon, Users } from 'lucide-vue-next'
import { useAuth } from '../composables/useAuth'

// Layout state
const { pageTitle } = useLayoutState()

// Auth state
const { isAuthenticated } = useAuth()
const showAuthModal = ref(false)

// Set page title
onMounted(() => {
  pageTitle.value = 'Пациенты'
})

// Auth handler
const handleAuthenticated = () => {
  showAuthModal.value = false
}
</script>
