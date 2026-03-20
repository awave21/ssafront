<template>
  <!-- Header is now integrated into the main dashboard layout -->
</template>

<script setup lang="ts">
const colorMode = useColorMode()

const toggleTheme = () => {
  colorMode.preference = colorMode.preference === 'light' ? 'dark' : 'light'
}
</script>