<template>
  <div class="flex items-center justify-between gap-2">
    <p class="min-w-0 flex-1 truncate text-xs text-slate-500" :title="value || ''">
      {{ value || '—' }}
    </p>
    <Button
      variant="outline"
      size="sm"
      class="h-8 w-8 shrink-0 rounded-md p-0"
      :aria-label="`Редактировать: ${label}`"
      :title="`Редактировать: ${label}`"
      @click="openSheet"
    >
      <Pencil class="h-3.5 w-3.5" />
    </Button>

    <Sheet :open="open" @update:open="(o: boolean) => { if (!o) close() }">
      <SheetContent side="right" class-name="w-full sm:max-w-xl flex flex-col">
        <SheetHeader>
          <SheetTitle>{{ title }}</SheetTitle>
        </SheetHeader>

        <div class="flex min-h-0 flex-1 flex-col gap-3 p-6">
          <p v-if="entityName" class="shrink-0 text-sm text-slate-600">{{ entityName }}</p>
          <label class="shrink-0 text-sm font-medium text-slate-700">{{ label }}</label>
          <Textarea
            v-model="draft"
            :placeholder="placeholder"
            class="min-h-0 flex-1 resize-none"
          />
          <p v-if="hint" class="shrink-0 text-xs text-slate-400">{{ hint }}</p>
        </div>

        <div class="flex items-center justify-end gap-2 border-t border-slate-200 bg-white px-6 py-4">
          <button
            class="rounded-md px-4 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="saving"
            @click="close"
          >
            Отмена
          </button>
          <button
            class="inline-flex items-center gap-1.5 rounded-xl bg-primary px-5 py-2 text-sm font-bold text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="saving"
            @click="save"
          >
            <Loader2 v-if="saving" class="h-4 w-4 animate-spin" />
            {{ saving ? 'Сохранение...' : 'Сохранить' }}
          </button>
        </div>
      </SheetContent>
    </Sheet>
  </div>
</template>

<script setup lang="ts">
/**
 * Ячейка таблицы с редактируемым длинным текстом (описание услуги / информация
 * специалиста). Показывает значение (truncate + тултип) + карандаш → Sheet с
 * Textarea на всю высоту. Единый компонент для вкладок «Услуги» и «Специалисты»
 * (устраняет дублирование). Сохранение — через переданный `onSave` (родитель
 * владеет API-вызовом и тостами; при ошибке пробрасывает исключение — панель
 * остаётся открытой).
 */
import { ref } from 'vue'
import { Pencil, Loader2 } from 'lucide-vue-next'
import { Button } from './ui/button'
import { Sheet, SheetContent, SheetHeader, SheetTitle } from './ui/sheet'
import { Textarea } from './ui/textarea'

const props = defineProps<{
  value: string | null | undefined
  title: string
  label: string
  entityName?: string
  placeholder?: string
  hint?: string
  onSave: (value: string) => Promise<void>
}>()

const open = ref(false)
const draft = ref('')
const saving = ref(false)

const openSheet = () => {
  draft.value = props.value ?? ''
  open.value = true
}

const close = () => {
  if (saving.value) return
  open.value = false
  draft.value = ''
}

const save = async () => {
  saving.value = true
  try {
    await props.onSave(draft.value.trim())
    open.value = false
    draft.value = ''
  } catch {
    // Родитель показывает тост об ошибке; панель оставляем открытой для повторной попытки.
  } finally {
    saving.value = false
  }
}
</script>
