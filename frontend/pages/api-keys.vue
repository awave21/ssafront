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
                    Войдите в систему для управления API-ключами
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


    <!-- Create API Key Form -->
    <div v-if="showCreateForm" class="bg-background rounded-xl border border-border p-6">
      <div class="flex items-center justify-between mb-6">
        <h2 class="text-xl font-bold text-foreground">Создать новый API ключ</h2>
              <button
                @click="showCreateForm = false"
                class="p-2 text-slate-400 hover:text-slate-600 transition-colors"
              >
                <X class="h-5 w-5" />
              </button>
            </div>

            <form @submit.prevent="handleCreateApiKey" class="space-y-6">
              <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label class="block text-sm font-medium text-slate-700 mb-2">
                    Название ключа (опционально)
                  </label>
                  <input
                    v-model="createForm.name"
                    type="text"
                    class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    placeholder="Например: Ключ для разработки"
                  />
                </div>

                <div>
                  <label class="block text-sm font-medium text-slate-700 mb-2">
                    Срок действия (дни)
                  </label>
                  <input
                    v-model.number="createForm.expires_in_days"
                    type="number"
                    min="1"
                    max="365"
                    class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                    placeholder="365"
                  />
                </div>
              </div>

              <div>
                <label class="block text-sm font-medium text-slate-700 mb-3">
                  Разрешения (scopes)
                </label>
                <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <label
                    v-for="scope in availableScopes"
                    :key="scope.value"
                    class="flex items-center"
                  >
                    <input
                      v-model="createForm.scopes"
                      :value="scope.value"
                      type="checkbox"
                      class="h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-slate-300 rounded"
                    />
                    <span class="ml-2 text-sm text-slate-700">{{ scope.label }}</span>
                  </label>
                </div>
              </div>

              <div class="flex gap-3">
                <button
                  type="button"
                  @click="showCreateForm = false"
                  class="flex-1 px-4 py-2 text-slate-700 bg-slate-100 rounded-lg hover:bg-slate-200 transition-colors"
                >
                  Отмена
                </button>
                <button
                  type="submit"
                  :disabled="creatingApiKey"
                  class="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
                >
                  <Loader2 v-if="creatingApiKey" class="h-4 w-4 animate-spin" />
                  {{ creatingApiKey ? 'Создание...' : 'Создать ключ' }}
                </button>
              </div>
            </form>
          </div>

          <!-- API Keys List -->
          <div v-if="apiKeysLoading" class="flex justify-center py-12">
            <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
          </div>

          <div v-else-if="apiKeys.length === 0" class="text-center py-12">
            <Key class="h-12 w-12 text-slate-400 mx-auto mb-4" />
            <h3 class="text-lg font-medium text-slate-900 mb-2">Нет API ключей</h3>
            <p class="text-slate-600 mb-4">Создайте свой первый API ключ для доступа к системе</p>
            <button
              v-if="isAuthenticated"
              @click="showCreateForm = true"
              class="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
            >
              Создать ключ
            </button>
          </div>

          <div v-else class="space-y-4">
            <div
              v-for="apiKey in apiKeys"
              :key="apiKey.id"
              class="bg-white rounded-xl border border-slate-200 p-6"
            >
              <div class="flex items-start justify-between">
                <div class="flex-1">
                  <div class="flex items-center gap-3 mb-2">
                    <Key class="h-5 w-5 text-slate-600" />
                    <h3 class="text-lg font-semibold text-slate-900">
                      {{ apiKey.name || `Ключ ${apiKey.id.slice(-8)}` }}
                    </h3>
                    <span
                      :class="[
                        'px-2 py-1 text-xs font-medium rounded-full',
                        apiKey.revoked_at
                          ? 'bg-red-100 text-red-800'
                          : 'bg-green-100 text-green-800'
                      ]"
                    >
                      {{ apiKey.revoked_at ? 'Отозван' : 'Активен' }}
                    </span>
                  </div>

                  <div class="mb-3">
                    <p class="text-sm text-slate-600 mb-1">API Ключ:</p>
                    <code class="text-xs bg-slate-100 px-2 py-1 rounded font-mono break-all">
                      {{ apiKey.key }}
                    </code>
                  </div>

                  <div class="mb-3">
                    <p class="text-sm text-slate-600 mb-2">Разрешения:</p>
                    <div class="flex flex-wrap gap-1">
                      <span
                        v-for="scope in apiKey.scopes"
                        :key="scope"
                        class="px-2 py-1 bg-slate-100 text-slate-700 text-xs rounded-full"
                      >
                        {{ scope }}
                      </span>
                    </div>
                  </div>

                  <div class="text-xs text-slate-500">
                    Создан: {{ new Date(apiKey.created_at).toLocaleString('ru-RU') }}
                    <span v-if="apiKey.expires_at">
                      • Истекает: {{ new Date(apiKey.expires_at).toLocaleString('ru-RU') }}
                    </span>
                  </div>
                </div>

                <div class="flex flex-col gap-2 ml-4">
                  <button
                    v-if="!apiKey.revoked_at"
                    @click="revokeApiKey(apiKey.id)"
                    class="px-3 py-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors text-sm"
                  >
                    Отозвать
                  </button>
            </div>
          </div>
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

