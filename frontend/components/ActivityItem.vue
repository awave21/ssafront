<template>
  <div class="px-4 sm:px-6 py-3 sm:py-4">
    <div class="flex items-center gap-3 sm:gap-4">
      <div class="flex items-center justify-center w-8 h-8 sm:w-10 sm:h-10 rounded-lg bg-gradient-to-br flex-shrink-0" :class="activity.color">
        <component
          :is="iconComponent"
          class="h-4 w-4 sm:h-5 sm:w-5 text-white"
        />
      </div>
      <div class="flex-1 min-w-0">
        <p class="text-xs sm:text-sm font-semibold text-slate-900">
          {{ activity.title }}
        </p>
        <p class="text-xs sm:text-sm text-slate-600">
          {{ activity.time }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { UserCheck, Activity as ActivityIcon, FileCheck } from 'lucide-vue-next'

interface Activity {
  id: number
  title: string
  time: string
  icon: string
  color: string
}

interface Props {
  activity: Activity
}

const props = defineProps<Props>()

const iconComponent = computed(() => {
  switch (props.activity.icon) {
    case 'UserCheck':
      return UserCheck
    case 'Activity':
      return ActivityIcon
    case 'FileCheck':
      return FileCheck
    default:
      return UserCheck
  }
})
</script>