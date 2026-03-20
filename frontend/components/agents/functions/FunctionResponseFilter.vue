<template>
  <div>
    <!-- Empty State -->
    <Alert v-if="fieldTree.length === 0" variant="default" class="border-dashed">
      <BrainCircuit class="h-4 w-4" />
      <AlertTitle>Нет данных для фильтрации</AlertTitle>
      <AlertDescription>
        Нажмите «Запустить» в заголовке, чтобы увидеть структуру ответа
      </AlertDescription>
    </Alert>

    <!-- Two-Column Layout -->
    <div v-else class="grid grid-cols-2 gap-4">
      <!-- Left Column: Field Selection -->
      <Card>
        <CardHeader class="pb-3">
          <CardTitle class="text-sm font-semibold">Доступные поля</CardTitle>
        </CardHeader>
        <CardContent>
          <ScrollArea class="h-[420px]">
            <slot name="field-tree" />
          </ScrollArea>
        </CardContent>
      </Card>

      <!-- Right Column: Live Preview -->
      <Card>
        <CardHeader class="pb-3">
          <CardTitle class="text-sm font-semibold">Превью (что увидит LLM)</CardTitle>
        </CardHeader>
        <CardContent class="bg-slate-900 p-3">
          <ScrollArea class="h-[420px]">
            <pre class="text-[11px] font-mono text-slate-50 leading-relaxed">{{ JSON.stringify(previewData, null, 2) }}</pre>
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { BrainCircuit } from 'lucide-vue-next'
import Alert from '~/components/ui/alert/Alert.vue'
import AlertDescription from '~/components/ui/alert/AlertDescription.vue'
import AlertTitle from '~/components/ui/alert/AlertTitle.vue'
import Card from '~/components/ui/card/Card.vue'
import CardContent from '~/components/ui/card/CardContent.vue'
import CardHeader from '~/components/ui/card/CardHeader.vue'
import CardTitle from '~/components/ui/card/CardTitle.vue'
import ScrollArea from '~/components/ui/scroll-area/ScrollArea.vue'

defineProps<{
  fieldTree: any[]
  previewData: any
}>()
</script>
