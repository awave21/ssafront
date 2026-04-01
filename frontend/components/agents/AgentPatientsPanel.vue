<template>
  <div class="flex w-full flex-col gap-6 md:gap-8 lg:gap-10">
    <Teleport v-if="isMounted" to="#topbar-actions">
      <div class="flex max-w-[min(100vw-8rem,28rem)] flex-wrap items-center justify-end gap-2 sm:max-w-none">
        <Button
          type="button"
          class="h-9 shrink-0 gap-2 rounded-xl bg-primary px-4 text-xs font-bold text-primary-foreground shadow-lg shadow-primary/20 transition-all hover:bg-primary/90 active:scale-95"
          @click="exportCsv"
        >
          <Download class="h-3.5 w-3.5" />
          Экспорт
        </Button>
      </div>
    </Teleport>

    <div class="space-y-4 sm:space-y-6">
      <h2 class="text-sm font-bold uppercase tracking-widest text-slate-400">Ключевые показатели</h2>

      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div
          v-for="card in kpiCards"
          :key="card.label"
          class="group relative overflow-hidden rounded-3xl border border-slate-100 bg-white p-6 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)] transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_12px_24px_-8px_rgba(0,0,0,0.08)]"
        >
          <div
            class="absolute -bottom-4 -right-4 h-16 w-16 rounded-full bg-slate-50 transition-all duration-500 group-hover:scale-150 group-hover:bg-primary/5"
          />
          <div class="relative z-10 flex h-full flex-col">
            <div class="mb-4 flex items-center gap-2">
              <div
                class="flex h-7 w-7 items-center justify-center rounded-lg bg-slate-50 text-slate-400 transition-colors group-hover:bg-primary/10 group-hover:text-primary"
              >
                <component :is="card.icon" class="h-4 w-4" />
              </div>
              <span
                class="text-[10px] font-bold uppercase tracking-wider text-slate-400 transition-colors group-hover:text-slate-600"
              >
                {{ card.label }}
              </span>
            </div>
            <div
              class="font-black tracking-tight text-slate-900 transition-colors group-hover:text-primary"
              :class="card.valueClass ?? 'text-2xl'"
            >
              {{ card.value }}
            </div>
            <p
              class="mt-4 line-clamp-2 text-[10px] font-medium leading-relaxed text-slate-400 transition-colors group-hover:text-slate-500"
            >
              {{ card.hint }}
            </p>
          </div>
        </div>
      </div>
    </div>

    <div class="space-y-4 sm:space-y-6">
      <h2 class="text-sm font-bold uppercase tracking-widest text-slate-400">Список пациентов</h2>

      <Alert v-if="!resolvedAgentId" variant="warning" class="rounded-2xl border-amber-200 bg-amber-50/80">
        <AlertDescription class="text-sm text-amber-900">
          Выберите агента в списке выше — без агента список пациентов недоступен.
        </AlertDescription>
      </Alert>

      <Alert v-else-if="patientsErrorMessage" variant="destructive" class="rounded-2xl">
        <AlertDescription class="text-sm">{{ patientsErrorMessage }}</AlertDescription>
      </Alert>

      <div class="min-h-[320px] overflow-hidden rounded-3xl border border-slate-100 bg-white shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
        <div
          v-if="resolvedAgentId"
          class="border-b border-slate-100 px-4 py-4 sm:px-5"
        >
          <p class="mb-2 text-[10px] font-black uppercase tracking-widest text-slate-400">
            Срез по визитам
          </p>
          <div class="mb-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
            <div class="flex flex-1 flex-col gap-2 sm:min-w-[140px] sm:max-w-[200px]">
              <label class="text-[10px] font-black uppercase tracking-widest text-slate-400">
                С даты
              </label>
              <Input
                :model-value="patientsQuery.visit_date_from"
                type="date"
                class="h-11 rounded-xl border-slate-100 bg-slate-50/50 font-medium text-slate-900 focus-visible:ring-primary/20"
                @update:model-value="onVisitDateFromUpdate"
              />
            </div>
            <div class="flex flex-1 flex-col gap-2 sm:min-w-[140px] sm:max-w-[200px]">
              <label class="text-[10px] font-black uppercase tracking-widest text-slate-400">
                По дату
              </label>
              <Input
                :model-value="patientsQuery.visit_date_to"
                type="date"
                class="h-11 rounded-xl border-slate-100 bg-slate-50/50 font-medium text-slate-900 focus-visible:ring-primary/20"
                @update:model-value="onVisitDateToUpdate"
              />
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              class="h-11 shrink-0 rounded-xl border-slate-200 text-[11px] font-bold sm:mb-0"
              @click="applyMonthToDate"
            >
              С 1-го числа — сегодня
            </Button>
          </div>
          <div class="mb-4 flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              class="h-8 rounded-xl border-slate-200 text-[11px] font-bold"
              :class="!visitFilterActive ? 'border-primary/30 bg-primary/5 text-primary' : ''"
              @click="clearVisitPreset"
            >
              Все пациенты
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              class="h-8 rounded-xl border-slate-200 text-[11px] font-bold"
              :class="cohortActiveClass('primary_bookings')"
              @click="setVisitPreset('primary_bookings')"
            >
              Первичные: записи
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              class="h-8 rounded-xl border-slate-200 text-[11px] font-bold"
              :class="cohortActiveClass('primary_arrived')"
              @click="setVisitPreset('primary_arrived')"
            >
              Первичные: дошли
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              class="h-8 rounded-xl border-slate-200 text-[11px] font-bold"
              :class="cohortActiveClass('repeat_bookings')"
              @click="setVisitPreset('repeat_bookings')"
            >
              Повторные: записи
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              class="h-8 rounded-xl border-slate-200 text-[11px] font-bold"
              :class="cohortActiveClass('repeat_arrived')"
              @click="setVisitPreset('repeat_arrived')"
            >
              Повторные: дошли
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              class="h-8 rounded-xl border-slate-200 text-[11px] font-bold"
              :class="cohortActiveClass('all_bookings')"
              @click="setVisitPreset('all_bookings')"
            >
              Все: записи
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              class="h-8 rounded-xl border-slate-200 text-[11px] font-bold"
              :class="cohortActiveClass('all_arrived')"
              @click="setVisitPreset('all_arrived')"
            >
              Все: дошли
            </Button>
          </div>
          <p v-if="visitPeriodHint" class="mb-4 text-[11px] text-slate-500">{{ visitPeriodHint }}</p>

          <div v-if="visitFilterActive" class="mb-4 max-w-md">
            <label class="mb-2 block text-[10px] font-black uppercase tracking-widest text-slate-400">
              Сотрудник
            </label>
            <Select
              :model-value="patientsQuery.resource_external_id === null ? '__all__' : String(patientsQuery.resource_external_id)"
              @update:model-value="onPatientResourceChange"
            >
              <SelectTrigger
                class="h-11 w-full rounded-xl border-slate-100 bg-slate-50/50 focus:ring-2 focus:ring-primary/20"
              >
                <SelectValue placeholder="Все сотрудники" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">Все сотрудники</SelectItem>
                <SelectItem v-for="r in patientResources" :key="r.id" :value="String(r.id)">
                  {{ r.name }}
                </SelectItem>
              </SelectContent>
            </Select>
            <p class="mt-2 text-[11px] text-slate-500">
              Учитываются только визиты выбранного специалиста в этом срезе.
            </p>
          </div>

          <label class="mb-2 block text-[10px] font-black uppercase tracking-widest text-slate-400">
            Поиск
          </label>
          <div class="relative max-w-2xl">
            <Search
              class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400"
              aria-hidden="true"
            />
            <Input
              v-model="patientsQuery.search"
              type="search"
              placeholder="Имя, телефон, ID (PT-…) или тег…"
              class="h-11 rounded-xl border-slate-100 bg-slate-50/50 pl-10 transition-all focus-visible:ring-2 focus-visible:ring-primary/20"
              autocomplete="off"
            />
          </div>

          <div class="mt-4 rounded-2xl border border-slate-100 bg-slate-50/40 px-3 py-4 sm:px-4">
            <p class="mb-1 text-[10px] font-black uppercase tracking-widest text-slate-400">
              Фильтры выручки
            </p>
            <p
              v-if="!visitFilterActive"
              class="mb-3 text-[11px] leading-relaxed text-slate-500"
            >
              Выберите период и сегмент визитов выше — тогда отмеченные опции будут влиять на колонку «За период» и карточку выручки. Значения в URL сохраняются заранее.
            </p>

            <div class="flex flex-wrap items-center gap-x-6 gap-y-2">
              <span class="w-full text-[10px] font-black uppercase tracking-widest text-slate-400 sm:w-auto">
                Способ оплаты
              </span>
              <label
                v-for="option in PAYMENT_METHOD_OPTIONS"
                :key="option.value"
                class="flex cursor-pointer items-center gap-2 select-none"
                @click.prevent="togglePaymentMethod(option.value)"
              >
                <span
                  class="flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-all"
                  :class="isPaymentMethodSelected(option.value)
                    ? 'border-primary bg-primary text-white'
                    : 'border-slate-300 bg-white'"
                >
                  <svg
                    v-if="isPaymentMethodSelected(option.value)"
                    viewBox="0 0 10 8"
                    class="h-2.5 w-2.5 fill-none stroke-current stroke-[1.8]"
                  >
                    <polyline points="1,4 3.5,6.5 9,1" />
                  </svg>
                </span>
                <span class="text-sm font-medium text-slate-700">{{ option.label }}</span>
              </label>
            </div>
            <p class="mt-2 text-[11px] text-slate-500">
              Все отмечены — по сумме визитов; снимите лишнее — только платежи выбранных способов.
            </p>

            <div class="mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-slate-100/80 pt-4">
              <span class="w-full text-[10px] font-black uppercase tracking-widest text-slate-400 sm:w-auto">
                Тип выручки
              </span>
              <label
                v-for="option in REVENUE_CATEGORY_OPTIONS"
                :key="option.value"
                class="flex cursor-pointer items-center gap-2 select-none"
                @click.prevent="toggleRevenueCategory(option.value)"
              >
                <span
                  class="flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-all"
                  :class="isRevenueCategorySelected(option.value)
                    ? 'border-primary bg-primary text-white'
                    : 'border-slate-300 bg-white'"
                >
                  <svg
                    v-if="isRevenueCategorySelected(option.value)"
                    viewBox="0 0 10 8"
                    class="h-2.5 w-2.5 fill-none stroke-current stroke-[1.8]"
                  >
                    <polyline points="1,4 3.5,6.5 9,1" />
                  </svg>
                </span>
                <span class="text-sm font-medium text-slate-700">{{ option.label }}</span>
              </label>
            </div>
            <p class="mt-2 text-[11px] text-slate-500">
              Услуги / товары по типу оплаты SQNS; все отмечены — без ограничения по типу.
            </p>
          </div>
        </div>
        <div class="overflow-x-auto">
          <Table
            wrapper-class="rounded-none border-0 bg-transparent shadow-none"
          >
            <TableHeader>
              <TableRow class-name="border-b border-slate-100 hover:bg-transparent">
                <TableHead class-name="whitespace-nowrap py-4">Пациент</TableHead>
                <TableHead class-name="whitespace-nowrap py-4">Визит</TableHead>
                <TableHead class-name="whitespace-nowrap py-4">Услуга</TableHead>
                <TableHead class-name="whitespace-nowrap py-4">За визит</TableHead>
                <TableHead class-name="whitespace-nowrap py-4">
                  {{ visitFilterActive ? 'Визитов (период)' : 'Визитов' }}
                </TableHead>
                <TableHead class-name="whitespace-nowrap py-4">
                  {{ visitFilterActive ? 'За период' : 'Всего' }}
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <template v-if="pending && !displayRows.length">
                <TableRow
                  v-for="sk in 8"
                  :key="`sk-${sk}`"
                  class-name="border-b border-slate-50 hover:bg-transparent"
                >
                  <TableCell v-for="c in 6" :key="c" class-name="py-4">
                    <Skeleton class="h-8 w-full max-w-[8rem] rounded-lg" />
                  </TableCell>
                </TableRow>
              </template>
              <template v-else>
                <TableRow
                  v-for="row in displayRows"
                  :key="row.id"
                  class-name="group/row border-b border-slate-50 cursor-pointer transition-colors last:border-0 hover:bg-slate-50/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary/25"
                  :class="row.highlighted ? '!bg-sky-50/60' : ''"
                  role="button"
                  tabindex="0"
                  :aria-label="`Открыть карточку: ${row.name}`"
                  @click="openPatient(row)"
                  @keydown.enter.prevent="openPatient(row)"
                  @keydown.space.prevent="openPatient(row)"
                >
                  <TableCell class-name="min-w-[220px] py-4 align-middle">
                    <div class="flex min-w-0 items-center gap-3">
                      <div
                        class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-[10px] font-black text-slate-400 transition-all group-hover/row:bg-primary group-hover/row:text-white"
                      >
                        {{ row.initials }}
                      </div>
                      <div class="min-w-0">
                        <div class="truncate text-sm font-bold text-slate-900">{{ row.name }}</div>
                        <p class="truncate text-[10px] font-bold uppercase tracking-tight text-slate-400">
                          {{ row.phone }} · ID {{ row.externalId }}
                        </p>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell class-name="min-w-[140px] align-middle">
                    <div class="text-sm font-bold text-slate-900">{{ row.visitDate }}</div>
                    <p class="text-[10px] font-bold uppercase tracking-tight text-slate-400">
                      {{ row.visitRelative }}
                    </p>
                  </TableCell>
                  <TableCell class-name="min-w-[130px] align-middle">
                    <div class="text-sm font-bold text-slate-900">{{ row.serviceName }}</div>
                    <p class="text-[10px] font-bold uppercase tracking-tight text-slate-400">
                      {{ row.serviceDetail }}
                    </p>
                  </TableCell>
                  <TableCell class-name="min-w-[110px] align-middle text-sm font-black text-slate-900">
                    {{ row.visitRevenueRub == null ? '—' : formatRub(row.visitRevenueRub) }}
                  </TableCell>
                  <TableCell class-name="min-w-[100px] align-middle text-sm font-bold text-slate-900">
                    {{ row.visitsCount }}
                  </TableCell>
                  <TableCell class-name="min-w-[120px] align-middle text-sm font-black text-slate-900">
                    {{ formatRub(row.revenueRub) }}
                  </TableCell>
                </TableRow>
              </template>
              <TableRow
                v-if="resolvedAgentId && !pending && !displayRows.length"
                class-name="hover:bg-transparent"
              >
                <TableCell colspan="6" class-name="py-12 text-center">
                  <p class="text-sm font-medium text-slate-400">Ничего не найдено по запросу.</p>
                </TableCell>
              </TableRow>
            </TableBody>
            <TableFooter v-if="tableTotalsVisible">
              <TableRow class-name="border-t border-slate-200 bg-slate-50/90 hover:bg-slate-50/90">
                <TableCell class-name="py-3 text-sm font-black text-slate-900">Итого</TableCell>
                <TableCell class-name="py-3 text-sm text-slate-400">—</TableCell>
                <TableCell class-name="py-3 text-sm text-slate-400">—</TableCell>
                <TableCell class-name="py-3 text-sm font-black text-slate-900">
                  {{
                    patientsLastVisitTotalPriceSum == null
                      ? '—'
                      : formatRub(patientsLastVisitTotalPriceSum)
                  }}
                </TableCell>
                <TableCell class-name="py-3 text-sm font-black text-slate-900">
                  {{
                    visitFilterActive
                      ? (patientsSliceVisitCount == null ? '—' : patientsSliceVisitCount.toLocaleString('ru-RU'))
                      : (patientsVisitsCountSum == null ? '—' : patientsVisitsCountSum.toLocaleString('ru-RU'))
                  }}
                </TableCell>
                <TableCell class-name="py-3 text-sm font-black text-slate-900">
                  {{
                    visitFilterActive
                      ? (patientsRevenueTotal == null ? '—' : formatRub(patientsRevenueTotal))
                      : (patientsTotalArrivalSum == null ? '—' : formatRub(patientsTotalArrivalSum))
                  }}
                </TableCell>
              </TableRow>
            </TableFooter>
          </Table>
        </div>

        <div
          class="flex flex-col gap-3 border-t border-slate-100 bg-slate-50/50 px-5 py-4 sm:flex-row sm:items-center sm:justify-between"
        >
          <p class="text-xs font-medium text-slate-500 sm:max-w-[70%]">
            <template v-if="resolvedAgentId">
              Показано {{ rangeLabel }}
            </template>
            <template v-else> Выберите агента, чтобы загрузить список. </template>
          </p>
          <div class="flex shrink-0 gap-2">
            <Button
              variant="ghost"
              size="sm"
              class="h-9 rounded-xl text-xs font-bold text-slate-400 hover:bg-white hover:text-slate-900"
              type="button"
              :disabled="!resolvedAgentId || pending || patientsQuery.offset === 0"
              @click="setPatientsPage(currentPage - 1)"
            >
              Назад
            </Button>
            <Button
              variant="ghost"
              size="sm"
              class="h-9 rounded-xl text-xs font-bold text-slate-400 hover:bg-white hover:text-slate-900"
              type="button"
              :disabled="!resolvedAgentId || pending || !patientsHasMore"
              @click="setPatientsPage(currentPage + 1)"
            >
              Вперёд
            </Button>
          </div>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import type { Component } from 'vue'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { CalendarRange, Download, Search, Stethoscope, Users, Wallet } from 'lucide-vue-next'
