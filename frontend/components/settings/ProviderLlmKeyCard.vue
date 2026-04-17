<template>
  <div class="bg-background rounded-xl border border-border overflow-hidden">
    <div class="px-6 py-4 border-b border-border">
      <h2 class="text-base font-semibold text-foreground">{{ title }}</h2>
      <p class="text-sm text-muted-foreground mt-0.5">{{ description }}</p>
    </div>
    <div class="px-6 py-5 space-y-4">
      <div v-if="status?.has_key" class="flex items-center justify-between gap-3">
        <div class="flex items-center gap-3 min-w-0">
          <div
            class="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
            :class="status.is_active ? 'bg-emerald-100' : 'bg-amber-100'"
          >
            <KeyRound class="w-5 h-5" :class="status.is_active ? 'text-emerald-600' : 'text-amber-600'" />
          </div>
          <div class="min-w-0">
            <div class="flex flex-wrap items-center gap-2">
              <span class="text-sm font-medium text-foreground truncate">••••{{ status.last4 }}</span>
              <span
                class="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded shrink-0"
                :class="status.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'"
              >
                {{ status.is_active ? 'Активен' : 'Неактивен' }}
              </span>
            </div>
            <p class="text-xs text-muted-foreground mt-0.5">Провайдер: {{ status.provider }}</p>
          </div>
        </div>
        <Button
          variant="destructive"
          size="sm"
          :disabled="isDeleting"
          @click="$emit('request-delete')"
        >
          <Loader2 v-if="isDeleting && deletingForThis" class="w-4 h-4 mr-1.5 animate-spin" />
          <Trash2 v-else class="w-4 h-4 mr-1.5" />
          Удалить
        </Button>
      </div>
      <div v-else class="flex items-center gap-3">
        <div class="w-10 h-10 bg-muted rounded-lg flex items-center justify-center shrink-0">
          <KeyRound class="w-5 h-5 text-muted-foreground" />
        </div>
        <p class="text-sm text-muted-foreground">Ключ не установлен</p>
      </div>

      <div class="space-y-2 pt-2 border-t border-border">
        <label :for="inputId" class="text-sm font-medium text-foreground">{{ inputLabel }}</label>
        <input
          :id="inputId"
          :value="modelValue"
          type="password"
          :placeholder="placeholder"
          class="w-full rounded-md border border-border bg-background px-3 py-2 text-sm focus:ring-2 focus:ring-ring focus:border-transparent outline-none transition-colors"
          :disabled="isSaving"
          @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
        />
        <div class="flex items-center gap-3">
          <Button :disabled="!modelValue.trim() || isSaving" @click="$emit('save')">
            <Loader2 v-if="isSaving" class="w-4 h-4 mr-2 animate-spin" />
            <Check v-else class="w-4 h-4 mr-2" />
            {{ status?.has_key ? 'Обновить ключ' : 'Установить ключ' }}
          </Button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { KeyRound, Loader2, Trash2, Check } from 'lucide-vue-next'
import { Button } from '~/components/ui/button'
import type { TenantLLMConfigStatus } from '~/types/tenantLlmConfig'

const props = defineProps<{
  title: string
  description: string
  providerId: string
  status: TenantLLMConfigStatus | null
  modelValue: string
  inputLabel: string
  placeholder?: string
  isSaving: boolean
  isDeleting: boolean
  deletingForThis: boolean
}>()

defineEmits<{
  'update:modelValue': [value: string]
  save: []
  'request-delete': []
}>()

const inputId = computed(() => `llm-key-input-${props.providerId}`)
</script>
