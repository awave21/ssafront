<template>
  <Sheet :open="open" @update:open="onRootOpenChange">
    <SheetContent
      side="right"
      :class="[
        'flex flex-col p-0 overflow-hidden',
        widthClass
      ]"
    >
      <!-- Header -->
      <div class="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-white shrink-0">
        <div class="flex items-center gap-3 min-w-0">
          <button 
            v-if="showBack" 
            @click="$emit('back')" 
            class="p-1 text-slate-400 hover:text-slate-600 transition-colors"
          >
            <ArrowLeft class="w-5 h-5" />
          </button>
          <div class="min-w-0">
            <SheetTitle class="text-lg font-bold text-slate-900 truncate">
              {{ title }}
            </SheetTitle>
            <p v-if="subtitle" class="text-xs text-slate-500 truncate mt-0.5">
              {{ subtitle }}
            </p>
          </div>
        </div>

        <div class="flex items-center gap-4 shrink-0 ml-4">
          <slot name="header-actions"></slot>
          <SheetClose class="text-slate-400 hover:text-slate-600 transition-colors" />
        </div>
      </div>

      <!-- Tabs (Optional) -->
      <div v-if="tabs && tabs.length > 0" class="flex items-center gap-6 px-6 border-b border-slate-100 bg-white shrink-0">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          @click="() => !tab.disabled && $emit('update:activeTab', tab.id)"
          :disabled="tab.disabled"
          class="py-3 text-sm font-medium transition-all relative"
          :class="[
            activeTab === tab.id ? 'text-indigo-600' : 'text-slate-500 hover:text-slate-700',
            tab.disabled ? 'opacity-40 cursor-not-allowed hover:text-slate-500' : ''
          ]"
        >
          {{ tab.label }}
          <div v-if="activeTab === tab.id" class="absolute bottom-0 left-0 right-0 h-0.5 bg-indigo-600"></div>
        </button>
      </div>

      <!-- Content -->
      <div class="flex-1 overflow-y-auto bg-white">
        <slot></slot>
      </div>

      <!-- Footer -->
      <div class="p-6 border-t border-slate-100 bg-slate-50 flex items-center justify-between shrink-0">
        <slot name="footer">
          <button
            type="button"
            @click="$emit('cancel')"
            class="px-6 py-2.5 rounded-md border border-slate-200 bg-white text-sm font-medium text-slate-600 hover:bg-slate-100 transition-colors"
          >
            {{ cancelText || 'Отменить' }}
          </button>
          <button
            @click="$emit('submit')"
            :disabled="submitDisabled || loading"
            class="px-8 py-2.5 bg-indigo-600 text-white rounded-md text-sm font-bold hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
          >
            <Loader2 v-if="loading" class="w-4 h-4 animate-spin" />
            <span>{{ submitText || 'Сохранить' }}</span>
          </button>
        </slot>
      </div>
    </SheetContent>
  </Sheet>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ArrowLeft, Loader2 } from 'lucide-vue-next'
import {
  Sheet,
  SheetContent,
  SheetTitle,
  SheetClose,
} from '~/components/ui/sheet'

type Tab = {
  id: string
  label: string
  disabled?: boolean
}

const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    subtitle?: string
    showBack?: boolean
    tabs?: Tab[]
    activeTab?: string
    loading?: boolean
    submitDisabled?: boolean
    submitText?: string
    cancelText?: string
    size?: 'sm' | 'md' | 'lg' | 'xl' | 'full'
    /**
     * Если true (по умолчанию), закрытие по оверлею / Esc / крестику шлёт `close` родителю.
     * Если false — только `update:open`, чтобы родитель сам решил (например автосохранение).
     */
    dismissEmitsClose?: boolean
  }>(),
  { dismissEmitsClose: true }
)

const emit = defineEmits<{
  (e: 'close'): void
  (e: 'cancel'): void
  (e: 'back'): void
  (e: 'submit'): void
  (e: 'update:activeTab', id: string): void
  (e: 'update:open', value: boolean): void
}>()

const onRootOpenChange = (v: boolean) => {
  emit('update:open', v)
  if (!v && props.dismissEmitsClose) {
    emit('close')
  }
}

const widthClass = computed(() => {
  switch (props.size) {
    case 'sm': return 'max-w-md'
    case 'md': return 'max-w-xl'
    case 'lg': return 'max-w-3xl'
    case 'xl': return 'max-w-5xl'
    case 'full': return 'max-w-[95vw]'
    default: return 'max-w-2xl'
  }
})
</script>
