---
name: analytics-page-style
description: Applies the same visual language as the Analytics page (dashboard layout, cards, tabs, filters, charts). Use when building or restyling dashboard-style pages, KPI grids, analytics-like sections, or when the user asks to match the analytics / аналитика look.
---

# Analytics page visual style

Reference implementation: `frontend/pages/analytics.vue` and `frontend/components/analytics/*`; chart blocks reuse `frontend/components/ChartCard.vue`.

## Page shell

- Full-width column: `w-full px-4 py-10 flex flex-col gap-8 bg-[#f8fafc] min-h-screen`
- Inner container: `max-w-7xl mx-auto w-full` with vertical rhythm `space-y-10` (or `gap-8` / `gap-10` between major blocks)

## Tabs (segmented control)

- List: `bg-white border border-slate-100 p-1.5 rounded-3xl shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] mb-10 h-14 w-fit`
- Trigger: `rounded-2xl px-10 h-full font-bold text-sm transition-all`
- Active: `data-[state=active]:bg-primary data-[state=active]:text-white data-[state=active]:shadow-lg data-[state=active]:shadow-primary/20`

## Cards and panels

Default “analytics card”:

- `bg-white rounded-3xl border border-slate-100 p-6` or `p-8` for chart-sized blocks
- Shadow: `shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]`
- Hover (interactive): `transition-all duration-300` (or `duration-500` for large blocks) with `hover:-translate-y-1` or `hover:-translate-y-1.5` and stronger shadow `hover:shadow-[0_12px_24px_-8px_rgba(0,0,0,0.08)]` or `hover:shadow-[0_20px_40px_-12px_rgba(0,0,0,0.08)]`
- Wrapper: `group relative … overflow-hidden`

Decorative accent (optional, matches KPI and chart cards):

- Absolutely positioned circle: e.g. `absolute -right-4 -bottom-4 h-16 w-16 rounded-full bg-slate-50` (or `-right-8 -top-8 h-32 w-32` on large cards)
- Hover: `group-hover:scale-150 group-hover:bg-primary/5` (or `group-hover:bg-emerald-500/5` for a green variant)
- Content above accent: `relative z-10`

## Typography

- Section label (eyebrow): `text-sm font-bold uppercase tracking-widest text-slate-400` — sometimes `font-black` for stronger hierarchy
- Small field labels (filters): `text-[10px] font-black uppercase tracking-widest text-slate-400`
- Card meta / KPI title: `text-[10px] font-bold uppercase tracking-wider text-slate-400` with `group-hover:text-slate-600`
- Card title (in-chart): `text-lg font-bold text-slate-900 tracking-tight` with `group-hover:text-primary transition-colors`
- Subtitle under title: `text-[10px] font-bold text-slate-400 uppercase tracking-widest`
- Primary metric: `text-2xl font-black text-slate-900 tracking-tight` with optional `group-hover:text-primary`
- Supporting text: `text-[10px]` or `text-xs` `text-slate-400 font-medium`

## Forms (filter bar pattern)

- Panel: same white `rounded-3xl` card as above with `p-6`
- Inputs / triggers: `h-11 bg-slate-50/50 border-slate-100 rounded-xl focus:ring-2 focus:ring-primary/20 transition-all`
- Primary button: `bg-primary hover:bg-primary/90 shadow-lg shadow-primary/20 rounded-xl font-bold text-xs h-11 active:scale-95`
- Ghost secondary: `variant="ghost"` with `text-slate-400 hover:bg-slate-50 hover:text-slate-900 rounded-xl font-bold text-xs`
- Section dividers inside panel: `border-t border-slate-100 mt-6 pt-6`

## Color semantics

- Positive / success: `emerald-50` / `emerald-500` / `emerald-600` (badges, dots, positive diffs)
- Negative / error: `rose-50` / `rose-500` / `rose-600` (alerts, negative diffs)
- Primary actions and highlights: `primary` with `shadow-primary/20` where shadows are used
- Muted UI: `slate-50`, `slate-100`, `slate-400`, `slate-600`, `slate-900`

## Icon treatment

- KPI / chart header icon box: `flex h-7 w-7` or `h-10 w-10 items-center justify-center rounded-lg` or `rounded-xl bg-slate-50 text-slate-400 group-hover:bg-primary/10 group-hover:text-primary transition-colors`
- Use `lucide-vue-next` icons consistently with analytics components

## Grids and spacing

- Vertical stacks: `space-y-6` within a section, `space-y-10` between filter bar and content
- KPI grids: `grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5` (adjust column count per layout)
- Chart grids: `grid grid-cols-1 gap-6 lg:grid-cols-2` or `lg:grid-cols-3` for breakdown columns

## Loading and empty states

- Skeletons: `rounded-3xl bg-white border-none shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]` (height per slot)
- Empty: `bg-white rounded-2xl border border-dashed border-slate-200` centered content, `text-sm font-medium text-slate-400`

## Secondary panels

- Soft informational blocks: `rounded-3xl border border-slate-100 bg-white/50 p-8 backdrop-blur-sm` with the same light shadow as cards
- Badges in analytics: `rounded-xl`, `border border-slate-100`, `font-bold`, `text-xs`, subtle `shadow-sm`

## Data formatting

- Match analytics: `Intl.NumberFormat('ru-RU', …)` for integers, money (₽), and percents where the UI shows Russian locale

## Checklist before shipping UI

- [ ] Page uses `#f8fafc` background and `max-w-7xl` content width where appropriate
- [ ] Cards use `rounded-3xl` + `border-slate-100` + analytics shadow token
- [ ] Section labels use uppercase tracking + slate-400
- [ ] Primary buttons use primary fill + `shadow-lg shadow-primary/20`
- [ ] Hover lift/shadow matches existing analytics cards
- [ ] Empty and error states follow dashed-card / rose alert patterns from `analytics.vue`

## See also

- `frontend/pages/analytics.vue` — tabs, page layout, error banner, backlog panel
- `frontend/components/analytics/AnalyticsKpiGrid.vue` — KPI card anatomy
- `frontend/components/analytics/AnalyticsFiltersBar.vue` — filter panel
- `frontend/components/ChartCard.vue` — chart container shared with dynamics tab
