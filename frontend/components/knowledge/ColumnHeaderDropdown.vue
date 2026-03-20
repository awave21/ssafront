<template>
  <DropdownMenu>
    <TooltipProvider :delay-duration="500">
      <Tooltip>
        <TooltipTrigger as-child>
          <DropdownMenuTrigger as-child>
            <div
              class="flex items-center gap-1 cursor-pointer group hover:bg-slate-50 -mx-2 px-2 py-1 rounded transition-colors w-full"
              draggable="true"
              @dragstart="$emit('dragstart', $event)"
            >
              <GripVertical class="w-3 h-3 text-slate-300 group-hover:text-slate-500 shrink-0" />
              <span class="select-none truncate flex-1 text-left">{{ column.label }}</span>
              <span v-if="column.type !== 'text'" class="text-[10px] text-slate-400 font-mono shrink-0">
                {{ typeLabel }}
              </span>
              <ChevronDown class="w-3 h-3 text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
            </div>
          </DropdownMenuTrigger>
        </TooltipTrigger>
        <TooltipContent side="top" :side-offset="8">
          <p class="text-xs">
            <span class="font-medium">{{ column.label }}</span>
            <span class="text-muted-foreground ml-1">({{ column.name }})</span>
          </p>
          <p class="text-xs text-muted-foreground mt-0.5">
            {{ typeFull }}
            <span v-if="column.required"> &bull; &nbsp;&#1086;&#1073;&#1103;&#1079;&#1072;&#1090;&#1077;&#1083;&#1100;&#1085;&#1086;&#1077;</span>
            <span v-if="column.searchable"> &bull; &nbsp;&#1087;&#1086;&#1080;&#1089;&#1082;</span>
          </p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
    <DropdownMenuContent align="start" class="w-52">
      <DropdownMenuLabel class="text-xs">
        Столбец "{{ column.label }}"
        <span class="font-mono text-slate-400 ml-1 font-normal">{{ column.name }}</span>
      </DropdownMenuLabel>
      <DropdownMenuSeparator />
      <DropdownMenuItem @click="$emit('edit')">
        <Settings class="w-4 h-4 mr-2" />
        Настройки столбца
      </DropdownMenuItem>
      <DropdownMenuItem @click="$emit('hide')">
        <EyeOff class="w-4 h-4 mr-2" />
        Скрыть столбец
        <DropdownMenuShortcut>H</DropdownMenuShortcut>
      </DropdownMenuItem>
      <DropdownMenuSeparator />
      <DropdownMenuItem
        :disabled="isOnlyColumn"
        class="text-red-600 focus:text-red-600 focus:bg-red-50"
        @click="$emit('delete')"
      >
        <Trash2 class="w-4 h-4 mr-2" />
        Удалить столбец
      </DropdownMenuItem>
    </DropdownMenuContent>
  </DropdownMenu>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { GripVertical, ChevronDown, Settings, EyeOff, Trash2 } from 'lucide-vue-next'
import type { DirectoryColumn } from '~/types/directories'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuTrigger,
} from '~/components/ui/dropdown-menu'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '~/components/ui/tooltip'

const props = defineProps<{
  column: DirectoryColumn
  isOnlyColumn?: boolean
}>()

defineEmits<{
  (e: 'dragstart', event: DragEvent): void
  (e: 'edit'): void
  (e: 'hide'): void
  (e: 'delete'): void
}>()

const TYPE_LABELS: Record<string, string> = {
  text: 'Aa',
  number: '#',
  date: '\uD83D\uDCC5',
  bool: '\u2611',
}

const TYPE_FULL: Record<string, string> = {
  text: '\u0422\u0435\u043A\u0441\u0442',
  number: '\u0427\u0438\u0441\u043B\u043E',
  date: '\u0414\u0430\u0442\u0430',
  bool: '\u0414\u0430/\u041D\u0435\u0442',
}

const typeLabel = computed(() => TYPE_LABELS[props.column.type] ?? props.column.type)
const typeFull = computed(() => TYPE_FULL[props.column.type] ?? props.column.type)
</script>
