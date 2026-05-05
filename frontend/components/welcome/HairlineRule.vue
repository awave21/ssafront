<script setup lang="ts">
interface Props {
  label?: string
}
defineProps<Props>()
</script>

<template>
  <div class="relative flex items-center justify-center my-16 md:my-24">
    <div class="hairline w-full" />
    <div class="absolute inset-0 flex items-center justify-center">
      <div
        v-if="label"
        class="mono px-4 bg-[var(--w-paper)] text-[var(--w-ink-soft)]"
      >
        {{ label }}
      </div>
      <div
        v-else
        class="h-1.5 w-1.5 rounded-full bg-[var(--w-peach)] shadow-[0_0_0_4px_var(--w-paper)]"
      />
    </div>
  </div>
</template>
