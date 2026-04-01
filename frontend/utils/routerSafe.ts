import type { RouteLocationRaw } from 'vue-router'

/** Тип без импорта `Router` из пакета — избегаем конфликта типов Nuxt/vue-router. */
type RouterNav = {
  replace: (to: RouteLocationRaw) => Promise<unknown>
  push: (to: RouteLocationRaw) => Promise<unknown>
}

const IGNORABLE_NAV_ERRORS = new Set([
  'NavigationDuplicated',
  'NavigationCancelled',
  'NavigationAborted',
])

/**
 * router.replace отклоняет промис при дублировании маршрута или отмене навигации —
 * из‑за этого падают useAsyncData / setup и появляются «ошибки перехода».
 */
function swallowIgnorableNav(err: unknown): boolean {
  const name =
    err && typeof err === 'object' && 'name' in err && typeof (err as { name: unknown }).name === 'string'
      ? (err as { name: string }).name
      : ''
  return IGNORABLE_NAV_ERRORS.has(name)
}

export async function routerReplaceSafe(router: RouterNav, to: RouteLocationRaw): Promise<void> {
  try {
    await router.replace(to)
  } catch (err: unknown) {
    if (swallowIgnorableNav(err)) return
    throw err
  }
}

export async function routerPushSafe(router: RouterNav, to: RouteLocationRaw): Promise<void> {
  try {
    await router.push(to)
  } catch (err: unknown) {
    if (swallowIgnorableNav(err)) return
    throw err
  }
}