import { Alert, AlertDescription } from '~/components/ui/alert'
import Button from '~/components/ui/button/Button.vue'
import Input from '~/components/ui/input/Input.vue'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '~/components/ui/select'
import Skeleton from '~/components/ui/skeleton/Skeleton.vue'
import Table from '~/components/ui/table/Table.vue'
import TableBody from '~/components/ui/table/TableBody.vue'
import TableCell from '~/components/ui/table/TableCell.vue'
import TableHead from '~/components/ui/table/TableHead.vue'
import TableHeader from '~/components/ui/table/TableHeader.vue'
import TableFooter from '~/components/ui/table/TableFooter.vue'
import TableRow from '~/components/ui/table/TableRow.vue'
import { useAnalyticsApi } from '~/composables/analyticsApi'
import { usePatients } from '~/composables/usePatients'
import type { AnalyticsPaymentMethod, AnalyticsResourceOption, AnalyticsRevenueCategory } from '~/types/analytics'
import type { PatientDirectoryRow, PatientsVisitCohort, SqnsClientListItem } from '~/types/patient-directory'
import { getReadableErrorMessage } from '~/utils/api-errors'
import { routerReplaceSafe } from '~/utils/routerSafe'

const props = withDefaults(
  defineProps<{
    /** С страницы /patients?agent=… или при редиректе со старого URL агента */
    agentId?: string | null
  }>(),
  { agentId: null },
)

