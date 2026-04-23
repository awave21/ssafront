<template>
  <div class="space-y-1">
    <label class="insp-label">{{ label }}</label>
    <Popover v-model:open="open">
      <PopoverTrigger as-child>
        <Button
          type="button"
          variant="outline"
          role="combobox"
          :aria-expanded="open"
          size="sm"
          :class="cn(
            'insp-input h-auto min-h-9 w-full justify-between px-2.5 py-2 font-normal shadow-none hover:bg-background',
          )"
        >
          <span class="truncate text-left text-[11px] leading-snug">{{ summary }}</span>
          <ChevronsUpDown class="ml-2 size-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent class="w-[min(100vw-2rem,320px)] p-0 sm:w-[320px]" align="start">
        <Command>
          <CommandInput class="text-xs" :placeholder="searchPlaceholder ?? 'Поиск…'" />
          <CommandEmpty class="text-xs">{{ emptyHint }}</CommandEmpty>
          <CommandList class="max-h-[220px]">
            <CommandGroup>
              <CommandItem
                v-for="opt in options"
                :key="opt.id"
                class="text-xs"
                :value="opt.id"
                @select="() => onItemSelect(opt.id)"
              >
                <Check
                  :class="cn(
                    'mr-2 size-4 shrink-0',
                    selectedIds.includes(opt.id) ? 'opacity-100' : 'opacity-0',
                  )"
                />
                {{ opt.name }}
              </CommandItem>
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
    <p v-if="!options.length" class="text-[10px] text-muted-foreground">{{ noDataHint }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Check, ChevronsUpDown } from 'lucide-vue-next'
import { Button } from '~/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '~/components/ui/popover'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '~/components/ui/command'
import { cn } from '~/lib/utils'

type Option = { id: string; name: string }

const props = withDefaults(
  defineProps<{
    options: Option[]
    selectedIds: string[]
    label: string
    searchPlaceholder?: string
    emptyHint?: string
    noDataHint?: string
  }>(),
  {
    emptyHint: 'Ничего не найдено',
    noDataHint: 'Нет данных SQNS',
  },
)

const emit = defineEmits<{
  toggle: [id: string]
}>()

const open = ref(false)

const summary = computed(() => {
  const n = props.selectedIds.length
  if (n === 0) return 'Не выбрано — любые'
  if (n <= 2) {
    const names = props.selectedIds
      .map((id) => props.options.find((o) => o.id === id)?.name)
      .filter(Boolean) as string[]
    return names.join(', ')
  }
  return `Выбрано: ${n}`
})

const onItemSelect = (id: string) => {
  emit('toggle', id)
}
</script>
