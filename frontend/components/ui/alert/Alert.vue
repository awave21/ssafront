<template>
  <div :class="cn(alertVariants({ variant }), $attrs.class)" role="alert">
    <slot />
  </div>
</template>

<script setup lang="ts">
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '~/lib/utils'

const alertVariants = cva(
  'relative w-full rounded-lg border p-4 [&>svg~*]:pl-7 [&>svg+div]:translate-y-[-3px] [&>svg]:absolute [&>svg]:left-4 [&>svg]:top-4 [&>svg]:text-slate-950',
  {
    variants: {
      variant: {
        default: 'bg-white text-slate-950',
        destructive: 'border-red-500/50 text-red-500 [&>svg]:text-red-500',
        warning: 'border-amber-500/50 bg-amber-50 text-amber-800 [&>svg]:text-amber-600',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
)

type AlertVariants = VariantProps<typeof alertVariants>

defineProps<{
  variant?: AlertVariants['variant']
}>()
</script>