const route = useRoute()
const router = useRouter()

const VISIT_COHORT_KEYS = new Set<string>([
  'primary_bookings',
  'primary_arrived',
  'repeat_bookings',
  'repeat_arrived',
  'all_bookings',
  'all_arrived',
])

const qStr = (v: unknown): string => {
  if (typeof v === 'string' && v.trim()) return v.trim()
  if (Array.isArray(v) && typeof v[0] === 'string' && v[0].trim()) return v[0].trim()
  return ''
}

const normalizeVisitCohort = (v: unknown): '' | PatientsVisitCohort => {
  const s = qStr(v).toLowerCase()
  if (VISIT_COHORT_KEYS.has(s)) return s as PatientsVisitCohort
  return ''
}

const YMD = /^\d{4}-\d{2}-\d{2}$/

/**
 * Сборка query для /patients: agent + vf/vt/vc.
 * vc: 'keep' — сохранить из URL, если обе даты валидны; иначе сбросить.
 * pm / rc / resource: задать явно (в т.ч. '' — убрать из URL); undefined — взять из текущего маршрута.
 */
const buildPatientsRouteQuery = (opts: {
  vf?: string
  vt?: string
  vc?: 'keep' | 'clear' | PatientsVisitCohort
  pm?: string
  rc?: string
  resource?: string
} = {}) => {
  const agent = resolvedAgentId.value
  if (!agent) return { agent: '' as const }

  const prevVf = qStr(route.query.vf)
  const prevVt = qStr(route.query.vt)
  const prevVc = normalizeVisitCohort(route.query.vc)

  const vfRaw = opts.vf !== undefined ? String(opts.vf).trim().slice(0, 10) : prevVf
  const vtRaw = opts.vt !== undefined ? String(opts.vt).trim().slice(0, 10) : prevVt
  const vfOk = vfRaw && YMD.test(vfRaw) ? vfRaw : ''
  const vtOk = vtRaw && YMD.test(vtRaw) ? vtRaw : ''

  let vcOut: '' | PatientsVisitCohort = ''
  const vcOpt = opts.vc
  if (vcOpt === 'clear') {
    vcOut = ''
  } else if (vcOpt === 'keep' || vcOpt === undefined) {
    if (vfOk && vtOk && prevVc) vcOut = prevVc
  } else if (vfOk && vtOk) {
    vcOut = vcOpt
  }

  const prevTz = qStr(route.query.tz)
  const prevChannel = qStr(route.query.channel)
  const prevTagsRaw = route.query.tags
  const prevTags = typeof prevTagsRaw === 'string' && prevTagsRaw.trim() ? prevTagsRaw : ''
  const prevPm = qStr(route.query.pm)
  const prevRc = qStr(route.query.rc)
  const prevResource = qStr(route.query.resource)
  const rb = route.query.revenue_basis
  const rb0 = Array.isArray(rb) ? rb[0] : rb

  const q: Record<string, string> = { agent }
  if (vfOk) q.vf = vfOk
  if (vtOk) q.vt = vtOk
  if (vcOut) q.vc = vcOut
  if (prevTz) q.tz = prevTz
  if (prevChannel) q.channel = prevChannel
  if (prevTags) q.tags = prevTags
  if (rb0 === 'all') q.revenue_basis = 'all'
  if (opts.pm !== undefined) {
    if (opts.pm) q.pm = opts.pm
  } else if (prevPm) {
    q.pm = prevPm
  }
  if (opts.rc !== undefined) {
    if (opts.rc) q.rc = opts.rc
  } else if (prevRc) {
    q.rc = prevRc
  }
  if (opts.resource !== undefined) {
    const trimmed = String(opts.resource).trim()
    if (trimmed && /^\d+$/.test(trimmed)) {
      q.resource = trimmed
    }
  } else if (prevResource && /^\d+$/.test(prevResource)) {
    q.resource = prevResource
  }
  return q
}

