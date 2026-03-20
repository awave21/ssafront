<template>
  <!-- Desktop: native context menu (right-click) -->
  <ContextMenu>
    <ContextMenuTrigger as-child>
      <div
        v-bind="longPressHandlers"
        class="contents"
      >
        <slot />
      </div>
    </ContextMenuTrigger>
    <ContextMenuContent class="w-56">
      <ContextMenuLabel class="text-xs">Действия с записью</ContextMenuLabel>
      <ContextMenuSeparator />
      <ContextMenuItem @click="emit('edit')">
        <Pencil class="w-4 h-4 mr-2" />
        Редактировать
        <ContextMenuShortcut>Enter</ContextMenuShortcut>
      </ContextMenuItem>
      <ContextMenuItem @click="emit('duplicate')">
        <Copy class="w-4 h-4 mr-2" />
        Дублировать
        <ContextMenuShortcut>Ctrl+D</ContextMenuShortcut>
      </ContextMenuItem>
      <ContextMenuSeparator />
      <ContextMenuItem
        class="text-red-600 focus:text-red-600 focus:bg-red-50"
        @click="emit('delete')"
      >
        <Trash2 class="w-4 h-4 mr-2" />
        Удалить
        <ContextMenuShortcut>Del</ContextMenuShortcut>
      </ContextMenuItem>
    </ContextMenuContent>
  </ContextMenu>

  <!-- Mobile: long-press bottom sheet -->
  <Sheet :open="isMobileMenuOpen" @update:open="isMobileMenuOpen = $event">
    <SheetContent side="bottom" class-name="rounded-t-2xl">
      <SheetHeader>
        <SheetTitle class="text-sm">Действия с записью</SheetTitle>
      </SheetHeader>
      <div class="py-2 space-y-1">
        <button
          @click="isMobileMenuOpen = false; emit('edit')"
          class="flex items-center gap-3 w-full px-4 py-3 text-sm text-slate-700 hover:bg-slate-50 rounded-lg transition-colors"
        >
          <Pencil class="w-5 h-5 text-slate-500" />
          Редактировать
        </button>
        <button
          @click="isMobileMenuOpen = false; emit('duplicate')"
          class="flex items-center gap-3 w-full px-4 py-3 text-sm text-slate-700 hover:bg-slate-50 rounded-lg transition-colors"
        >
          <Copy class="w-5 h-5 text-slate-500" />
          Дублировать
        </button>
        <div class="border-t border-slate-100 my-1"></div>
        <button
          @click="isMobileMenuOpen = false; emit('delete')"
          class="flex items-center gap-3 w-full px-4 py-3 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors"
        >
          <Trash2 class="w-5 h-5" />
          Удалить
        </button>
      </div>
    </SheetContent>
  </Sheet>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Pencil, Copy, Trash2 } from 'lucide-vue-next'
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuLabel,
  ContextMenuSeparator,
  ContextMenuShortcut,
  ContextMenuTrigger,
} from '~/components/ui/context-menu'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '~/components/ui/sheet'
import { useLongPress } from '~/composables/useLongPress'

const emit = defineEmits<{
  (e: 'edit'): void
  (e: 'duplicate'): void
  (e: 'delete'): void
}>()

const isMobileMenuOpen = ref(false)

const { onTouchstart, onTouchend, onTouchmove, onTouchcancel } = useLongPress({
  delay: 500,
  onLongPress: () => {
    isMobileMenuOpen.value = true
  },
})

const longPressHandlers = computed(() => ({
  onTouchstart,
  onTouchend,
  onTouchmove,
  onTouchcancel,
}))
</script>
