<template>
  <Teleport to="body">
    <Transition name="modal-fade">
      <div
        v-if="isOpen"
        class="fixed inset-0 z-[60] flex items-center justify-center px-4 py-6 sm:px-6"
        aria-modal="true"
        role="dialog"
      >
        <div class="fixed inset-0 bg-black/40 backdrop-blur-sm" @click="emitClose"></div>
        <div
          class="relative w-full max-w-lg overflow-hidden rounded-2xl bg-white shadow-xl shadow-indigo-900/20 ring-1 ring-indigo-100"
          @click.stop
        >
          <!-- Header -->
          <div class="flex items-center justify-between p-6 border-b border-slate-100">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 bg-red-50 rounded-xl flex items-center justify-center text-red-600">
                <AlertTriangle class="h-6 w-6" />
              </div>
              <div>
                <h2 class="text-lg font-bold text-slate-900">Отключение SQNS</h2>
                <p class="text-xs text-slate-500 mt-0.5">Предпросмотр удаления данных</p>
              </div>
            </div>
            <button aria-label="Закрыть" class="text-slate-400 hover:text-slate-600" @click="emitClose">
              <X class="h-5 w-5" />
            </button>
          </div>

          <!-- Content -->
          <div class="p-6">
            <div v-if="isLoading" class="flex flex-col items-center justify-center py-12 space-y-4">
              <Loader2 class="h-8 w-8 text-indigo-600 animate-spin" />
              <p class="text-sm text-slate-500">Загрузка данных...</p>
            </div>
            
            <div v-else-if="previewData" class="space-y-6">
              <div class="bg-red-50 border border-red-100 rounded-xl p-4">
                <p class="text-sm text-red-800 font-medium">
                  Будет УДАЛЕНО БЕЗ ВОЗМОЖНОСТИ ВОССТАНОВЛЕНИЯ:
                </p>
                <ul class="mt-3 space-y-2">
                  <li class="flex items-center gap-2 text-sm text-red-700">
                    <div class="w-1.5 h-1.5 bg-red-400 rounded-full"></div>
                    {{ previewData.services_count }} услуг
                  </li>
                  <li class="flex items-center gap-2 text-sm text-red-700">
                    <div class="w-1.5 h-1.5 bg-red-400 rounded-full"></div>
                    {{ previewData.resources_count }} специалистов
                  </li>
                  <li class="flex items-center gap-2 text-sm text-red-700">
                    <div class="w-1.5 h-1.5 bg-red-400 rounded-full"></div>
                    {{ previewData.links_count }} связей услуга-специалист
                  </li>
                  <li class="flex items-center gap-2 text-sm text-red-700">
                    <div class="w-1.5 h-1.5 bg-red-400 rounded-full"></div>
                    {{ previewData.categories_count }} категорий
                  </li>
                </ul>
              </div>

              <div class="flex items-start gap-3 p-4 bg-yellow-50 border border-yellow-100 rounded-xl text-yellow-800">
                <AlertCircle class="h-5 w-5 text-yellow-500 flex-shrink-0 mt-0.5" />
                <p class="text-xs leading-relaxed">
                  Все настройки приоритетов, включения услуг и категорий будут безвозвратно утеряны. Для восстановления потребуется повторная настройка.
                </p>
              </div>
            </div>

            <div v-else class="text-center py-12">
              <p class="text-sm text-slate-500">Не удалось загрузить данные предпросмотра</p>
            </div>
          </div>

          <!-- Footer -->
          <div class="flex items-center justify-between gap-3 p-6 bg-slate-50 border-t border-slate-100">
            <button
              type="button"
              class="flex-1 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-bold text-slate-600 hover:bg-slate-50 transition-colors"
              @click="emitClose"
            >
              Отмена
            </button>
            <button
              @click="handleConfirm"
              :disabled="isDeleting || isLoading"
              class="flex-1 rounded-xl bg-red-600 px-4 py-3 text-sm font-bold text-white shadow-md shadow-red-100 hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
            >
              <Loader2 v-if="isDeleting" class="h-4 w-4 animate-spin" />
              <Trash2 v-else class="h-4 w-4" />
              {{ isDeleting ? 'Удаление...' : 'Подтвердить' }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { 
  X, 
  AlertTriangle, 
  AlertCircle, 
  Loader2, 
  Trash2 
} from 'lucide-vue-next'
import { useAgents } from '../composables/useAgents'

const props = defineProps<{
  isOpen: boolean
  agentId: string
}>()

const emit = defineEmits<{
  (event: 'close'): void
  (event: 'confirm'): void
}>()

const { getSqnsDisablePreview } = useAgents()

const isLoading = ref(false)
const isDeleting = ref(false)
const previewData = ref<any>(null)

const loadPreview = async () => {
  if (!props.agentId) return
  try {
    isLoading.value = true
    previewData.value = await getSqnsDisablePreview(props.agentId)
  } catch (err) {
    console.error('Failed to load disable preview:', err)
  } finally {
    isLoading.value = false
  }
}

const emitClose = () => {
  emit('close')
}

const handleConfirm = () => {
  isDeleting.value = true
  emit('confirm')
}

watch(() => props.isOpen, (newVal) => {
  if (newVal) {
    loadPreview()
    isDeleting.value = false
  }
})
</script>

<style scoped>
.modal-fade-enter-active,
.modal-fade-leave-active {
  transition: opacity 0.3s ease;
}

.modal-fade-enter-from,
.modal-fade-leave-to {
  opacity: 0;
}
</style>