const pushPatientsRoute = (opts: Parameters<typeof buildPatientsRouteQuery>[0] = {}) => {
  const q = buildPatientsRouteQuery(opts)
  if (!q.agent) return
  void routerReplaceSafe(router, { path: '/patients', query: q })
}

const onPatientResourceChange = (value: string | number) => {
  const s = String(value)
  if (s === '__all__') {
    pushPatientsRoute({ resource: '' })
    return
  }
  const n = Number(s)
  if (!Number.isFinite(n)) return
  pushPatientsRoute({ resource: String(Math.trunc(n)) })
}

const onVisitDateFromUpdate = (value: string | number) => {
  const v = String(value ?? '').trim().slice(0, 10)
  pushPatientsRoute({ vf: v, vc: 'keep' })
}

const onVisitDateToUpdate = (value: string | number) => {
  const v = String(value ?? '').trim().slice(0, 10)
  pushPatientsRoute({ vt: v, vc: 'keep' })
}

const formatYmdLocal = (d: Date) => {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/** С 1-го числа текущего месяца по сегодня (локальная дата просмотра). */
const monthToDateRange = () => {
  const vt = new Date()
  const vf = new Date(vt.getFullYear(), vt.getMonth(), 1)
  return { vf: formatYmdLocal(vf), vt: formatYmdLocal(vt) }
}

const applyMonthToDate = () => {
  const r = monthToDateRange()
  pushPatientsRoute({ vf: r.vf, vt: r.vt, vc: 'keep' })
}

const isMounted = ref(false)
onMounted(() => {
  isMounted.value = true
})
onBeforeUnmount(() => {
  isMounted.value = false
})

const resolvedAgentId = computed(() => {
  if (props.agentId) return props.agentId
  const raw = route.params.id
  if (raw === undefined || raw === null || raw === '') return null
  return Array.isArray(raw) ? raw[0] : raw
})

const agentIdRef = computed(() => resolvedAgentId.value ?? null)

const analyticsApi = useAnalyticsApi()
const patientResources = ref<AnalyticsResourceOption[]>([])

watch(
  agentIdRef,
  async (id) => {
    patientResources.value = []
    if (!id) return
    patientResources.value = await analyticsApi.getSqnsResourcesForFilter(id).catch(() => [])
  },
  { immediate: true },
)

// ─── Читаем фильтры из URL ПЕРЕД вызовом usePatients ─────────────────────────
// Это гарантирует, что первый fetch ({ immediate: true } внутри usePatients)
// уже использует правильные значения из маршрута, а не пустые.
const readRouteFilters = () => {
  const vfRaw = qStr(route.query.vf)
  const vtRaw = qStr(route.query.vt)
  const rb = route.query.revenue_basis
  const rb0 = Array.isArray(rb) ? rb[0] : rb
  const rawPm = route.query.pm
  const pmStr = typeof rawPm === 'string' ? rawPm : Array.isArray(rawPm) && typeof rawPm[0] === 'string' ? rawPm[0] : ''
  const paymentMethods = pmStr
    .split(',')
    .map(s => s.trim().toLowerCase())
    .filter((v): v is AnalyticsPaymentMethod => v === 'cash' || v === 'card' || v === 'certificate')

  const rawRc = route.query.rc
  const rcStr =
    typeof rawRc === 'string'
      ? rawRc
      : Array.isArray(rawRc) && typeof rawRc[0] === 'string'
        ? rawRc[0]
        : ''
  const revenueCategories = rcStr
    .split(',')
    .map(s => s.trim().toLowerCase())
    .filter((v): v is AnalyticsRevenueCategory => v === 'services' || v === 'commodities')

  const resRaw = qStr(route.query.resource)
  let resource_external_id: number | null = null
  if (resRaw && /^\d+$/.test(resRaw)) {
    const n = Number(resRaw)
    if (Number.isFinite(n)) resource_external_id = Math.trunc(n)
  }

  return {
    visit_date_from: YMD.test(vfRaw) ? vfRaw : '',
    visit_date_to: YMD.test(vtRaw) ? vtRaw : '',
    visit_cohort: normalizeVisitCohort(route.query.vc),
    timezone: qStr(route.query.tz),
    channel: qStr(route.query.channel),
    tags: typeof route.query.tags === 'string' ? route.query.tags : '',
    revenue_basis: (rb0 === 'all' ? 'all' : 'clinical') as 'all' | 'clinical',
    paymentMethods,
    revenueCategories,
    resource_external_id,
  }
}

const {
  query: patientsQuery,
  items: patientsItems,
  total: patientsTotal,
  hasMore: patientsHasMore,
  revenueTotal: patientsRevenueTotal,
  totalArrivalSum: patientsTotalArrivalSum,
  visitsCountSum: patientsVisitsCountSum,
  lastVisitTotalPriceSum: patientsLastVisitTotalPriceSum,
  sliceVisitCount: patientsSliceVisitCount,
  topServiceName: patientsTopServiceName,
  topServiceBookings: patientsTopServiceBookings,
  pending,
  error: patientsError,
  currentPage,
  setPage: setPatientsPage,
} = usePatients(agentIdRef, readRouteFilters())

// ─── Синхронизация URL → patientsQuery при последующих изменениях маршрута ───
watch(
  () => [
    route.query.vf,
    route.query.vt,
    route.query.vc,
    route.query.tz,
    route.query.channel,
    route.query.tags,
    route.query.revenue_basis,
    route.query.pm,
    route.query.rc,
    route.query.resource,
  ],
  () => {
    const filters = readRouteFilters()
    patientsQuery.visit_date_from = filters.visit_date_from
    patientsQuery.visit_date_to = filters.visit_date_to
    patientsQuery.visit_cohort = filters.visit_cohort
    patientsQuery.timezone = filters.timezone
    patientsQuery.channel = filters.channel
    patientsQuery.tags = filters.tags
    patientsQuery.revenue_basis = filters.revenue_basis
    patientsQuery.paymentMethods = filters.paymentMethods
    patientsQuery.revenueCategories = filters.revenueCategories
    patientsQuery.resource_external_id = filters.resource_external_id
    patientsQuery.offset = 0
  },
)

const PAYMENT_METHOD_OPTIONS: { value: AnalyticsPaymentMethod; label: string }[] = [
  { value: 'cash', label: 'Наличные' },
  { value: 'card', label: 'Безналичные' },
  { value: 'certificate', label: 'Сертификаты' },
]

const isPaymentMethodSelected = (method: AnalyticsPaymentMethod) => {
  const methods = patientsQuery.paymentMethods ?? []
  return methods.length === 0 || methods.includes(method)
}

const togglePaymentMethod = (method: AnalyticsPaymentMethod) => {
  const current = patientsQuery.paymentMethods ?? []
  const allSelected = current.length === 0
  const currentSet: Set<AnalyticsPaymentMethod> = allSelected
    ? new Set(PAYMENT_METHOD_OPTIONS.map(o => o.value))
    : new Set(current)
  if (currentSet.has(method)) currentSet.delete(method)
  else currentSet.add(method)
  const allMethods = PAYMENT_METHOD_OPTIONS.map(o => o.value)
  const next = allMethods.every(m => currentSet.has(m)) ? [] : Array.from(currentSet)
  pushPatientsRoute({ pm: next.length ? next.join(',') : '' })
}

const REVENUE_CATEGORY_OPTIONS: { value: AnalyticsRevenueCategory; label: string }[] = [
  { value: 'services', label: 'Услуги' },
  { value: 'commodities', label: 'Товары' },
]

const isRevenueCategorySelected = (cat: AnalyticsRevenueCategory) => {
  const list = patientsQuery.revenueCategories ?? []
  return list.length === 0 || list.includes(cat)
}

const toggleRevenueCategory = (cat: AnalyticsRevenueCategory) => {
  const current = patientsQuery.revenueCategories ?? []
  const allSelected = current.length === 0
  const currentSet: Set<AnalyticsRevenueCategory> = allSelected
    ? new Set(REVENUE_CATEGORY_OPTIONS.map(o => o.value))
    : new Set(current)
  if (currentSet.has(cat)) currentSet.delete(cat)
  else currentSet.add(cat)
  const allCats = REVENUE_CATEGORY_OPTIONS.map(o => o.value)
  const next = allCats.every(c => currentSet.has(c)) ? [] : Array.from(currentSet)
  pushPatientsRoute({ rc: next.length ? next.join(',') : '' })
}

const visitFilterActive = computed(
  () =>
    !!(
      patientsQuery.visit_date_from &&
      patientsQuery.visit_date_to &&
      patientsQuery.visit_cohort
    ),
)

const paymentSliceFilterActive = computed(
  () =>
    visitFilterActive.value &&
    ((patientsQuery.paymentMethods?.length ?? 0) > 0 ||
      (patientsQuery.revenueCategories?.length ?? 0) > 0),
)

const visitPeriodHint = computed(() => {
  const a = patientsQuery.visit_date_from
  const b = patientsQuery.visit_date_to
  if (!a || !b) return ''
  if (visitFilterActive.value) return `Период среза: ${a} — ${b}`
  return `Период визитов: ${a} — ${b}. Выберите сегмент ниже, чтобы отфильтровать список по визитам.`
})

const cohortActiveClass = (key: PatientsVisitCohort) =>
  patientsQuery.visit_cohort === key && visitFilterActive.value
    ? 'border-primary/30 bg-primary/5 text-primary'
    : ''

const setVisitPreset = (vc: PatientsVisitCohort) => {
  let vf = qStr(route.query.vf) || patientsQuery.visit_date_from
  let vt = qStr(route.query.vt) || patientsQuery.visit_date_to
  if (!vf || !vt) {
    const r = monthToDateRange()
    vf = r.vf
    vt = r.vt
  }
  pushPatientsRoute({ vf, vt, vc })
}

const clearVisitPreset = () => {
  const agent = resolvedAgentId.value
  if (!agent) return
  void routerReplaceSafe(router, { path: '/patients', query: { agent } })
}

const patientsErrorMessage = computed(() =>
  patientsError.value ? getReadableErrorMessage(patientsError.value, 'Не удалось загрузить пациентов') : '',
)

const toRevenueNumber = (v: number | string | null | undefined): number => {
  if (v == null) return 0
  if (typeof v === 'number') return Number.isFinite(v) ? v : 0
  const n = parseFloat(String(v).replace(',', '.'))
  return Number.isFinite(n) ? n : 0
}

const initialsFromName = (name: string | null | undefined): string => {
  const parts = (name ?? '').trim().split(/\s+/).filter(Boolean)
  if (!parts.length) return '—'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

const mapClientToRow = (client: SqnsClientListItem): PatientDirectoryRow => {
  const nameRaw = client.name?.trim()
  
  // Определяем отображаемый визит (будущий или последний прошедший)
  let visitDate = '—'
  let visitRelative = '—'
  let serviceName = '—'
  let serviceDetail = '—'
  
  if (client.last_visit_datetime) {
    const d = new Date(client.last_visit_datetime)
    if (!Number.isNaN(d.getTime())) {
      visitDate = new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' }).format(d)
      const now = new Date()
      const isFuture = d > now
      visitRelative = isFuture ? 'Запланирован' : 'Последний визит'
      serviceName = client.last_service_name || '—'
      serviceDetail = client.last_specialist_name || '—'
    }
  }

  const visitRevenueRub =
    !client.last_visit_datetime
      ? null
      : client.last_visit_total_price == null || client.last_visit_total_price === ''
        ? null
        : toRevenueNumber(client.last_visit_total_price)

  const hasSliceRevenue =
    client.slice_revenue !== undefined && client.slice_revenue !== null && client.slice_revenue !== ''
  const revenueRub = hasSliceRevenue
    ? toRevenueNumber(client.slice_revenue!)
    : toRevenueNumber(client.total_arrival)

  const hasSliceVisits =
    client.slice_visits_count !== undefined && client.slice_visits_count !== null

  return {
    id: client.id,
    externalClientId: client.external_id,
    initials: initialsFromName(nameRaw),
    name: nameRaw ? nameRaw : 'Без имени',
    phone: client.phone?.trim() ? client.phone.trim() : '—',
    externalId: `PT-${client.external_id}`,
    visitDate,
    visitRelative,
    serviceName,
    serviceDetail,
    visitRevenueRub,
    visitsCount: hasSliceVisits
      ? String(client.slice_visits_count)
      : String(client.visits_count ?? 0),
    visitsCountIsSlice: hasSliceVisits,
    revenueRub,
    revenueIsSlice: hasSliceRevenue,
  }
}

const displayRows = computed(() => patientsItems.value.map(mapClientToRow))

const tableTotalsVisible = computed(
  () =>
    !!resolvedAgentId.value && !pending.value && patientsTotal.value > 0,
)

const rangeLabel = computed(() => {
  const t = patientsTotal.value
  if (t === 0) return '0 из 0'
  const from = patientsQuery.offset + 1
  const to = patientsQuery.offset + displayRows.value.length
  return `${from}–${to} из ${t.toLocaleString('ru-RU')}`
})

const kpiCards = computed(() => {
  const loading = pending.value && !!resolvedAgentId.value && patientsTotal.value === 0
  const totalStr = !resolvedAgentId.value
    ? '—'
    : loading
      ? '…'
      : patientsTotal.value.toLocaleString('ru-RU')
  const cohort = patientsQuery.visit_cohort
  const bookingsSlice =
    visitFilterActive.value &&
    (cohort === 'all_bookings' || cohort === 'primary_bookings' || cohort === 'repeat_bookings')
  const arrivedSlice =
    visitFilterActive.value &&
    (cohort === 'all_arrived' || cohort === 'primary_arrived' || cohort === 'repeat_arrived')
  const sliceCountReady = patientsSliceVisitCount.value != null
  const firstLabel = bookingsSlice ? 'Записей в срезе' : arrivedSlice ? 'Дошедших в срезе' : 'Всего пациентов'
  const firstValue =
    (bookingsSlice || arrivedSlice) && sliceCountReady
      ? patientsSliceVisitCount.value!.toLocaleString('ru-RU')
      : totalStr
  const firstHint = bookingsSlice
    ? sliceCountReady
      ? `Уникальных пациентов в списке: ${patientsTotal.value.toLocaleString('ru-RU')}. Число визитов совпадает с карточкой «Записи» в аналитике при тех же датах, часовом поясе (tz), канале и тегах.`
      : 'Уникальные клиенты в выбранном срезе визитов за период (после поиска).'
    : arrivedSlice
      ? sliceCountReady
        ? `Уникальных пациентов в списке: ${patientsTotal.value.toLocaleString('ru-RU')}. Число состоявшихся визитов совпадает с «Дошедшие» в аналитике при тех же фильтрах.`
        : 'Уникальные клиенты в выбранном срезе визитов за период (после поиска).'
      : visitFilterActive.value
        ? 'Уникальные клиенты в выбранном срезе визитов за период (после поиска).'
        : 'Пациенты агента по данным интеграции (после поиска).'
  const revenueStr =
    !resolvedAgentId.value
      ? '—'
      : pending.value && patientsRevenueTotal.value === null
        ? '…'
        : patientsRevenueTotal.value !== null
          ? formatRub(patientsRevenueTotal.value)
          : '—'

  const cards: {
    label: string
    value: string
    hint: string
    icon: Component
    valueClass?: string
  }[] = [
    {
      label: firstLabel,
      value: firstValue,
      hint: firstHint,
      icon: Users,
    },
    {
      label: 'С визитом на неделе',
      value: '—',
      hint: 'Появится в следующей версии (визиты)',
      icon: CalendarRange,
    },
    {
      label: 'Фактическая выручка',
      value: revenueStr,
      hint: visitFilterActive.value
        ? paymentSliceFilterActive.value
          ? 'Сумма платежей за период (даты оплаты) с учётом выбранных способов оплаты и типа выручки (clinical), только по клиентам среза визитов — как фильтры в аналитике.'
          : 'Сумма по визитам среза за выбранный период (как в аналитике по когорте), по всей выборке, не только на странице.'
        : 'Сумма total_arrival по всем клиентам в текущей выборке после поиска.',
      icon: Wallet,
    },
    {
      label: 'Топ-услуга',
      value: !resolvedAgentId.value
        ? '—'
        : loading
          ? '…'
          : patientsTopServiceName.value
            ? patientsTopServiceName.value
            : 'Нет данных',
      hint: !resolvedAgentId.value
        ? 'Выберите агента'
        : patientsTopServiceName.value != null && patientsTopServiceBookings.value != null
          ? `Визитов с этой услугой в текущей выборке: ${patientsTopServiceBookings.value.toLocaleString('ru-RU')}. Подробная аналитика — в разделе «Аналитика».`
          : 'По визитам в кэше для пациентов выборки не удалось определить услугу. Подробнее — в «Аналитика».',
      icon: Stethoscope,
      valueClass: 'line-clamp-3 min-h-[2rem] text-lg leading-snug sm:text-xl sm:leading-snug',
    },
  ]
  return cards
})

const formatRub = (n: number) =>
  new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    maximumFractionDigits: 0,
  }).format(n)

const openPatient = (row: PatientDirectoryRow) => {
  const agent = resolvedAgentId.value
  if (!agent) return
  void navigateTo({
    path: `/patients/${row.externalClientId}`,
    query: { agent },
  })
}

const exportCsv = () => {
  const sep = ';'
  const headers = [
    'Имя',
    'Телефон',
    'ID',
    'Визит',
    'Услуга',
    'За визит (₽)',
    'Визитов',
    'Всего (₽)',
  ]
  const lines = displayRows.value.map((row) =>
    [
      row.name,
      row.phone,
      row.externalId,
      `${row.visitDate} ${row.visitRelative}`,
      `${row.serviceName} — ${row.serviceDetail}`,
      row.visitRevenueRub == null ? '' : String(row.visitRevenueRub),
      row.visitsCount,
      String(row.revenueRub),
    ].join(sep),
  )
  const body = [headers.join(sep), ...lines].join('\n')
  const blob = new Blob([`\uFEFF${body}`], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `patients-${resolvedAgentId.value ?? 'export'}.csv`
  a.click()
  URL.revokeObjectURL(url)
}
</script>
