<template>
  <div class="bg-background rounded-md border border-border p-4 sm:p-5 space-y-5">
    <div class="flex items-start justify-between">
      <div>
        <h3 class="text-lg font-bold text-slate-900">API-ключи</h3>
        <p class="text-sm text-slate-500 mt-1">
          Ключи для интеграции с внешними системами через API.
        </p>
      </div>
      <Button size="sm" @click="showCreateDialog = true">
        <Plus class="h-4 w-4" />
        Создать ключ
      </Button>
    </div>

    <!-- Show revoked toggle -->
    <div class="flex items-center gap-2">
      <Switch :model-value="showRevoked" @update:model-value="handleToggleRevoked" />
      <span class="text-sm text-slate-500">Показать отозванные</span>
    </div>

    <!-- Loading -->
    <div v-if="isLoading" class="flex justify-center py-12">
      <Loader2 class="h-8 w-8 animate-spin text-indigo-600" />
    </div>

    <!-- Empty state -->
    <div v-else-if="keys.length === 0" class="text-center py-12">
      <KeyRound class="h-12 w-12 text-slate-300 mx-auto mb-4" />
      <h4 class="text-base font-medium text-slate-900 mb-1">Нет API-ключей</h4>
      <p class="text-sm text-slate-500 mb-4">Создайте первый ключ для интеграции с внешними системами</p>
      <Button @click="showCreateDialog = true">
        <Plus class="h-4 w-4" />
        Создать ключ
      </Button>
    </div>

    <!-- Keys list -->
    <div v-else class="space-y-3">
      <div
        v-for="key in keys"
        :key="key.id"
        class="border rounded-lg p-4 transition-colors"
        :class="keyCardClass(key)"
      >
        <div class="flex items-start justify-between gap-4">
          <div class="flex-1 min-w-0">
            <!-- Name + masked key + badge -->
            <div class="flex items-center gap-2 flex-wrap">
              <span class="font-medium text-slate-900 truncate">{{ key.name }}</span>
              <code class="text-xs bg-slate-100 text-slate-500 px-1.5 py-0.5 rounded font-mono">
                sk-&#8226;&#8226;&#8226;&#8226;{{ key.last4 }}
              </code>
              <Badge :variant="statusBadgeVariant(key)" class="text-[10px]">
                {{ statusLabel(key) }}
              </Badge>
            </div>

            <!-- Stats row -->
            <div class="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-slate-500">
              <span>Вызовов: <strong class="text-slate-700">{{ key.total_calls.toLocaleString('ru-RU') }}</strong></span>
              <span>
                Лимит:
                <strong class="text-slate-700">{{ key.daily_limit ? `${key.daily_limit.toLocaleString('ru-RU')}/день` : 'без лимита' }}</strong>
              </span>
              <span>
                Срок:
                <strong class="text-slate-700">{{ expiryLabel(key) }}</strong>
              </span>
              <span v-if="key.last_used_at">
                Использован: <strong class="text-slate-700">{{ relativeTime(key.last_used_at) }}</strong>
              </span>
              <span v-else class="italic">Не использовался</span>
              <span>Создан: {{ formatDate(key.created_at) }}</span>
            </div>
          </div>

          <!-- Actions -->
          <div v-if="getApiKeyStatus(key) === 'active'" class="flex items-center gap-1 shrink-0">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger as-child>
                  <Button variant="ghost" size="icon-sm" @click="openEdit(key)">
                    <Pencil class="h-3.5 w-3.5" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Редактировать</TooltipContent>
              </Tooltip>
            </TooltipProvider>
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger as-child>
                  <Button variant="ghost" size="icon-sm" class="text-red-500 hover:text-red-600 hover:bg-red-50" @click="openRevoke(key)">
                    <Ban class="h-3.5 w-3.5" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Отозвать</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>

          <!-- Expired keys can also be revoked -->
          <div v-else-if="getApiKeyStatus(key) === 'expired'" class="flex items-center gap-1 shrink-0">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger as-child>
                  <Button variant="ghost" size="icon-sm" @click="openEdit(key)">
                    <Pencil class="h-3.5 w-3.5" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Продлить</TooltipContent>
              </Tooltip>
            </TooltipProvider>
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger as-child>
                  <Button variant="ghost" size="icon-sm" class="text-red-500 hover:text-red-600 hover:bg-red-50" @click="openRevoke(key)">
                    <Ban class="h-3.5 w-3.5" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>Отозвать</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </div>
      </div>
    </div>

    <!-- Dialogs -->
    <ApiKeyCreateDialog
      :open="showCreateDialog"
      :agent-id="agentId"
      :is-submitting="isCreating"
      @update:open="showCreateDialog = $event"
      @submit="handleCreate"
    />

    <ApiKeySecretDialog
      :open="showSecretDialog"
      :api-key="createdSecret"
      @update:open="showSecretDialog = $event"
      @done="handleSecretDone"
    />

    <ApiKeyEditDialog
      :open="showEditDialog"
      :api-key="editingKey"
      :is-submitting="isEditing"
      @update:open="showEditDialog = $event"
      @submit="handleEdit"
    />

    <ApiKeyRevokeDialog
      :open="showRevokeDialog"
      :api-key="revokingKey"
      :is-submitting="isRevoking"
      @update:open="showRevokeDialog = $event"
      @confirm="handleRevoke"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Plus, Loader2, KeyRound, Pencil, Ban } from 'lucide-vue-next'
