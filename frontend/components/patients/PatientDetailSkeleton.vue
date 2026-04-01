<template>
  <div class="space-y-6">
    <div
      class="grid min-w-0 gap-6 xl:grid-cols-[minmax(0,340px)_minmax(0,1fr)] xl:items-start"
    >
      <Skeleton class="h-[420px] w-full min-w-0 max-w-full rounded-3xl" />
      <div class="min-w-0 space-y-6">
        <div class="grid min-w-0 grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
          <Skeleton v-for="i in 3" :key="i" class="h-28 w-full rounded-3xl" />
        </div>
        <Skeleton class="h-[360px] w-full rounded-3xl" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import Skeleton from '~/components/ui/skeleton/Skeleton.vue'
</script>
