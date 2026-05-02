<template>
  <!-- node-edge: handle снаружи карточки на её краю (как у обычной ноды Vue Flow). -->
  <div
    v-if="variant === 'node-edge'"
    class="pointer-events-none absolute top-1/2 z-[5] flex -translate-y-1/2 items-center"
    :class="side === 'right' ? 'left-full flex-row' : 'right-full flex-row'"
  >
    <div
      v-if="side === 'right'"
      class="h-0.5 shrink-0 rounded-full opacity-95"
      :class="lineWidthClass"
      :style="{ backgroundColor: portLineColor }"
    />
    <div
      class="flow-n8n-handle pointer-events-auto flex items-center justify-center !border-2 !border-background shadow-md cursor-crosshair"
      :class="handleBoxClass"
      :data-handle-id="handleId"
      :data-handle-type="handleType"
      :data-node-id="nodeId"
      :data-handle-position="connectPosition"
      :style="{ borderRadius: '9999px', backgroundColor: accent }"
      @click="onPortClick"
    >
      <Plus
        v-if="handleType === 'source'"
        class="pointer-events-none text-white"
        :class="plusClass"
        :stroke-width="compact ? 2.75 : 3"
      />
      <span
        v-else
        class="pointer-events-none rounded-full bg-white shadow-sm ring-2 ring-white/80"
        :class="targetDotClass"
      />
    </div>
    <div
      v-if="side === 'left'"
      class="h-0.5 shrink-0 rounded-full opacity-95"
      :class="lineWidthClass"
      :style="{ backgroundColor: portLineColor }"
    />
  </div>

  <!-- inline: handle в потоке (для condition веток). -->
  <div
    v-else
    class="pointer-events-none flex flex-row items-center"
  >
    <div
      class="h-0.5 shrink-0 rounded-full opacity-95"
      :class="lineWidthClass"
      :style="{ backgroundColor: portLineColor }"
    />
    <div
      class="flow-n8n-handle pointer-events-auto flex items-center justify-center !border-2 !border-background shadow-md cursor-crosshair"
      :class="handleBoxClass"
      :data-handle-id="handleId"
      :data-handle-type="'source'"
      :data-node-id="nodeId"
      :data-handle-position="connectPosition"
      :style="{ borderRadius: '9999px', backgroundColor: accent }"
      @click="onPortClick"
    >
      <Plus
        class="pointer-events-none text-white"
        :class="plusClass"
        :stroke-width="compact ? 2.75 : 3"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, inject } from 'vue'
import { Plus } from 'lucide-vue-next'

/** Position — простое строковое перечисление (раньше было из @vue-flow/core). */
type Position = 'left' | 'right' | 'top' | 'bottom'

const props = withDefaults(
  defineProps<{
    nodeId: string
    handleType: 'source' | 'target'
    handleId: string
    connectPosition: Position
    accent: string
    /** Линия-отвод: рамка ноды / синий при выделенной ноде */
    highlightLine?: boolean
    variant?: 'node-edge' | 'inline'
    side?: 'left' | 'right'
    lineWidthClass?: string
    compact?: boolean
  }>(),
  {
    highlightLine: false,
    variant: 'node-edge',
    side: 'right',
    lineWidthClass: 'w-7',
    compact: false,
  },
)

const openPalette = inject<((nodeId: string, handleId: string) => void) | undefined>('openPaletteFromConnector', undefined)
const openInspector = inject<((id: string) => void) | undefined>('openInspectorFromConnector', undefined)

/** В покое — оранжевый контур как у неактивных рёбер на канвасе. */
const portLineColor = computed(() =>
  props.highlightLine ? props.accent : `${props.accent}b0`,
)

const onPortClick = (e: MouseEvent) => {
  e.stopPropagation()
  if (props.handleType === 'source' && openPalette) {
    openPalette(props.nodeId, props.handleId)
    return
  }
  if (props.handleType === 'target' && openInspector)
    openInspector(props.nodeId)
}

const handleBoxClass = computed(() =>
  props.compact
    ? '!h-[18px] !w-[18px] min-h-[18px] min-w-[18px]'
    : '!h-[22px] !w-[22px] min-h-[22px] min-w-[22px]',
)

const plusClass = computed(() => (props.compact ? 'size-3' : 'size-3.5'))

const targetDotClass = computed(() => (props.compact ? 'size-1.5' : 'size-2'))
</script>

<style scoped>
.flow-n8n-handle {
  /* Плавные переходы для hover/active. transform отвечает за scale/rotate, */
  /* box-shadow за свечение. cubic-bezier даёт лёгкий «спружиненный» эффект.    */
  transition:
    transform 0.18s cubic-bezier(0.34, 1.56, 0.64, 1),
    box-shadow 0.18s ease,
    filter 0.18s ease;
}

/* На hover — увеличиваем + добавляем мягкое свечение цветом accent. */
.flow-n8n-handle:hover {
  transform: scale(1.18);
  box-shadow:
    0 0 0 4px rgba(255, 255, 255, 0.55),
    0 4px 14px -2px rgba(99, 102, 241, 0.45),
    0 0 0 1px rgba(99, 102, 241, 0.2);
  filter: brightness(1.1);
}

/* При нажатии — слегка сжимается и становится темнее (тактильно). */
.flow-n8n-handle:active {
  transform: scale(0.92);
  transition-duration: 0.08s;
  filter: brightness(0.92);
}

/* Плюсик внутри handle — лёгкое вращение на hover. */
.flow-n8n-handle :deep(svg) {
  transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.flow-n8n-handle:hover :deep(svg) {
  transform: rotate(90deg);
}

/* Плавный pulse фокуса когда канвас в connect-mode (опц., если хотим подсветку target). */
@keyframes flow-handle-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(99, 102, 241, 0.5); }
  50%      { box-shadow: 0 0 0 8px rgba(99, 102, 241, 0); }
}
</style>
