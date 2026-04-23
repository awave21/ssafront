<template>
  <DialogPortal>
    <DialogOverlay
      v-if="!hideOverlay"
      class="fixed inset-0 z-[10000] bg-black/40 backdrop-blur-sm data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:pointer-events-none"
    />
    <DialogContent
      :class="[
        'fixed z-[10001] bg-white shadow-xl flex flex-col',
        'outline-none ring-0 focus:outline-none focus-visible:outline-none focus-visible:ring-0',
        'duration-300 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:pointer-events-none',
        sideClasses,
        className
      ]"
      @open-auto-focus="onOpenAutoFocus"
      @close-auto-focus="onCloseAutoFocus"
      @pointer-down-outside="onInteractOutside"
      @interact-outside="onInteractOutside"
      @focus-outside="onFocusOutside"
      v-bind="{ ...forwarded, ...$attrs }"
    >
      <slot />
    </DialogContent>
  </DialogPortal>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  type DialogContentEmits,
  type DialogContentProps,
  DialogContent,
  DialogOverlay,
  DialogPortal,
  useForwardPropsEmits,
} from 'radix-vue'
import { clearStaleBodyPointerAndOverflow } from '~/utils/bodyPointerFix'

type SheetSide = 'top' | 'bottom' | 'left' | 'right'

const props = withDefaults(defineProps<DialogContentProps & { side?: SheetSide; className?: string; hideOverlay?: boolean }>(), {
  side: 'right',
  className: '',
  hideOverlay: false,
})

const emits = defineEmits<DialogContentEmits>()
const forwarded = useForwardPropsEmits(props, emits)

/** Без автофокуса Radix не попадает на первый фокусируемый узел (часто кнопка закрытия) — без кольца вокруг крестика при открытии. */
const onOpenAutoFocus = (e: Event) => {
  e.preventDefault()
}

/** После закрытия принудительно чистим body-стили, застрявшие при открытии из dropdown (reka-ui + radix-vue). */
const onCloseAutoFocus = (e: Event) => {
  e.preventDefault()
  clearStaleBodyPointerAndOverflow()
}

/**
 * Sheet (radix-vue Dialog, modal=false) считает любой клик вне своего контента «outside»
 * и закрывается. Поповеры/селекты/дропдауны/тултипы открываются в портале <body> и формально
 * лежат рядом с Sheet, поэтому клик по их пунктам закрывает Sheet до того, как сработает
 * `@select` в Listbox/CommandItem (см. фильтры услуг/сотрудников в инспекторе узла потока).
 *
 * Решение: если событие пришло из любого reka-ui/radix-vue popper-портала — не закрываем Sheet.
 * `data-radix-popper-content-wrapper` ставит radix-vue, `[data-reka-popper-content-wrapper]` —
 * reka-ui; селекторы внизу покрывают оба.
 */
const PORTAL_GUARDS = [
  '[data-radix-popper-content-wrapper]',
  '[data-reka-popper-content-wrapper]',
  '[data-radix-popover-content]',
  '[data-radix-dropdown-menu-content]',
  '[data-radix-select-content]',
  '[data-radix-context-menu-content]',
  '[data-radix-tooltip-content]',
  '[data-radix-hover-card-content]',
  '[data-reka-popover-content]',
  '[data-reka-dropdown-menu-content]',
  '[data-reka-select-content]',
  '[data-reka-context-menu-content]',
  '[data-reka-tooltip-content]',
  '[data-reka-hover-card-content]',
  '[data-reka-listbox-content]',
  '[data-sonner-toaster]',
].join(',')

const isClickInsidePortal = (target: EventTarget | null): boolean => {
  if (!(target instanceof Element)) return false
  return Boolean(target.closest(PORTAL_GUARDS))
}

const onInteractOutside = (e: Event & { detail?: { originalEvent?: Event } }) => {
  const original = e.detail?.originalEvent
  const target = (original?.target as EventTarget | null) ?? (e.target as EventTarget | null)
  if (isClickInsidePortal(target))
    e.preventDefault()
}

const onFocusOutside = (e: Event) => {
  if (isClickInsidePortal(e.target))
    e.preventDefault()
}

const sideClasses = computed(() => {
  const base: Record<SheetSide, string> = {
    right: 'right-0 top-0 bottom-0 w-full data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right',
    left: 'left-0 top-0 bottom-0 w-full data-[state=closed]:slide-out-to-left data-[state=open]:slide-in-from-left',
    top: 'top-0 left-0 right-0 data-[state=closed]:slide-out-to-top data-[state=open]:slide-in-from-top',
    bottom: 'bottom-0 left-0 right-0 data-[state=closed]:slide-out-to-bottom data-[state=open]:slide-in-from-bottom',
  }
  return base[props.side]
})
</script>
