<template>
  <Dialog :open="open" @update:open="$emit('update:open', $event)">
    <DialogContent class="sm:max-w-md">
      <DialogHeader>
        <DialogTitle>Редактировать ключ</DialogTitle>
        <DialogDescription>
          Измените настройки API-ключа <span class="font-mono text-slate-700">sk-••••{{ apiKey?.last4 }}</span>
        </DialogDescription>
      </DialogHeader>

      <form v-if="apiKey" @submit.prevent="handleSubmit" class="space-y-5">
        <div class="space-y-2">
          <label class="text-sm font-medium text-slate-700">Название</label>
          <Input
            v-model="form.name"
            placeholder="Название ключа"
            maxlength="100"
          />
        </div>

        <div class="space-y-2">
          <label class="text-sm font-medium text-slate-700">Дневной лимит вызовов</label>
          <Input
            v-model.number="form.dailyLimit"
            type="number"
            min="1"
            placeholder="Без лимита"
          />
          <p class="text-xs text-slate-400">Оставьте пустым для неограниченного количества</p>
        </div>

        <div class="space-y-2">
          <label class="text-sm font-medium text-slate-700">Продлить срок действия</label>
          <Select v-model="extendOption">
            <SelectTrigger>
              <SelectValue placeholder="Не продлевать" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">Не продлевать</SelectItem>
              <SelectItem value="30">+30 дней от сейчас</SelectItem>
              <SelectItem value="90">+90 дней от сейчас</SelectItem>
              <SelectItem value="180">+180 дней от сейчас</SelectItem>
              <SelectItem value="365">+365 дней от сейчас</SelectItem>
            </SelectContent>
          </Select>
          <p v-if="apiKey.expires_at" class="text-xs text-slate-400">
            Текущий срок: {{ formatDate(apiKey.expires_at) }}
          </p>
          <p v-else class="text-xs text-slate-400">Сейчас: бессрочный</p>
        </div>

        <DialogFooter class="gap-2 sm:gap-0">
          <Button type="button" variant="outline" @click="$emit('update:open', false)">
            Отмена
          </Button>
          <Button type="submit" :disabled="isSubmitting || !hasChanges">
            <Loader2 v-if="isSubmitting" class="h-4 w-4 animate-spin" />
            {{ isSubmitting ? 'Сохранение...' : 'Сохранить' }}
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Loader2 } from 'lucide-vue-next'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '~/components/ui/dialog'
import { Button } from '~/components/ui/button'
import { Input } from '~/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '~/components/ui/select'
import type { ApiKey } from '~/types/apiKey'

const props = defineProps<{
  open: boolean
  apiKey: ApiKey | null
  isSubmitting?: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'submit': [payload: { name?: string; daily_limit?: number | null; expires_in_days?: number | null }]
}>()

const form = ref({ name: '', dailyLimit: null as number | null })
const extendOption = ref('none')

watch(() => props.open, (val) => {
  if (val && props.apiKey) {
    form.value.name = props.apiKey.name
    form.value.dailyLimit = props.apiKey.daily_limit
    extendOption.value = 'none'
  }
})

const hasChanges = computed(() => {
  if (!props.apiKey) return false
  return form.value.name !== props.apiKey.name
    || form.value.dailyLimit !== props.apiKey.daily_limit
    || extendOption.value !== 'none'
})

const formatDate = (iso: string) => {
  return new Date(iso).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
}

const handleSubmit = () => {
  if (!props.apiKey || !hasChanges.value) return

  const payload: Record<string, unknown> = {}

  if (form.value.name !== props.apiKey.name) {
    payload.name = form.value.name
  }
  if (form.value.dailyLimit !== props.apiKey.daily_limit) {
    payload.daily_limit = form.value.dailyLimit && form.value.dailyLimit >= 1 ? form.value.dailyLimit : null
  }
  if (extendOption.value !== 'none') {
    payload.expires_in_days = parseInt(extendOption.value)
  }

  emit('submit', payload)
}
</script>
