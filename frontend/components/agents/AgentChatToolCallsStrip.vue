<template>
  <div v-if="tools?.length" class="flex flex-col gap-1.5 w-full max-w-[80%]">
    <div
      v-for="(tc, i) in tools"
      :key="`${tc.tool_name}-${tc.tool_call_id ?? i}`"
      class="rounded-lg border border-amber-200/90 bg-amber-50/90 px-2.5 py-2 text-left shadow-sm"
    >
      <div class="flex items-center gap-1.5 text-[11px] font-semibold text-amber-900">
        <Wrench class="w-3.5 h-3.5 shrink-0 text-amber-700" aria-hidden="true" />
        <span class="truncate">{{ tc.tool_name }}</span>
        <span v-if="tc.tool_call_id" class="ml-auto font-mono text-[10px] font-normal text-amber-700/80 truncate max-w-[45%]" :title="tc.tool_call_id">
          {{ tc.tool_call_id }}
        </span>
      </div>
      <details class="mt-1.5 group">
        <summary
          class="cursor-pointer list-none text-[10px] text-slate-500 hover:text-slate-700 select-none flex items-center gap-1"
        >
          <span class="group-open:rotate-90 transition-transform inline-block">▸</span>
          Аргументы и результат
        </summary>
        <pre class="mt-1.5 max-h-48 overflow-auto rounded bg-white/80 border border-amber-100 px-2 py-1.5 text-[10px] leading-relaxed text-slate-700 whitespace-pre-wrap break-all">{{ formatDump(tc) }}</pre>
      </details>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Wrench } from 'lucide-vue-next'

export type ChatToolCallRow = {
  tool_name: string
  tool_call_id: string | null
  args: Record<string, unknown>
  result: unknown
}

defineProps<{
  tools: ChatToolCallRow[] | undefined
}>()

const formatDump = (tc: ChatToolCallRow) => {
  try {
    return JSON.stringify({ args: tc.args, result: tc.result }, null, 2)
  } catch {
    return String(tc)
  }
}
</script>
