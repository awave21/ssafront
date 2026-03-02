<template>
  <Dialog :open="open" @update:open="$emit('update:open', $event)">
    <DialogContent class="sm:max-w-md">
      <DialogHeader>
        <DialogTitle>Добавить правило</DialogTitle>
        <DialogDescription>
          Опишите правило поведения агента, которое должно учитываться при генерации промпта
        </DialogDescription>
      </DialogHeader>

      <div class="py-4">
        <textarea
          v-model="ruleText"
          placeholder="Например: всегда обращаться к клиенту на «вы», предлагать запись на приём..."
          rows="4"
          class="w-full rounded-md border border-border bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:ring-2 focus:ring-ring resize-none"
        />
      </div>

      <DialogFooter>
        <Button variant="ghost" @click="$emit('update:open', false)">
          Отмена
        </Button>
        <Button :disabled="!ruleText.trim()" @click="handleSubmit">
          Добавить
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { Button } from '~/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '~/components/ui/dialog'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  submit: [ruleText: string]
}>()

const ruleText = ref('')

watch(() => props.open, (val) => {
  if (val) ruleText.value = ''
})

const handleSubmit = () => {
  if (!ruleText.value.trim()) return
  emit('submit', ruleText.value.trim())
  ruleText.value = ''
}
</script>
