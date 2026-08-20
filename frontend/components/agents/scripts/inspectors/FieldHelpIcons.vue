<template>
  <span v-if="meta" class="inline-flex items-center gap-2 align-middle">
    <Popover>
      <PopoverTrigger as-child>
        <button
          type="button"
          class="inline-flex h-5 w-5 items-center justify-center rounded-md text-muted-foreground/70 hover:text-foreground hover:bg-muted/60 transition-colors"
          aria-label="Подсказка"
        >
          <HelpCircle class="size-3.5" />
        </button>
      </PopoverTrigger>
      <PopoverContent side="top" align="start" class="w-80 text-xs">
        <p class="text-foreground/90 leading-snug">{{ meta.description }}</p>
        <div v-if="meta.examples?.length" class="mt-2">
          <p class="text-[9px] font-semibold uppercase tracking-wider text-muted-foreground mb-1">
            Примеры
          </p>
          <ul class="space-y-1 text-[11px] leading-snug text-muted-foreground">
            <li
              v-for="(ex, idx) in meta.examples"
              :key="idx"
              class="border-l-2 border-primary/40 pl-2"
            >
              {{ ex }}
            </li>
          </ul>
        </div>
        <p
          v-if="hasValue"
          class="mt-2 pt-2 border-t border-border/60 text-[10px] text-muted-foreground"
        >
          AI-генерация перезапишет текущее значение.
        </p>
      </PopoverContent>
    </Popover>

    <button
      v-if="aiEnabled && meta.aiEnabled"
      type="button"
      :disabled="isLoading || !canGenerate"
      class="inline-flex h-5 w-5 items-center justify-center rounded-md text-primary/70 hover:text-primary hover:bg-primary/10 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
      :aria-label="isLoading ? 'Генерация…' : 'Заполнить через AI'"
      :title="isLoading ? 'Генерация…' : 'Заполнить через AI (gpt-4o-mini)'"
      @click="handleAiClick"
    >
      <Loader2 v-if="isLoading" class="size-3.5 animate-spin" />
      <Sparkles v-else class="size-3.5" />
    </button>
  </span>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { HelpCircle, Loader2, Sparkles } from 'lucide-vue-next'
import { Popover, PopoverContent, PopoverTrigger } from '~/components/ui/popover'
import { getFieldMeta } from '~/utils/scriptFlowFieldMeta'
import { useScriptFlowFieldGenerator } from '~/composables/useScriptFlowFieldGenerator'

const props = withDefaults(
  defineProps<{
    fieldKey: string
    nodeId: string | null
    nodeType: string
    aiEnabled?: boolean
    currentNodeData: Record<string, unknown>
    currentValue?: string
  }>(),
  {
    aiEnabled: true,
    currentValue: '',
  },
)

const emit = defineEmits<{
  (e: 'ai-fill', text: string): void
}>()

const meta = computed(() => getFieldMeta(props.fieldKey))
const hasValue = computed(() => !!(props.currentValue || '').trim())

const route = useRoute()
const agentId = computed(() => String(route.params.id ?? ''))
const flowId = computed(() => String(route.params.flowId ?? ''))

const canGenerate = computed(
  () => !!agentId.value && !!flowId.value && !!props.nodeId,
)

const { generateField, isGenerating } = useScriptFlowFieldGenerator()
const isLoading = ref(false)

const handleAiClick = async () => {
  if (!canGenerate.value || isLoading.value) return
  isLoading.value = true
  try {
    const text = await generateField({
      agentId: agentId.value,
      flowId: flowId.value,
      nodeId: props.nodeId!,
      nodeType: props.nodeType,
      fieldKey: props.fieldKey,
      currentNodeData: props.currentNodeData,
    })
    if (text) emit('ai-fill', text)
  } finally {
    isLoading.value = false
  }
}

defineExpose({ isGenerating })
</script>
