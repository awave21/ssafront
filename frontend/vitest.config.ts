import path from 'node:path'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    environment: 'node',
    include: ['**/*.spec.ts'],
    /** Playwright specs live under `e2e/` and use @playwright/test (not in package.json). */
    exclude: ['**/node_modules/**', '**/dist/**', '.nuxt/**', '**/e2e/**'],
  },
  resolve: {
    alias: {
      '~': path.resolve(__dirname),
    },
  },
})