import { ref, onMounted, watch } from 'vue'
import {
  AlertCircle,
  PlusIcon,
  X,
  Loader2,
  Key
} from 'lucide-vue-next'
import { useAuth } from '../composables/useAuth'
import { useApiKeys } from '../composables/useApiKeys'

// Layout state
const { pageTitle } = useLayoutState()

// State
const showAuthModal = ref(false)
const showCreateForm = ref(false)
const creatingApiKey = ref(false)

// Composables
const { isAuthenticated } = useAuth()
const {
  apiKeys,
  fetchApiKeys,
  createApiKey,
  revokeApiKey,
  isLoading: apiKeysLoading,
  error: apiKeysError
} = useApiKeys()

// Form data
const createForm = ref({
  name: '',
  scopes: [] as string[],
  expires_in_days: 365
})

// Available scopes
const availableScopes = [
  { value: 'agents:read', label: 'Чтение агентов' },
  { value: 'agents:write', label: 'Создание агентов' },
  { value: 'tools:read', label: 'Чтение инструментов' },
  { value: 'tools:write', label: 'Создание инструментов' },
  { value: 'runs:read', label: 'Чтение запусков' },
  { value: 'runs:write', label: 'Запуск агентов' }
]

// Load API keys on mount
onMounted(async () => {
  pageTitle.value = 'API Ключи'
  
  if (isAuthenticated.value) {
    try {
      await fetchApiKeys()
    } catch (error) {
      console.error('Failed to load API keys:', error)
    }
  }
})

// Watch for authentication changes
watch(isAuthenticated, async (newAuth) => {
  if (newAuth) {
    await fetchApiKeys()
  }
})

// Handle API key creation
const handleCreateApiKey = async () => {
  try {
    creatingApiKey.value = true
    await createApiKey({
      name: createForm.value.name || undefined,
      scopes: createForm.value.scopes,
      expires_in_days: createForm.value.expires_in_days
    })

    // Reset form
    createForm.value = {
      name: '',
      scopes: [],
      expires_in_days: 365
    }
    showCreateForm.value = false
  } catch (error) {
    console.error('Error creating API key:', error)
  } finally {
    creatingApiKey.value = false
  }
}

// Handle API key revocation
const revokeApiKeyHandler = async (keyId: string) => {
  if (confirm('Вы уверены, что хотите отозвать этот API ключ?')) {
    try {
      await revokeApiKey(keyId)
    } catch (error) {
      console.error('Error revoking API key:', error)
    }
  }
}

// Handle authentication
const handleAuthenticated = () => {
  showAuthModal.value = false
}
</script>