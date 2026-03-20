import { ref, onUnmounted } from 'vue'

export type LongPressOptions = {
  delay?: number
  onLongPress: () => void
}

/**
 * Composable for detecting long-press / touch-hold on mobile.
 * Returns an object with event handlers to attach to an element.
 */
export const useLongPress = (options: LongPressOptions) => {
  const { delay = 500, onLongPress } = options
  const timer = ref<ReturnType<typeof setTimeout> | null>(null)
  const isLongPressing = ref(false)

  const start = (e: TouchEvent | MouseEvent) => {
    isLongPressing.value = false
    timer.value = setTimeout(() => {
      isLongPressing.value = true
      // Prevent context menu on mobile after long-press fires
      onLongPress()
    }, delay)
  }

  const cancel = () => {
    if (timer.value) {
      clearTimeout(timer.value)
      timer.value = null
    }
  }

  const onTouchEnd = (e: TouchEvent) => {
    if (isLongPressing.value) {
      // Prevent the click that follows a long-press
      e.preventDefault()
    }
    cancel()
    isLongPressing.value = false
  }

  onUnmounted(cancel)

  return {
    onTouchstart: start,
    onTouchend: onTouchEnd,
    onTouchmove: cancel,
    onTouchcancel: cancel,
    isLongPressing,
  }
}
