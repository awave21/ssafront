<template>
  <div class="space-y-4">
    <!-- URL Input -->
    <div>
      <label class="block text-xs font-medium mb-1.5 text-slate-900">URL запроса</label>
      <div class="flex border border-slate-200 rounded-md bg-white focus-within:border-indigo-500 transition-colors">
        <Select
          :model-value="httpMethod"
          @update:model-value="$emit('update:httpMethod', $event)"
        >
          <SelectTrigger class="w-[100px] bg-slate-50 border-0 border-r border-slate-200 font-semibold rounded-none shadow-none focus:ring-0 focus:ring-offset-0">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="GET">GET</SelectItem>
            <SelectItem value="POST">POST</SelectItem>
            <SelectItem value="PUT">PUT</SelectItem>
            <SelectItem value="PATCH">PATCH</SelectItem>
            <SelectItem value="DELETE">DELETE</SelectItem>
          </SelectContent>
        </Select>
        
        <div class="relative flex-1 min-w-0 overflow-hidden">
          <div 
            v-if="hasVariables(endpoint)"
            ref="overlayRef"
            class="absolute inset-0 px-3 py-2.5 text-[13px] font-mono pointer-events-none whitespace-nowrap overflow-hidden flex items-center"
            aria-hidden="true"
          >
            <template v-for="(seg, si) in splitByVars(endpoint)" :key="si">
              <span v-if="seg.isVar" class="text-amber-700 bg-amber-100/70 rounded-sm px-px">{{ seg.text }}</span>
              <span v-else class="text-slate-900">{{ seg.text }}</span>
            </template>
          </div>
          <Input
            :ref="(el: any) => { urlEl = el?.$el || el; $emit('register-url-ref', el) }"
            :model-value="endpoint"
            @update:model-value="$emit('update:endpoint', $event)"
            @focus="$emit('focus-url')"
            @scroll="syncOverlayScroll"
            placeholder="https://api.example.com/users/{{id}}"
            class="border-none rounded-none font-mono text-[13px] h-10 bg-transparent shadow-none focus-visible:ring-0 focus-visible:ring-offset-0 overflow-x-auto"
            :style="hasVariables(endpoint) ? 'color: transparent; -webkit-text-fill-color: transparent; caret-color: #0f172a' : ''"
          />
        </div>
      </div>
      
      <!-- Variable Quick Insert -->
      <div v-if="variables.length > 0" class="flex items-center gap-1.5 mt-2 flex-wrap">
        <span class="text-[10px] text-slate-400 uppercase font-semibold mr-0.5">Вставить:</span>
        <Button
          v-for="v in variables"
          :key="v.name"
          variant="outline"
          size="sm"
          @click="$emit('insert-variable', v.name)"
          class="h-6 px-2 py-0 text-[11px] font-mono bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100 rounded-full"
          :title="v.description || v.value"
        >
          <Braces class="w-3 h-3 mr-1" />
          {{ v.name }}
        </Button>
      </div>
    </div>

    <!-- Credential Select -->
    <div>
      <label class="block text-xs font-medium mb-1.5 text-slate-900">Учётные данные (Credential)</label>
      <Select
        :model-value="credentialId"
        @update:model-value="$emit('update:credentialId', $event)"
      >
        <SelectTrigger>
          <SelectValue placeholder="Без авторизации" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem :value="null">Без авторизации</SelectItem>
          <SelectItem
            v-for="cred in credentials"
            :key="cred.id"
            :value="cred.id"
          >
            {{ cred.name }} ({{ getAuthTypeLabel(cred.auth_type) }})
          </SelectItem>
        </SelectContent>
      </Select>
      <p class="mt-1.5 text-xs text-slate-500">
        Выберите учётные данные для авторизации запросов. Управление учётными данными: 
        <NuxtLink to="/credentials" class="text-indigo-600 hover:text-indigo-700 underline">Учётные данные</NuxtLink>
      </p>
    </div>

    <!-- Secret Headers Warning -->
    <Alert v-if="hasSecretHeaders" variant="warning">
      <AlertCircle class="h-4 w-4" />
      <AlertTitle>Обнаружены секретные заголовки</AlertTitle>
      <AlertDescription>
        При использовании credential секреты из заголовков (apikey, Authorization) можно удалить — credential подставит авторизацию автоматически.
        <Button
          variant="link"
          size="sm"
          @click="$emit('remove-secret-headers')"
          class="mt-2 h-auto p-0 text-amber-800 hover:text-amber-900"
        >
          Удалить секретные заголовки
        </Button>
      </AlertDescription>
    </Alert>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { Braces, AlertCircle } from 'lucide-vue-next'
import { hasVariables, splitByVars } from '~/utils/function-schema'

// UI Components
import { Button } from '~/components/ui/button'
import { Input } from '~/components/ui/input'
import Select from '~/components/ui/select/Select.vue'
import SelectContent from '~/components/ui/select/SelectContent.vue'
import SelectItem from '~/components/ui/select/SelectItem.vue'
import SelectTrigger from '~/components/ui/select/SelectTrigger.vue'
import SelectValue from '~/components/ui/select/SelectValue.vue'
import Alert from '~/components/ui/alert/Alert.vue'
import AlertDescription from '~/components/ui/alert/AlertDescription.vue'
import AlertTitle from '~/components/ui/alert/AlertTitle.vue'

defineProps<{
  endpoint: string
  httpMethod: string
  credentialId: string | null
  credentials: any[]
  variables: Array<{ name: string; value: string; description: string }>
  hasSecretHeaders: boolean
}>()

defineEmits<{
  'update:endpoint': [value: string]
  'update:httpMethod': [value: string]
  'update:credentialId': [value: string | null]
  'insert-variable': [name: string]
  'remove-secret-headers': []
  'focus-url': []
  'register-url-ref': [el: HTMLInputElement | null]
}>()

// Sync overlay scroll with input scroll
const overlayRef = ref<HTMLElement | null>(null)
const urlEl = ref<HTMLInputElement | null>(null)
let rafId = 0

const syncOverlayScroll = () => {
  if (overlayRef.value && urlEl.value) {
    overlayRef.value.scrollLeft = urlEl.value.scrollLeft
  }
}

const pollScroll = () => {
  syncOverlayScroll()
  rafId = requestAnimationFrame(pollScroll)
}

onMounted(() => { rafId = requestAnimationFrame(pollScroll) })
onBeforeUnmount(() => { cancelAnimationFrame(rafId) })

const CREDENTIAL_AUTH_TYPES: Record<string, string> = {
  api_key: 'API Key',
  bearer: 'Bearer Token',
  basic: 'Basic Auth',
  oauth2: 'OAuth 2.0'
}

const getAuthTypeLabel = (type: string) => CREDENTIAL_AUTH_TYPES[type] || type
</script>
