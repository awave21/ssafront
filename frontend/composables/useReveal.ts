import { onMounted, onBeforeUnmount, ref } from 'vue'

export function useReveal(options: IntersectionObserverInit = { threshold: 0.18, rootMargin: '0px 0px -8% 0px' }) {
  const el = ref<HTMLElement | null>(null)
  const isVisible = ref(false)
  let observer: IntersectionObserver | null = null

  onMounted(() => {
    if (!el.value || typeof IntersectionObserver === 'undefined') {
      isVisible.value = true
      return
    }
    observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          isVisible.value = true
          observer?.disconnect()
          break
        }
      }
    }, options)
    observer.observe(el.value)
  })

  onBeforeUnmount(() => {
    observer?.disconnect()
    observer = null
  })

  return { el, isVisible }
}
