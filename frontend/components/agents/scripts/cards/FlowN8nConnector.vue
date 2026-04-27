<template>
  <!-- node-edge: линия от границы карточки наружу, «+» снаружи (как n8n). -->
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
    <Handle
      :id="handleId"
      :type="handleType"
      :position="connectPosition"
      class="flow-n8n-handle pointer-events-auto flex items-center justify-center !border-2 !border-background shadow-md !relative !transform-none"
      :class="handleBoxClass"
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
    </Handle>
    <div
      v-if="side === 'left'"
      class="h-0.5 shrink-0 rounded-full opacity-95"
      :class="lineWidthClass"
      :style="{ backgroundColor: portLineColor }"
    />
  </div>
  <div
    v-else
    class="pointer-events-none flex flex-row items-center"
  >
    <div
      class="h-0.5 shrink-0 rounded-full opacity-95"
      :class="lineWidthClass"
      :style="{ backgroundColor: portLineColor }"
    />
    <Handle
      :id="handleId"
      type="source"
      :position="connectPosition"
      class="flow-n8n-handle pointer-events-auto flex items-center justify-center !border-2 !border-background shadow-md !relative !transform-none"
      :class="handleBoxClass"
      :style="{ borderRadius: '9999px', backgroundColor: accent }"
      @click="onPortClick"
    >
      <Plus
        class="pointer-events-none text-white"
        :class="plusClass"
        :stroke-width="compact ? 2.75 : 3"
      />
    </Handle>
  </div>
</template>

<script setup lang="ts">
import { computed, inject } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { Plus } from 'lucide-vue-next'

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
  props.highlightLine ? 'hsl(var(--primary))' : 'rgba(249, 115, 22, 0.82)',
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
