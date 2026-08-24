<template>
  <div class="flex flex-col gap-3">
    <!-- Найденные блоки промпта -->
    <div class="rounded-2xl border border-slate-100 bg-white p-3 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
      <div class="px-1 pb-1 text-[10px] font-bold uppercase tracking-wider text-slate-400">
        Блоки промпта
      </div>

      <ul v-if="detectedBlocks.length" class="flex flex-col gap-0.5">
        <li v-for="block in detectedBlocks" :key="block.char">
          <button
            type="button"
            @click="$emit('navigate', block)"
            class="group flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left transition-colors"
            :class="activeChar === block.char
              ? 'bg-primary/10 text-primary'
              : 'text-slate-600 hover:bg-slate-50'"
          >
            <span class="flex-1 truncate font-mono text-xs font-semibold">{{ block.label }}</span>
            <Check class="h-3.5 w-3.5 shrink-0 text-green-600" />
          </button>
        </li>
      </ul>

      <p v-else class="px-1 py-2 text-[11px] leading-snug text-slate-400">
        Заголовки не найдены. Добавьте блоки вида <span class="font-mono text-slate-500"># РОЛЬ</span>,
        чтобы структурировать промпт.
      </p>
    </div>

    <!-- Рекомендуемые, но отсутствующие блоки -->
    <div v-if="missingBlocks.length" class="rounded-2xl bg-amber-50 p-3">
      <div class="px-1 pb-1 text-[10px] font-bold uppercase tracking-wider text-amber-600">
        Не хватает блоков
      </div>

      <div class="flex flex-col gap-1.5">
        <button
          v-for="block in missingBlocks"
          :key="block.key"
          type="button"
          :disabled="!canEdit"
          @click="$emit('add', block)"
          class="flex w-full items-center gap-1.5 rounded-lg bg-white px-2 py-1.5 text-left transition-colors hover:bg-amber-100/40 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Plus class="h-3 w-3 shrink-0 text-amber-600" />
          <span class="flex-1 truncate font-mono text-[11px] font-semibold text-slate-700">
            # {{ block.label }}
          </span>
        </button>
      </div>

      <p class="px-1 pt-2 text-[10px] leading-tight text-amber-600">
        Вставятся в конец промпта как обычный текст — можно править и удалять.
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Check, Plus } from 'lucide-vue-next'

/** Блок, найденный в тексте промпта (заголовок # ... или XML-тег <...>). */
export type OutlineBlock = {
  /** Отображаемая метка, как в тексте: «# РОЛЬ» или «<role>». */
  label: string
  /** Нормализованный ключ для сравнения (верхний регистр, без разметки). */
  key: string
  /** Смещение начала заголовка в символах. */
  char: number
  /** Длина строки заголовка (для выделения при переходе). */
  length: number
}

/** Рекомендуемый блок для карточки «не хватает». */
export type RecommendedBlock = {
  label: string
  key: string
  /** Ключи-синонимы, по которым блок считается присутствующим. */
  aliases: string[]
  /** Заготовка, вставляемая в конец промпта. */
  stub: string
}

const props = defineProps<{
  text: string
  canEdit: boolean
  /** Смещение активного блока (обычно позиция курсора) для подсветки. */
  activeChar?: number | null
}>()

defineEmits<{
  (e: 'navigate', block: OutlineBlock): void
  (e: 'add', block: RecommendedBlock): void
}>()

/** Канонический набор блоков хорошо структурированного промпта. */
const RECOMMENDED: RecommendedBlock[] = [
  { label: 'РОЛЬ', key: 'РОЛЬ', aliases: ['РОЛЬ', 'ПЕРСОНА', 'ROLE', 'PERSONA'], stub: '# РОЛЬ\nТы — ...\n' },
  { label: 'ПРАВИЛА', key: 'ПРАВИЛА', aliases: ['ПРАВИЛА', 'ИНСТРУКЦИИ', 'INSTRUCTIONS', 'RULES'], stub: '# ПРАВИЛА\n1. ...\n' },
  { label: 'ИНСТРУМЕНТЫ', key: 'ИНСТРУМЕНТЫ', aliases: ['ИНСТРУМЕНТЫ', 'ТУЛЫ', 'TOOLS'], stub: '# ИНСТРУМЕНТЫ\n- ...\n' },
  { label: 'КОНТЕКСТ', key: 'КОНТЕКСТ', aliases: ['КОНТЕКСТ', 'CONTEXT'], stub: '# КОНТЕКСТ\n...\n' },
  { label: 'ЕСЛИ НЕ ЗНАЮ', key: 'ЕСЛИ НЕ ЗНАЮ', aliases: ['ЕСЛИ НЕ ЗНАЮ', 'FALLBACK', 'НЕ ЗНАЮ'], stub: '# ЕСЛИ НЕ ЗНАЮ\nЕсли не знаешь ответ — честно скажи об этом и предложи связать с администратором.\n' },
  { label: 'ЭСКАЛАЦИЯ', key: 'ЭСКАЛАЦИЯ', aliases: ['ЭСКАЛАЦИЯ', 'ПЕРЕДАЧА', 'ESCALATION'], stub: '# ЭСКАЛАЦИЯ\nВ сложных или конфликтных ситуациях переводи диалог на администратора.\n' },
]

const normalize = (raw: string): string =>
  raw
    .replace(/^#+\s*/, '')
    .replace(/^<\s*|\s*>$/g, '')
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toUpperCase()

/** Парсим заголовки промпта: строки «# ...» и одиночные XML-теги «<tag>». */
const detectedBlocks = computed<OutlineBlock[]>(() => {
  const text = props.text || ''
  const blocks: OutlineBlock[] = []
  let offset = 0
  for (const line of text.split('\n')) {
    const trimmed = line.trim()
    const isHeading = /^#{1,6}\s+\S/.test(trimmed)
    const isTag = /^<[a-zA-Zа-яА-Я_][\w-]*>$/.test(trimmed)
    if (isHeading || isTag) {
      blocks.push({
        label: trimmed,
        key: normalize(trimmed),
        char: offset + (line.length - line.trimStart().length),
        length: trimmed.length,
      })
    }
    offset += line.length + 1 // +1 за перенос строки
  }
  return blocks
})

const missingBlocks = computed<RecommendedBlock[]>(() => {
  const present = new Set(detectedBlocks.value.map(b => b.key))
  return RECOMMENDED.filter(rec => !rec.aliases.some(alias => present.has(alias.toUpperCase())))
})
</script>
