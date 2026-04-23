<template>
  <Popover v-model:open="open">
    <PopoverTrigger as-child>
      <Button
        type="button"
        variant="outline"
        role="combobox"
        :aria-expanded="open"
        size="sm"
        :disabled="disabled || !options.length"
        :class="cn(
          'insp-input h-auto min-h-9 w-full justify-between px-2.5 py-2 font-normal shadow-none hover:bg-background',
        )"
      >
        <span class="truncate text-left text-[11px] leading-snug">{{ displayLabel }}</span>
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
              @select="() => pick(opt.id)"
            >
              <Check
                :class="cn(
                  'mr-2 size-4 shrink-0',
                  modelValue === opt.id ? 'opacity-100' : 'opacity-0',
                )"
              />
              {{ opt.name }}
            </CommandItem>
          </CommandGroup>
        </CommandList>
      </Command>
    </PopoverContent>
  </Popover>
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
    modelValue: string
    options: Option[]
    disabled?: boolean
    searchPlaceholder?: string
    emptyHint?: string
  }>(),
  {
    emptyHint: 'Ничего не найдено',
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
  picked: []
}>()

const open = ref(false)

const displayLabel = computed(() => {
  if (!props.modelValue?.trim()) return '— Выбрать —'
  const row = props.options.find((o) => o.id === props.modelValue)
  return row?.name ?? props.modelValue
})

const pick = (id: string) => {
  emit('update:modelValue', id)
  emit('picked')
  open.value = false
}
</script>
