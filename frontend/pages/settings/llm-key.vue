<template>
  <div class="w-full px-5 py-5 flex flex-col gap-5">
    <!-- Permission Check -->
    <div v-if="!canManageApiKeys" class="bg-background rounded-xl border border-border p-8 text-center">
      <div class="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
        <ShieldAlert class="h-8 w-8 text-red-600" />
      </div>
      <h3 class="text-lg font-semibold text-foreground mb-2">Нет доступа</h3>
      <p class="text-muted-foreground text-sm">
        Управление API-ключами доступно только владельцам и администраторам.
      </p>
    </div>

    <!-- Content -->
    <template v-else>
      <!-- Back link -->
      <div>
        <NuxtLink
          to="/settings"
          class="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft class="w-4 h-4" />
          Назад к настройкам
        </NuxtLink>
      </div>

      <!-- Loading -->
      <div v-if="isLoading" class="bg-background rounded-xl border border-border p-12 text-center">
        <Loader2 class="h-8 w-8 text-primary animate-spin mx-auto mb-4" />
        <p class="text-muted-foreground">Загрузка...</p>
      </div>

      <template v-else>
        <!-- Current Status Card -->
        <div class="bg-background rounded-xl border border-border overflow-hidden">
          <div class="px-6 py-4 border-b border-border">
            <h2 class="text-base font-semibold text-foreground">Статус API-ключа OpenAI</h2>
            <p class="text-sm text-muted-foreground mt-0.5">
              Собственный ключ используется вместо системного для генерации ответов
            </p>
          </div>
          <div class="px-6 py-5">
            <div v-if="keyStatus?.has_key" class="flex items-center justify-between">
              <div class="flex items-center gap-3">
                <div class="w-10 h-10 rounded-lg flex items-center justify-center"
                  :class="keyStatus.is_active ? 'bg-emerald-100' : 'bg-amber-100'">
                  <KeyRound class="w-5 h-5"
                    :class="keyStatus.is_active ? 'text-emerald-600' : 'text-amber-600'" />
                </div>
                <div>
                  <div class="flex items-center gap-2">
                    <span class="text-sm font-medium text-foreground">sk-••••{{ keyStatus.last4 }}</span>
                    <span
                      class="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded"
                      :class="keyStatus.is_active
                        ? 'bg-emerald-100 text-emerald-700'
                        : 'bg-amber-100 text-amber-700'"
                    >
                      {{ keyStatus.is_active ? 'Активен' : 'Неактивен' }}
                    </span>
                  </div>
                  <p class="text-xs text-muted-foreground mt-0.5">
                    Провайдер: {{ keyStatus.provider }}
                  </p>
                </div>
              </div>
              <Button
                variant="destructive"
                size="sm"
                :disabled="isDeleting"
                @click="showDeleteDialog = true"
              >
                <Loader2 v-if="isDeleting" class="w-4 h-4 mr-1.5 animate-spin" />
                <Trash2 v-else class="w-4 h-4 mr-1.5" />
                Удалить
              </Button>
            </div>

            <div v-else class="flex items-center gap-3">
              <div class="w-10 h-10 bg-muted rounded-lg flex items-center justify-center">
                <KeyRound class="w-5 h-5 text-muted-foreground" />
              </div>
              <div>
                <p class="text-sm font-medium text-foreground">Ключ не установлен</p>
                <p class="text-xs text-muted-foreground">Без ключа запросы к OpenAI недоступны</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Set / Update Key Form -->
        <div class="bg-background rounded-xl border border-border overflow-hidden">
          <div class="px-6 py-4 border-b border-border">
            <h2 class="text-base font-semibold text-foreground">
              {{ keyStatus?.has_key ? 'Обновить ключ' : 'Установить ключ' }}
            </h2>
          </div>
          <div class="px-6 py-5 space-y-4">
            <div class="space-y-2">
              <label for="api-key-input" class="text-sm font-medium text-foreground">
                API-ключ OpenAI
              </label>
              <input
                id="api-key-input"
                v-model="apiKeyInput"
                type="password"
                placeholder="sk-proj-..."
                class="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:ring-2 focus:ring-ring focus:border-transparent outline-none transition-colors"
                :disabled="isSaving"
              />
              <p v-if="validationError" class="text-xs text-red-500">{{ validationError }}</p>
              <p class="text-xs text-muted-foreground">
                Ключ шифруется и хранится безопасно. Только последние 4 символа будут видны.
              </p>
            </div>

            <div class="flex items-center gap-3">
              <Button
                :disabled="!apiKeyInput.trim() || isSaving"
                @click="handleSave"
              >
                <Loader2 v-if="isSaving" class="w-4 h-4 mr-2 animate-spin" />
                <Check v-else class="w-4 h-4 mr-2" />
                {{ keyStatus?.has_key ? 'Обновить ключ' : 'Установить ключ' }}
              </Button>
            </div>
          </div>
        </div>

        <!-- Info Block -->
        <div class="bg-muted/50 rounded-xl border border-border p-6">
          <h3 class="text-sm font-semibold text-foreground mb-2">Как это работает</h3>
          <ul class="text-sm text-muted-foreground space-y-1.5">
            <li>Если установлен собственный ключ, он используется для всех запросов к OpenAI</li>
            <li>При удалении ключа запросы к OpenAI будут недоступны до повторной установки ключа</li>
            <li>Ключ шифруется Fernet и никогда не возвращается в API-ответах</li>
          </ul>
        </div>
      </template>
    </template>

    <!-- Delete Confirmation Dialog -->
    <Dialog :open="showDeleteDialog" @update:open="showDeleteDialog = $event">
      <DialogContent class="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Удалить API-ключ</DialogTitle>
          <DialogDescription>
            После удаления запросы к OpenAI будут недоступны до установки нового ключа.
            Это действие нельзя отменить.
          </DialogDescription>
        </DialogHeader>
        <DialogFooter class="gap-2">
          <Button variant="ghost" :disabled="isDeleting" @click="showDeleteDialog = false">
            Отмена
          </Button>
          <Button variant="destructive" :disabled="isDeleting" @click="handleDelete">
            <Loader2 v-if="isDeleting" class="w-4 h-4 mr-2 animate-spin" />
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
import { ArrowLeft, KeyRound, ShieldAlert, Loader2, Trash2, Check } from 'lucide-vue-next'
import { Button } from '~/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '~/components/ui/dialog'
import { usePermissions } from '~/composables/usePermissions'
import { useTenantLlmConfig } from '~/composables/useTenantLlmConfig'

