<template>
  <Dialog :open="open" @update:open="$emit('update:open', $event)">
    <DialogContent class="sm:max-w-md">
      <DialogHeader>
        <DialogTitle class="flex items-center gap-2.5">
          <span
            class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl"
            :class="destructive ? 'bg-red-50 text-red-600' : 'bg-primary/10 text-primary'"
          >
            <AlertTriangle class="h-4 w-4" />
          </span>
          {{ title }}
        </DialogTitle>
        <DialogDescription v-if="description">{{ description }}</DialogDescription>
      </DialogHeader>

      <DialogFooter class="gap-2 sm:gap-2">
        <Button variant="outline" :disabled="busy" @click="$emit('update:open', false)">
          {{ cancelLabel }}
        </Button>
        <button
          type="button"
          :disabled="busy"
          class="inline-flex items-center justify-center rounded-xl px-4 py-2 text-sm font-semibold text-white transition-colors disabled:cursor-not-allowed disabled:opacity-60"
          :class="destructive ? 'bg-red-600 hover:bg-red-700' : 'bg-primary hover:bg-primary/90'"
          @click="$emit('confirm')"
        >
          {{ confirmLabel }}
        </button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { AlertTriangle } from 'lucide-vue-next'
import { Button } from '~/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '~/components/ui/dialog'

/**
 * Подтверждение вместо нативного confirm().
 *
 * Браузер умеет подавлять системные диалоги («Не позволять этому сайту создавать
 * диалоговые окна»), и тогда confirm() молча возвращает false: пользователь жмёт
 * «Удалить», ничего не происходит и никакой ошибки не видно. Свой попап подавить
 * нельзя.
 */
withDefaults(
  defineProps<{
    open: boolean
    title: string
    description?: string
    confirmLabel?: string
    cancelLabel?: string
    /** Красная кнопка и красная иконка — для необратимых действий. */
    destructive?: boolean
    /** Блокирует кнопки на время запроса. */
    busy?: boolean
  }>(),
  {
    description: '',
    confirmLabel: 'Удалить',
    cancelLabel: 'Отмена',
    destructive: true,
    busy: false,
  },
)

defineEmits<{
  'update:open': [value: boolean]
  confirm: []
}>()
</script>
