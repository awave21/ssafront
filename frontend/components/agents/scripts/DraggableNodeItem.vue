<template>
  <div
    class="flex cursor-grab items-center gap-2.5 rounded-lg border px-3 py-2.5 shadow-sm transition-all hover:shadow-md active:cursor-grabbing active:scale-95"
    :style="{
      borderColor: `${color}40`,
      background: `${color}0a`,
    }"
    draggable="true"
    @dragstart="onDragStart"
  >
    <div class="rounded-md p-1.5 shrink-0" :style="{ background: `${color}20`, color }">
      <span class="text-base leading-none">{{ emoji }}</span>
    </div>
    <div class="flex flex-col min-w-0">
      <span class="text-xs font-semibold text-foreground">{{ label }}</span>
      <span class="text-[10px] text-muted-foreground truncate">{{ description }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  type: string
  label: string
  description: string
  color?: string
  emoji?: string
}>()

const onDragStart = (event: DragEvent) => {
  if (event.dataTransfer) {
    event.dataTransfer.setData('application/vueflow', props.type)
    event.dataTransfer.effectAllowed = 'move'
  }
}
</script>
