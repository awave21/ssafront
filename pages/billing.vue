<template>
  <div class="w-full px-5 py-5 flex flex-col gap-5">
    <div>
      <h1 class="text-xl font-bold text-foreground">Платежи</h1>
      <p class="text-sm text-muted-foreground mt-1">Управление подпиской и историей платежей.</p>
    </div>

    <div class="bg-background rounded-xl border border-border p-8 text-center">
      <CreditCard class="h-12 w-12 text-muted-foreground mx-auto mb-4" />
      <h3 class="text-lg font-medium text-foreground mb-2">Раздел в разработке</h3>
      <p class="text-sm text-muted-foreground max-w-md mx-auto">
        Здесь будет отображаться информация о вашей подписке, история платежей и управление тарифным планом.
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
definePageMeta({
  middleware: 'auth'
})

import { onMounted } from 'vue'
import { CreditCard } from 'lucide-vue-next'

const { pageTitle } = useLayoutState()

onMounted(() => {
  pageTitle.value = 'Платежи'
})
</script>
