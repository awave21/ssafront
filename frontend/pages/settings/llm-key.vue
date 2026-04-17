<template>
  <div class="w-full px-5 py-5 flex flex-col gap-5">
    <div v-if="!canManageApiKeys" class="bg-background rounded-xl border border-border p-8 text-center">
      <div class="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
        <ShieldAlert class="h-8 w-8 text-red-600" />
      </div>
      <h3 class="text-lg font-semibold text-foreground mb-2">Нет доступа</h3>
      <p class="text-sm text-muted-foreground">
        Управление API-ключами доступно только владельцам и администраторам.
      </p>
    </div>

    <template v-else>
      <div>
        <NuxtLink
          to="/settings"
          class="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft class="w-4 h-4" />
          Назад к настройкам
        </NuxtLink>
      </div>

      <div v-if="pageLoading" class="bg-background rounded-xl border border-border p-12 text-center">
        <Loader2 class="h-8 w-8 text-primary animate-spin mx-auto mb-4" />
        <p class="text-muted-foreground">Загрузка...</p>
      </div>

      <template v-else>
        <ProviderLlmKeyCard
          provider-id="openai"
          title="OpenAI"
          description="Ключ для эмбеддингов, поиска по базе знаний, каталога и моделей openai:* в агентах."
          :status="openaiStatus"
          v-model="openaiKeyInput"
          input-label="API-ключ OpenAI"
          placeholder="sk-proj-..."
          :is-saving="isSaving"
          :is-deleting="isDeletingKey"
          :deleting-for-this="deleteTarget === 'openai'"
          @save="saveOpenai"
          @request-delete="deleteTarget = 'openai'"
        />

        <ProviderLlmKeyCard
          provider-id="anthropic"
          title="Anthropic (Claude)"
          description="Ключ для моделей чата anthropic:* в агентах."
          :status="anthropicStatus"
          v-model="anthropicKeyInput"
          input-label="API-ключ Anthropic"
          placeholder="Вставьте ключ API Anthropic"
          :is-saving="isSaving"
          :is-deleting="isDeletingKey"
          :deleting-for-this="deleteTarget === 'anthropic'"
          @save="saveAnthropic"
          @request-delete="deleteTarget = 'anthropic'"
        />

        <div class="bg-muted/50 rounded-xl border border-border p-6">
          <h3 class="text-sm font-semibold text-foreground mb-2">Как это работает</h3>
          <ul class="text-sm text-muted-foreground space-y-1.5">
            <li>OpenAI нужен для эмбеддингов и инструментов поиска; без него диалог с агентом не запустится.</li>
            <li>Если в агенте выбрана модель Anthropic, дополнительно нужен ключ Anthropic.</li>
            <li>Ключи шифруются Fernet и никогда не возвращаются в API-ответах.</li>
          </ul>
        </div>
      </template>
    </template>

    <Dialog :open="deleteTarget !== null" @update:open="(v: boolean) => { if (!v) deleteTarget = null }">
      <DialogContent class="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Удалить API-ключ</DialogTitle>
          <DialogDescription>
            После удаления запросы к выбранному провайдеру с использованием организационного ключа будут недоступны до установки нового ключа.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter class="gap-2">
          <Button variant="ghost" :disabled="isDeletingKey" @click="deleteTarget = null">
            Отмена
          </Button>
          <Button variant="destructive" :disabled="isDeletingKey" @click="runDelete">
            <Loader2 v-if="isDeletingKey" class="w-4 h-4 mr-2 animate-spin" />
            Удалить ключ
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
definePageMeta({
  middleware: ['auth', 'settings-write'] as any,
})

import { ref, onMounted, watch } from 'vue'
import { ArrowLeft, ShieldAlert, Loader2 } from 'lucide-vue-next'
import { Button } from '~/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '~/components/ui/dialog'
import ProviderLlmKeyCard from '~/components/settings/ProviderLlmKeyCard.vue'
import { usePermissions } from '~/composables/usePermissions'
import { useTenantLlmConfig } from '~/composables/useTenantLlmConfig'
import { useApiFetch } from '~/composables/useApiFetch'
import { useToast } from '~/composables/useToast'
import type { TenantLLMConfigStatus } from '~/types/tenantLlmConfig'

const { pageTitle } = useLayoutState()
const { canManageApiKeys } = usePermissions()
const { saveKey, isSaving } = useTenantLlmConfig()
const apiFetch = useApiFetch()
const { success: toastOk, error: toastErr } = useToast()

const openaiStatus = ref<TenantLLMConfigStatus | null>(null)
const anthropicStatus = ref<TenantLLMConfigStatus | null>(null)
const openaiKeyInput = ref('')
const anthropicKeyInput = ref('')
const deleteTarget = ref<'openai' | 'anthropic' | null>(null)
const pageLoading = ref(true)
const isDeletingKey = ref(false)

const loadStatuses = async () => {
  const [o, a] = await Promise.all([
    apiFetch<TenantLLMConfigStatus>('/tenant-settings/llm-key', { query: { provider: 'openai' } }),
    apiFetch<TenantLLMConfigStatus>('/tenant-settings/llm-key', { query: { provider: 'anthropic' } }),
  ])
  openaiStatus.value = o
  anthropicStatus.value = a
}

onMounted(async () => {
  pageTitle.value = 'Ключи LLM'
  if (!canManageApiKeys.value) {
    pageLoading.value = false
    return
  }
  try {
    await loadStatuses()
  } catch {
    /* errors surfaced via composables */
  } finally {
    pageLoading.value = false
  }
})

watch(canManageApiKeys, async (val) => {
  if (val) {
    pageLoading.value = true
    try {
      await loadStatuses()
    } finally {
      pageLoading.value = false
    }
  }
})

const saveOpenai = async () => {
  const key = openaiKeyInput.value.trim()
  const result = await saveKey({ api_key: key, provider: 'openai' })
  if (result) {
    openaiKeyInput.value = ''
    await loadStatuses()
  }
}

const saveAnthropic = async () => {
  const key = anthropicKeyInput.value.trim()
  const result = await saveKey({ api_key: key, provider: 'anthropic' })
  if (result) {
    anthropicKeyInput.value = ''
    await loadStatuses()
  }
}

const runDelete = async () => {
  const p = deleteTarget.value
  if (!p) return
  isDeletingKey.value = true
  try {
    await apiFetch('/tenant-settings/llm-key', { method: 'DELETE', query: { provider: p } })
    toastOk('Ключ удалён', 'Запросы с этим провайдером будут недоступны до установки нового ключа')
    deleteTarget.value = null
    await loadStatuses()
  } catch (err: any) {
    if (err?.statusCode === 404) {
      deleteTarget.value = null
      await loadStatuses()
      return
    }
    toastErr('Ошибка удаления', err?.message || 'Не удалось удалить ключ')
  } finally {
    isDeletingKey.value = false
  }
}

</script>
