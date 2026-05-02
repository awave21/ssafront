<template>
  <Dialog :open="open" @update:open="$emit('update:open', $event)">
    <DialogContent class="sm:max-w-md">
      <DialogHeader>
        <DialogTitle>Переименовать поток</DialogTitle>
        <DialogDescription>
          Измените название потока. Это название видят менеджеры в списке и в результатах поиска.
        </DialogDescription>
      </DialogHeader>

      <form v-if="flow" class="space-y-5" @submit.prevent="handleSubmit">
        <div class="space-y-2">
          <label class="text-sm font-medium text-slate-700">Название</label>
          <Input
            ref="inputRef"
            v-model="name"
            placeholder="Название потока"
            maxlength="200"
          />
        </div>

        <DialogFooter class="gap-2 sm:gap-0">
          <Button type="button" variant="outline" @click="$emit('update:open', false)">
            Отмена
          </Button>
          <Button type="submit" :disabled="isSubmitting || !hasChanges || !name.trim()">
            <Loader2 v-if="isSubmitting" class="h-4 w-4 animate-spin" />
            {{ isSubmitting ? 'Сохранение…' : 'Сохранить' }}
          </Button>
        </DialogFooter>
      </form>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { Loader2 } from 'lucide-vue-next'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '~/components/ui/dialog'
import { Button } from '~/components/ui/button'
import { Input } from '~/components/ui/input'
import type { ScriptFlow } from '~/types/scriptFlow'

const props = defineProps<{
  open: boolean
  flow: ScriptFlow | null
  isSubmitting?: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'submit': [payload: { name: string }]
}>()

const name = ref('')
const inputRef = ref<{ $el?: HTMLElement } | null>(null)

watch(
  () => props.open,
  async (val) => {
    if (val && props.flow) {
      name.value = props.flow.name
      await nextTick()
      const el = (inputRef.value as any)?.$el ?? inputRef.value
      const input = el instanceof HTMLInputElement ? el : el?.querySelector?.('input')
      input?.focus()
      input?.select()
    }
  },
)

const hasChanges = computed(() => {
  if (!props.flow) return false
  return name.value.trim() !== props.flow.name
})

const handleSubmit = () => {
  if (!props.flow || !hasChanges.value) return
  const trimmed = name.value.trim()
  if (!trimmed) return
  emit('submit', { name: trimmed })
}
</script>
