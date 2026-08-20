<template>
  <TooltipProvider :delay-duration="150">
    <Tooltip>
      <TooltipTrigger as-child>
        <button
          type="button"
          tabindex="-1"
          class="inline-flex h-4 w-4 items-center justify-center rounded-full text-slate-400 transition-colors hover:bg-slate-100 hover:text-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
          :aria-label="text"
        >
          <HelpCircle class="h-3.5 w-3.5" />
        </button>
      </TooltipTrigger>
      <TooltipContent
        side="top"
        :side-offset="6"
        class="max-w-[280px] rounded-xl border border-slate-100 bg-white px-3 py-2 text-xs leading-snug text-slate-700 shadow-[0_8px_24px_-8px_rgba(0,0,0,0.15)]"
      >
        <div v-if="title" class="mb-0.5 font-semibold text-slate-900">{{ title }}</div>
        <div>{{ text }}</div>
      </TooltipContent>
    </Tooltip>
  </TooltipProvider>
</template>

<script setup lang="ts">
import { HelpCircle } from 'lucide-vue-next'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '~/components/ui/tooltip'

defineProps<{
  text: string
  title?: string
}>()
</script>
