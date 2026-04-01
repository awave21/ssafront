/**
 * Reka UI (dropdown) + Radix Vue (dialog/sheet) иногда оставляют на document.body
 * pointer-events: none / overflow после закрытия — страница перестаёт реагировать на клики.
 */
export const clearStaleBodyPointerAndOverflow = () => {
  if (!import.meta.client) return
  const run = () => {
    document.body.style.removeProperty('pointer-events')
    document.body.style.removeProperty('overflow')
  }
  requestAnimationFrame(() => {
    run()
    requestAnimationFrame(run)
  })
  setTimeout(run, 0)
  setTimeout(run, 100)
}
