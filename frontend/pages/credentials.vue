<template>
  <div class="w-full px-5 py-5 flex flex-col gap-5">
    <!-- Auth Status Banner -->
    <div v-if="!isAuthenticated" class="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
      <div class="flex items-center justify-between">
        <div class="flex items-center">
          <AlertCircle class="h-5 w-5 text-yellow-400 mr-3" />
          <div>
            <h3 class="text-sm font-medium text-yellow-800">Требуется аутентификация</h3>
            <p class="text-sm text-yellow-700 mt-1">Войдите в систему для управления учётными данными</p>
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

    <!-- Header with Create Button -->
    <div v-if="isAuthenticated && !showForm" class="flex items-center justify-between">
      <p class="text-sm text-muted-foreground">Управление учётными данными для API-интеграций ваших инструментов</p>
      <button
        @click="openCreateForm"
        class="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors flex items-center gap-2"
      >
        <Plus class="h-4 w-4" />
        Добавить
      </button>
    </div>

    <!-- Create / Edit Form -->
    <div v-if="showForm" class="bg-background rounded-xl border border-border p-6">
      <div class="flex items-center justify-between mb-6">
        <h2 class="text-xl font-bold text-foreground">
          {{ editingId ? 'Редактировать учётные данные' : 'Новые учётные данные' }}
        </h2>
        <button @click="closeForm" class="p-2 text-slate-400 hover:text-slate-600 transition-colors">
          <X class="h-5 w-5" />
        </button>
      </div>

      <form @submit.prevent="handleSubmit" class="space-y-5">
        <!-- Name -->
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1.5">Название</label>
          <input
            v-model="form.name"
            type="text"
            required
            class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
            placeholder="Напр: Supabase ChatMedBot"
          />
        </div>

        <!-- Auth Type -->
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1.5">Тип авторизации</label>
          <select
            v-model="form.auth_type"
            @change="onAuthTypeChange"
            class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm"
          >
            <option v-for="(label, key) in AUTH_TYPES" :key="key" :value="key">{{ label }}</option>
          </select>
        </div>

        <!-- Dynamic Config Fields -->
        <div v-if="configFields.length > 0" class="space-y-4">
          <div class="text-xs font-semibold text-slate-500 uppercase tracking-wide">Параметры</div>
          <div v-for="field in configFields" :key="field" class="space-y-1.5">
            <label class="block text-sm font-medium text-slate-700">
              {{ configLabels[field] || field }}
            </label>
            <div class="relative">
              <input
                v-model="(form.config as any)[field]"
                :type="isSecretField(field) && !showSecrets[field] ? 'password' : 'text'"
                :placeholder="configPlaceholders[field] || ''"
                class="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-sm font-mono pr-10"
              />
              <button
                v-if="isSecretField(field)"
                type="button"
                @click="showSecrets[field] = !showSecrets[field]"
                class="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
              >
                <EyeOff v-if="showSecrets[field]" class="h-4 w-4" />
                <Eye v-else class="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>

        <!-- Actions -->
        <div class="flex gap-3 pt-2">
          <button
            type="button"
            @click="closeForm"
            class="flex-1 px-4 py-2 text-slate-700 bg-slate-100 rounded-lg hover:bg-slate-200 transition-colors text-sm"
          >
            Отмена
          </button>
          <button
            type="submit"
            :disabled="isSaving || !isFormValid"
            class="flex-1 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2 text-sm"
          >
            <Loader2 v-if="isSaving" class="h-4 w-4 animate-spin" />
            {{ isSaving ? 'Сохранение...' : (editingId ? 'Сохранить' : 'Создать') }}
          </button>
        </div>
      </form>
    </div>

    <!-- Loading -->
    <div v-if="isLoading && !showForm" class="flex justify-center py-12">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
    </div>

    <!-- Empty State -->
    <div v-else-if="credentials.length === 0 && !showForm" class="text-center py-12">
      <Shield class="h-12 w-12 text-slate-400 mx-auto mb-4" />
      <h3 class="text-lg font-medium text-slate-900 mb-2">Нет учётных данных</h3>
      <p class="text-slate-600 mb-4">Создайте учётные данные для безопасного подключения инструментов к API</p>
      <button
        v-if="isAuthenticated"
        @click="openCreateForm"
        class="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors text-sm"
      >
        Создать учётные данные
      </button>
    </div>

    <!-- Credentials List -->
    <div v-else-if="!showForm" class="space-y-3">
      <div
        v-for="cred in credentials"
        :key="cred.id"
        class="bg-background rounded-xl border border-border p-5 hover:border-slate-300 transition-colors"
      >
        <div class="flex items-start justify-between">
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-3 mb-2">
              <Shield class="h-5 w-5 text-indigo-500 shrink-0" />
              <h3 class="text-base font-semibold text-slate-900 truncate">{{ cred.name }}</h3>
              <span class="px-2 py-0.5 text-xs font-medium rounded-full bg-indigo-50 text-indigo-700 shrink-0">
                {{ AUTH_TYPES[cred.auth_type] || cred.auth_type }}
              </span>
            </div>

            <div class="flex items-center gap-4 text-xs text-slate-500">
              <span class="font-mono bg-slate-50 px-2 py-0.5 rounded">ID: {{ cred.id.slice(0, 8) }}...</span>
              <span v-if="cred.created_at">
                Создан: {{ new Date(cred.created_at).toLocaleDateString('ru-RU') }}
              </span>
            </div>
          </div>

          <div class="flex items-center gap-1 ml-4 shrink-0">
            <button
              @click="handleTest(cred.id)"
              :disabled="testingId === cred.id"
              class="p-2 text-slate-400 hover:text-emerald-600 hover:bg-emerald-50 rounded-lg transition-colors"
              title="Тестировать"
            >
              <Loader2 v-if="testingId === cred.id" class="h-4 w-4 animate-spin" />
              <Play v-else class="h-4 w-4" />
            </button>
            <button
              @click="openEditForm(cred)"
              class="p-2 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
              title="Редактировать"
            >
              <Pencil class="h-4 w-4" />
            </button>
            <button
              @click="handleDelete(cred.id, cred.name)"
              class="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
              title="Удалить"
            >
              <Trash2 class="h-4 w-4" />
            </button>
          </div>
        </div>

        <!-- Test Result Inline -->
        <div v-if="testResults[cred.id]" class="mt-3 text-xs rounded-lg p-3" :class="testResults[cred.id].success ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'">
          <span class="font-medium">{{ testResults[cred.id].success ? 'OK' : 'Ошибка' }}</span>
          <span v-if="testResults[cred.id].status_code"> &mdash; {{ testResults[cred.id].status_code }}</span>
          <span v-if="testResults[cred.id].message"> &mdash; {{ testResults[cred.id].message }}</span>
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
  middleware: ['auth', 'credentials-write'] as any,
})