import { storeToRefs } from 'pinia'
import { Button } from '~/components/ui/button'
import { Badge } from '~/components/ui/badge'
import Switch from '~/components/ui/switch/Switch.vue'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '~/components/ui/tooltip'
import { useAgentEditorStore } from '~/composables/useAgentEditorStore'
import { useAgentApiKeys } from '~/composables/useAgentApiKeys'
import { getApiKeyStatus } from '~/types/apiKey'
import type { ApiKey, ApiKeyCreated } from '~/types/apiKey'
import ApiKeyCreateDialog from '~/components/agents/api-keys/ApiKeyCreateDialog.vue'
import ApiKeySecretDialog from '~/components/agents/api-keys/ApiKeySecretDialog.vue'
import ApiKeyEditDialog from '~/components/agents/api-keys/ApiKeyEditDialog.vue'
import ApiKeyRevokeDialog from '~/components/agents/api-keys/ApiKeyRevokeDialog.vue'

const store = useAgentEditorStore()
const { agent } = storeToRefs(store)
const { keys, isLoading, fetchKeys, createKey, updateKey, revokeKey } = useAgentApiKeys()

const agentId = computed(() => agent.value?.id ?? '')

const showRevoked = ref(false)
const showCreateDialog = ref(false)
const showSecretDialog = ref(false)
const showEditDialog = ref(false)
const showRevokeDialog = ref(false)

const isCreating = ref(false)
const isEditing = ref(false)
const isRevoking = ref(false)

const createdSecret = ref('')
const editingKey = ref<ApiKey | null>(null)
const revokingKey = ref<ApiKey | null>(null)

watch(agent, async (val) => {
  if (val?.id) {
    await fetchKeys(val.id, showRevoked.value)
  }
}, { immediate: true })

const handleToggleRevoked = async (val: boolean) => {
  showRevoked.value = val
  if (agentId.value) {
    await fetchKeys(agentId.value, val)
  }
}

const handleCreate = async (payload: { name: string; expires_in_days?: number | null; daily_limit?: number | null }) => {
  if (!agentId.value) return
  isCreating.value = true
  try {
    const created: ApiKeyCreated = await createKey({
      name: payload.name,
      agent_id: agentId.value,
      expires_in_days: payload.expires_in_days,
      daily_limit: payload.daily_limit
    })
    showCreateDialog.value = false
    createdSecret.value = created.api_key
    showSecretDialog.value = true
  } catch { /* handled in composable */ } finally {
    isCreating.value = false
  }
}

const handleSecretDone = async () => {
  createdSecret.value = ''
  if (agentId.value) {
    await fetchKeys(agentId.value, showRevoked.value)
  }
}

const openEdit = (key: ApiKey) => {
  editingKey.value = key
  showEditDialog.value = true
}

const handleEdit = async (payload: { name?: string; daily_limit?: number | null; expires_in_days?: number | null }) => {
  if (!editingKey.value) return
  isEditing.value = true
  try {
    await updateKey(editingKey.value.id, payload)
    showEditDialog.value = false
    editingKey.value = null
  } catch { /* handled in composable */ } finally {
    isEditing.value = false
  }
}

const openRevoke = (key: ApiKey) => {
  revokingKey.value = key
  showRevokeDialog.value = true
}

const handleRevoke = async () => {
  if (!revokingKey.value) return
  isRevoking.value = true
  try {
    await revokeKey(revokingKey.value.id)
    showRevokeDialog.value = false
    revokingKey.value = null
  } catch { /* handled in composable */ } finally {
    isRevoking.value = false
  }
}

// Helpers
const statusLabel = (key: ApiKey) => {
  const s = getApiKeyStatus(key)
  if (s === 'active') return 'Активен'
  if (s === 'expired') return 'Истёк'
  return 'Отозван'
}

const statusBadgeVariant = (key: ApiKey) => {
  const s = getApiKeyStatus(key)
  if (s === 'active') return 'success' as const
  if (s === 'expired') return 'secondary' as const
  return 'destructive' as const
}

const keyCardClass = (key: ApiKey) => {
  const s = getApiKeyStatus(key)
  if (s === 'active') return 'border-slate-200 bg-white'
  if (s === 'expired') return 'border-amber-200 bg-amber-50/30'
  return 'border-red-100 bg-red-50/20 opacity-60'
}

const expiryLabel = (key: ApiKey) => {
  if (!key.expires_at) return 'бессрочный'
  const exp = new Date(key.expires_at)
  const now = new Date()
  const diffMs = exp.getTime() - now.getTime()
  if (diffMs <= 0) return `истёк ${formatDate(key.expires_at)}`
  const days = Math.ceil(diffMs / (1000 * 60 * 60 * 24))
  return `${formatDate(key.expires_at)} (${days} дн.)`
}

const formatDate = (iso: string) =>
  new Date(iso).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' })

const relativeTime = (iso: string) => {
  const diff = Date.now() - new Date(iso).getTime()
  const sec = Math.floor(diff / 1000)
  if (sec < 60) return 'только что'
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min} мин. назад`
  const hours = Math.floor(min / 60)
  if (hours < 24) return `${hours} ч. назад`
  const days = Math.floor(hours / 24)
  if (days === 1) return 'вчера'
  if (days < 30) return `${days} дн. назад`
  return formatDate(iso)
}
</script>
