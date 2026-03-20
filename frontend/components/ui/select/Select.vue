<template>
  <component :is="comp" v-bind="$attrs">
    <slot />
  </component>
</template>

<script setup lang="ts">
import { SelectRoot } from 'radix-vue'

const comp = SelectRoot
</script>
