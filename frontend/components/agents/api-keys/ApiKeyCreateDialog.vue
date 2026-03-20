<template>
  <Dialog :open="open" @update:open="$emit('update:open', $event)">
    <DialogContent class="sm:max-w-md">
      <DialogHeader>
        <DialogTitle>Создать API-ключ</DialogTitle>
        <DialogDescription>
          Ключ позволит внешним системам отправлять сообщения агенту через API.
        </DialogDescription>
      </DialogHeader>

      <form @submit.prevent="handleSubmit" class="space-y-5">
        <div class="space-y-2">
          <label class="text-sm font-medium text-slate-700">Название *</label>
          <Input
            v-model="form.name"
            placeholder="Например: CRM интеграция"
            maxlength="100"
            required
          />
        </div>

        <div class="space-y-2">
          <label class="text-sm font-medium text-slate-700">Срок действия</label>
          <Select v-model="expiryOption">
            <SelectTrigger>
              <SelectValue placeholder="Выберите срок действия" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">Бессрочный</SelectItem>
              <SelectItem value="30">30 дней</SelectItem>
              <SelectItem value="90">90 дней</SelectItem>
              <SelectItem value="180">180 дней</SelectItem>
              <SelectItem value="365">365 дней</SelectItem>
              <SelectItem value="custom">Свой вариант</SelectItem>
            </SelectContent>
          </Select>
          <div v-if="expiryOption === 'custom'" class="pt-1">
            <Input
              v-model.number="form.customDays"
              type="number"
              min="1"
              max="365"
              placeholder="Количество дней (1–365)"
            />
          </div>
        </div>

        <div class="space-y-2">
          <label class="text-sm font-medium text-slate-700">Дневной лимит вызовов</label>
          <Input
            v-model.number="form.dailyLimit"
            type="number"
            min="1"
            placeholder="Без лимита"
          />
          <p class="text-xs text-slate-400">Оставьте пустым для неограниченного количества вызовов</p>
        </div>

        <DialogFooter class="gap-2 sm:gap-0">
          <Button type="button" variant="outline" @click="$emit('update:open', false)">
            Отмена
          </Button>
          <Button type="submit" :disabled="isSubmitting || !form.name.trim()">
            <Loader2 v-if="isSubmitting" class="h-4 w-4 animate-spin" />
            {{ isSubmitting ? 'Создание...' : 'Создать ключ' }}
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Loader2 } from 'lucide-vue-next'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '~/components/ui/dialog'
import { Button } from '~/components/ui/button'
import { Input } from '~/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '~/components/ui/select'

const props = defineProps<{
  open: boolean
  agentId: string
  isSubmitting?: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'submit': [payload: { name: string; expires_in_days?: number | null; daily_limit?: number | null }]
}>()

const form = ref({
  name: '',
  customDays: null as number | null,
  dailyLimit: null as number | null
})

const expiryOption = ref('none')

const resetForm = () => {
  form.value = { name: '', customDays: null, dailyLimit: null }
  expiryOption.value = 'none'
}

watch(() => props.open, (val) => {
  if (!val) resetForm()
})

const handleSubmit = () => {
  if (!form.value.name.trim()) return

  let expiresInDays: number | null = null
  if (expiryOption.value === 'custom') {
    expiresInDays = form.value.customDays && form.value.customDays >= 1 ? form.value.customDays : null
  } else if (expiryOption.value !== 'none') {
    expiresInDays = parseInt(expiryOption.value)
  }

  emit('submit', {
    name: form.value.name.trim(),
    expires_in_days: expiresInDays,
    daily_limit: form.value.dailyLimit && form.value.dailyLimit >= 1 ? form.value.dailyLimit : null
  })
}
</script>
