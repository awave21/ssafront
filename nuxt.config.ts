// @ts-ignore
export default defineNuxtConfig({
  devtools: { enabled: false },
  typescript: { strict: true },

  css: ["~/assets/css/main.css"],

  modules: [
    "@nuxtjs/tailwindcss",
    "@vueuse/nuxt",
    "@pinia/nuxt",
  ],

  runtimeConfig: {
    public: {
      // Значения по умолчанию для development
      // В production переопределяются через NUXT_PUBLIC_* переменные окружения или .env
      apiBase: "/api/v1",
      siteUrl: "http://localhost:3000",
      domain: "localhost",
    },
  },

  nitro: {
    // В dev-режиме проксируем API на бэкенд
    devProxy: {
      "/api/v1": {
        target: "https://agentsapp.integration-ai.ru",
        changeOrigin: true,
        prependPath: true,
      },
    },
  },

  components: {
    dirs: [
      {
        path: '~/components',
        // Ignore barrel index.ts files in UI dirs — they conflict with .vue auto-import
        ignore: ['ui/**/index.ts'],
      },
    ],
  },

  ssr: false,

  app: {
    head: {
      title: "ChatMedBot",
      htmlAttrs: {
        lang: "ru",
      },
      meta: [
        { charset: "utf-8" },
        { name: "viewport", content: "width=device-width, initial-scale=1" },
        {
          name: "description",
          content: "Умные ИИ-агенты для вашей клиники. Автоматизируйте рутинные задачи, улучшите качество диагностики и освободите врачей для работы с пациентами.",
        },
      ],
      link: [
        { rel: "icon", type: "image/x-icon", href: "/favicon.ico" },
      ],
    },
  },

  // Production optimizations
  vite: {
    // ...
  },
});