import { ref, computed, onMounted, watch } from 'vue'
import {
  AlertCircle,
  Plus,
  X,
  Loader2,
  Shield,
  Eye,
  EyeOff,
  Pencil,
  Trash2,
  Play,
} from 'lucide-vue-next'
import { useAuth } from '~/composables/useAuth'
import { useCredentials } from '~/composables/useCredentials'
import { useToast } from '~/composables/useToast'
import {
  AUTH_TYPES,
  getConfigFieldsForAuthType,
  getConfigFieldLabels,
  getConfigFieldPlaceholders,
  getSecretFields,
  createEmptyConfig,
  type CredentialAuthType,
  type Credential,
  type CredentialTestResult,
} from '~/types/credential'

const { pageTitle } = useLayoutState()
const { isAuthenticated } = useAuth()
const {
  credentials,
  isLoading,
  fetchCredentials,
  createCredential,
  updateCredential,
  deleteCredential,
  testCredential,
} = useCredentials()
const { success: toastSuccess, error: toastError } = useToast()

const showAuthModal = ref(false)
const showForm = ref(false)
const editingId = ref<string | null>(null)
const isSaving = ref(false)
const testingId = ref<string | null>(null)
const testResults = ref<Record<string, CredentialTestResult>>({})
const showSecrets = ref<Record<string, boolean>>({})

const form = ref({
  name: '',
  auth_type: 'api_key' as CredentialAuthType,
  config: createEmptyConfig('api_key') as Record<string, string>,
})

const configFields = computed(() => getConfigFieldsForAuthType(form.value.auth_type))
const configLabels = computed(() => getConfigFieldLabels(form.value.auth_type))
const configPlaceholders = computed(() => getConfigFieldPlaceholders(form.value.auth_type))
const secretFields = computed(() => getSecretFields(form.value.auth_type))

const isSecretField = (field: string) => secretFields.value.has(field)

const isFormValid = computed(() => {
  if (!form.value.name.trim()) return false
  if (form.value.auth_type === 'none') return true
  return configFields.value.every((f) => (form.value.config as any)[f]?.trim())
})

const onAuthTypeChange = () => {
  form.value.config = createEmptyConfig(form.value.auth_type) as Record<string, string>
  showSecrets.value = {}
}

const openCreateForm = () => {
  editingId.value = null
  form.value = {
    name: '',
    auth_type: 'api_key',
    config: createEmptyConfig('api_key') as Record<string, string>,
  }
  showSecrets.value = {}
  showForm.value = true
}

const openEditForm = (cred: Credential) => {
  editingId.value = cred.id
  form.value = {
    name: cred.name,
    auth_type: cred.auth_type,
    config: { ...(cred.config as Record<string, string>) },
  }
  showSecrets.value = {}
  showForm.value = true
}

const closeForm = () => {
  showForm.value = false
  editingId.value = null
}

const handleSubmit = async () => {
  try {
    isSaving.value = true
    const payload = {
      name: form.value.name,
      auth_type: form.value.auth_type,
      config: form.value.auth_type === 'none' ? {} : form.value.config,
    }

    if (editingId.value) {
      await updateCredential(editingId.value, payload)
      toastSuccess('Сохранено', 'Учётные данные обновлены')
    } else {
      await createCredential(payload)
      toastSuccess('Создано', 'Учётные данные добавлены')
    }

    closeForm()
  } catch (err: any) {
    toastError('Ошибка', err.message || 'Не удалось сохранить')
  } finally {
    isSaving.value = false
  }
}

const handleDelete = async (id: string, name: string) => {
  if (!confirm(`Удалить учётные данные "${name}"?`)) return
  try {
    await deleteCredential(id)
    toastSuccess('Удалено', `Учётные данные "${name}" удалены`)
  } catch (err: any) {
    toastError('Ошибка удаления', err.message || 'Не удалось удалить')
  }
}

const handleTest = async (id: string) => {
  try {
    testingId.value = id
    const result = await testCredential(id)
    testResults.value[id] = result
  } catch (err: any) {
    testResults.value[id] = { success: false, message: err.message || 'Тест не пройден' }
  } finally {
    testingId.value = null
  }
}

const handleAuthenticated = () => {
  showAuthModal.value = false
}

onMounted(async () => {
  pageTitle.value = 'Учётные данные'
  if (isAuthenticated.value) {
    try {
      await fetchCredentials()
    } catch (err) {
      console.error('Failed to load credentials:', err)
    }
  }
})

watch(isAuthenticated, async (newAuth) => {
  if (newAuth) await fetchCredentials()
})
</script>