const { pageTitle } = useLayoutState()
const { canManageApiKeys } = usePermissions()
const {
  keyStatus,
  isLoading,
  isSaving,
  isDeleting,
  fetchKeyStatus,
  saveKey,
  deleteKey,
} = useTenantLlmConfig()

const apiKeyInput = ref('')
const validationError = ref('')
const showDeleteDialog = ref(false)

onMounted(() => {
  pageTitle.value = 'API-ключ OpenAI'
  if (canManageApiKeys.value) {
    fetchKeyStatus()
  }
})

watch(canManageApiKeys, (val) => {
  if (val) fetchKeyStatus()
})

watch(apiKeyInput, () => {
  validationError.value = ''
})

const handleSave = async () => {
  const key = apiKeyInput.value.trim()
  if (key.length < 10 || key.length > 512) {
    validationError.value = 'API-ключ должен быть от 10 до 512 символов'
    return
  }
  if (!key.startsWith('sk-')) {
    validationError.value = 'OpenAI ключ должен начинаться с «sk-»'
    return
  }

  const result = await saveKey({ api_key: key, provider: 'openai' })
  if (result) {
    apiKeyInput.value = ''
  }
}

const handleDelete = async () => {
  await deleteKey('openai')
  showDeleteDialog.value = false
}
</script>
