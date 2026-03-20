declare module 'nuxt/schema' {
  interface CustomAppConfig {
    layouts?: {
      agent?: any
      default?: any
    }
  }
}

declare module '#app' {
  interface PageMeta {
    layout?: 'default' | 'agent' | false
  }
}

declare module 'vue-router' {
  interface RouteMeta {
    layout?: 'default' | 'agent' | false
  }
}

// Extend NuxtApp to include custom layout
declare module '#app' {
  interface NuxtApp {
    $layouts?: Record<string, any>
  }
}

export {}
