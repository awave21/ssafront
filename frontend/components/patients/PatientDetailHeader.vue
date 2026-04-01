<template>
  <header
    class="mb-8 flex w-full min-w-0 flex-col gap-4 border-b border-slate-100 pb-6 sm:flex-row sm:items-center sm:justify-between"
  >
    <div class="flex min-w-0 items-center gap-3 sm:gap-4">
      <Button
        variant="outline"
        size="icon"
        class="h-10 w-10 shrink-0 rounded-xl border-slate-200 bg-white shadow-sm"
        type="button"
        aria-label="Назад к списку"
        @click="emit('back')"
      >
        <ArrowLeft class="h-5 w-5 text-slate-700" />
      </Button>
      <div
        class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary"
      >
        <User class="h-5 w-5" />
      </div>
      <div class="min-w-0">
        <template v-if="loading">
          <Skeleton class="h-6 w-48 max-w-full rounded-lg" />
          <Skeleton class="mt-2 h-4 w-64 max-w-full rounded-md" />
        </template>
        <template v-else>
          <h1 class="truncate text-lg font-bold tracking-tight text-slate-900 sm:text-xl">
            {{ displayName }}
          </h1>
          <p class="truncate text-xs font-medium text-slate-400 sm:text-sm">
            ID {{ externalIdLabel }} · Интеграция SQNS
          </p>
        </template>
      </div>
    </div>
    <div class="flex w-full min-w-0 flex-col gap-2 sm:w-auto sm:shrink-0 sm:flex-row sm:flex-wrap">
      <Button
        variant="outline"
        type="button"
        class="h-10 w-full gap-2 rounded-xl border-slate-100 bg-white text-xs font-bold shadow-sm sm:w-auto"
        disabled
        title="Скоро"
      >
        <MessageCircle class="h-4 w-4" />
        Написать сообщение
      </Button>
      <Button
        type="button"
        class="h-10 w-full gap-2 rounded-xl bg-primary text-xs font-bold text-primary-foreground shadow-lg shadow-primary/20 hover:bg-primary/90 sm:w-auto"
        disabled
        title="Скоро"
      >
        <CalendarPlus class="h-4 w-4" />
        Записать на приём
      </Button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { ArrowLeft, CalendarPlus, MessageCircle, User } from 'lucide-vue-next'
import Button from '~/components/ui/button/Button.vue'
import Skeleton from '~/components/ui/skeleton/Skeleton.vue'

defineProps<{
  displayName: string
  externalIdLabel: string
  loading: boolean
}>()

const emit = defineEmits<{
  back: []
}>()
</script>
