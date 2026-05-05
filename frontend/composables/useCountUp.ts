import { onBeforeUnmount, onMounted, ref } from 'vue'

interface CountUpOptions {
  to: number
  from?: number
  durationMs?: number
  decimals?: number
  start?: 'mount' | 'visible'
}

const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3)

export function useCountUp(opts: CountUpOptions) {
  const { to, from = 0, durationMs = 1400, decimals = 0, start = 'visible' } = opts
  const value = ref<number>(from)
  const el = ref<HTMLElement | null>(null)
  let raf = 0
  let observer: IntersectionObserver | null = null
  let started = false

  const begin = () => {
    if (started) return
    started = true
    if (typeof window === 'undefined') {
      value.value = to
      return
    }
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduced) {
      value.value = to
      return
    }
    const startTs = performance.now()
    const tick = (now: number) => {
      const t = Math.min(1, (now - startTs) / durationMs)
      const eased = easeOutCubic(t)
      const raw = from + (to - from) * eased
      value.value = decimals === 0 ? Math.round(raw) : Number(raw.toFixed(decimals))
      if (t < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
  }

  onMounted(() => {
    if (start === 'mount' || typeof IntersectionObserver === 'undefined' || !el.value) {
      begin()
      return
    }
    observer = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            begin()
            observer?.disconnect()
            break
          }
        }
      },
      { threshold: 0.4 }
    )
    observer.observe(el.value)
  })

  onBeforeUnmount(() => {
    cancelAnimationFrame(raf)
    observer?.disconnect()
  })

  return { value, el }
}
