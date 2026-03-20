<template>
  <Dialog :open="open" @update:open="$emit('update:open', $event)">
    <DialogContent class="sm:max-w-4xl max-h-[90vh] flex flex-col">
      <DialogHeader>
        <DialogTitle>Предпросмотр нового промпта</DialogTitle>
        <DialogDescription>
          Мета-агент проанализировал ваши коррекции и сгенерировал улучшенный промпт
        </DialogDescription>
      </DialogHeader>

      <div v-if="preview" class="flex-1 overflow-y-auto space-y-4 py-2">
        <!-- Reasoning -->
        <div class="bg-muted/50 border border-border rounded-lg p-4">
          <p class="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
            Обоснование изменений
          </p>
          <p class="text-sm text-muted-foreground leading-relaxed whitespace-pre-wrap">
            {{ preview.reasoning }}
          </p>
        </div>

        <!-- Переключатель режима diff -->
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <span class="text-xs text-muted-foreground">Режим:</span>
            <Tabs v-model="diffMode" class="inline-flex">
              <TabsList class="h-8">
                <TabsTrigger value="side-by-side" class="text-xs px-3 h-6">Side-by-side</TabsTrigger>
                <TabsTrigger value="unified" class="text-xs px-3 h-6">Unified</TabsTrigger>
              </TabsList>
            </Tabs>
          </div>

          <Button
            v-if="!isEditing"
            size="sm"
            variant="outline"
            @click="startEditing"
          >
            <Pencil class="w-3.5 h-3.5 mr-1" />
            Редактировать вручную
          </Button>
          <Button
            v-else
            size="sm"
            variant="ghost"
            @click="cancelEditing"
          >
            Отменить правку
          </Button>
        </div>

        <!-- Режим редактирования -->
        <div v-if="isEditing" class="space-y-2">
          <textarea
            v-model="editedPrompt"
            rows="16"
            class="w-full rounded-md border border-border bg-background px-4 py-3 text-sm font-mono leading-relaxed focus:ring-2 focus:ring-ring resize-y"
          />
        </div>

        <!-- Side-by-side diff -->
        <div v-else-if="diffMode === 'side-by-side'" class="grid grid-cols-2 gap-0 border border-border rounded-lg overflow-hidden">
          <div class="border-r border-border">
            <div class="px-3 py-2 bg-red-50 border-b border-border">
              <span class="text-xs font-semibold text-red-700">Было</span>
            </div>
            <div class="p-3 text-sm font-mono leading-relaxed max-h-[400px] overflow-y-auto">
              <div
                v-for="(seg, i) in diffLeft"
                :key="'l' + i"
                class="whitespace-pre-wrap"
                :class="{
                  'bg-red-100 text-red-900': seg.type === 'removed',
                  'text-foreground': seg.type === 'equal',
                }"
              >{{ seg.text }}</div>
            </div>
          </div>
          <div>
            <div class="px-3 py-2 bg-emerald-50 border-b border-border">
              <span class="text-xs font-semibold text-emerald-700">Стало</span>
            </div>
            <div class="p-3 text-sm font-mono leading-relaxed max-h-[400px] overflow-y-auto">
              <div
                v-for="(seg, i) in diffRight"
                :key="'r' + i"
                class="whitespace-pre-wrap"
                :class="{
                  'bg-emerald-100 text-emerald-900': seg.type === 'added',
                  'text-foreground': seg.type === 'equal',
                }"
              >{{ seg.text }}</div>
            </div>
          </div>
        </div>

        <!-- Unified diff -->
        <div v-else class="border border-border rounded-lg overflow-hidden">
          <div class="px-3 py-2 bg-muted/50 border-b border-border">
            <span class="text-xs font-semibold text-muted-foreground">Изменения</span>
          </div>
          <div class="p-3 text-sm font-mono leading-relaxed max-h-[400px] overflow-y-auto">
            <div
              v-for="(change, i) in unifiedDiff"
              :key="'u' + i"
              class="whitespace-pre-wrap"
              :class="{
                'bg-red-100 text-red-900': change.removed,
                'bg-emerald-100 text-emerald-900': change.added,
                'text-foreground': !change.added && !change.removed,
              }"
            >{{ change.value }}</div>
          </div>
        </div>

        <!-- Метаинформация -->
        <div class="flex flex-wrap items-center gap-4 text-xs text-muted-foreground pt-1">
          <span>Использовано коррекций: <strong class="text-foreground">{{ preview.feedback_used }}</strong></span>
          <span v-if="preview.meta_model">Мета-модель: <strong class="text-foreground">{{ preview.meta_model }}</strong></span>
          <span v-if="preview.agent_model">Модель агента: <strong class="text-foreground">{{ preview.agent_model }}</strong></span>
          <span v-if="preview.change_summary" class="flex-1 basis-full">{{ preview.change_summary }}</span>
        </div>
      </div>

      <DialogFooter class="shrink-0 gap-2">
        <Button
          variant="ghost"
          :disabled="isApplying"
          @click="$emit('update:open', false)"
        >
          Отменить
        </Button>
        <Button
          :disabled="isApplying"
          @click="handleApply"
        >
          <Loader2 v-if="isApplying" class="w-4 h-4 mr-2 animate-spin" />
          <Check v-else class="w-4 h-4 mr-2" />
          Применить
        </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { diffLines, type Change } from 'diff'
import { Pencil, Loader2, Check } from 'lucide-vue-next'
import { Button } from '~/components/ui/button'
import { Tabs, TabsList, TabsTrigger } from '~/components/ui/tabs'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '~/components/ui/dialog'
import { computeLineDiff, type DiffSegment } from '~/utils/text-diff'
import type { GeneratedPromptPreview } from '~/types/promptTraining'

const props = defineProps<{
  open: boolean
  preview: GeneratedPromptPreview | null
  isApplying: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  apply: [prompt?: string]
}>()

const diffMode = ref<'side-by-side' | 'unified'>('side-by-side')
const isEditing = ref(false)
const editedPrompt = ref('')

const currentPrompt = computed(() => props.preview?.current_prompt ?? '')
const generatedPrompt = computed(() =>
  isEditing.value ? editedPrompt.value : (props.preview?.generated_prompt ?? '')
)

// Side-by-side diff (existing utility)
const sideBySideDiff = computed(() => {
  if (!props.preview) return { left: [], right: [] }
  return computeLineDiff(currentPrompt.value, generatedPrompt.value)
})

const diffLeft = computed<DiffSegment[]>(() => sideBySideDiff.value.left)
const diffRight = computed<DiffSegment[]>(() => sideBySideDiff.value.right)

// Unified diff (npm diff package)
const unifiedDiff = computed<Change[]>(() => {
  if (!props.preview) return []
  return diffLines(currentPrompt.value, generatedPrompt.value)
})

const startEditing = () => {
  editedPrompt.value = props.preview?.generated_prompt ?? ''
  isEditing.value = true
}

const cancelEditing = () => {
  isEditing.value = false
  editedPrompt.value = ''
}

const handleApply = () => {
  if (isEditing.value) {
    emit('apply', editedPrompt.value)
  } else {
    emit('apply')
  }
}

watch(() => props.open, (val) => {
  if (val) {
    isEditing.value = false
    editedPrompt.value = ''
    diffMode.value = 'side-by-side'
  }
})
</script>
