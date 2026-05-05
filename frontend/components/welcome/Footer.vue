<script setup lang="ts">
</script>

<template>
  <footer id="contacts" class="bg-[var(--w-ink)] text-[var(--w-paper)]">
    <div class="max-w-[1280px] mx-auto px-6 lg:px-10 pt-16 pb-10">
      <div class="grid grid-cols-12 gap-8 pb-12 border-b border-[var(--w-paper)]/15">
        <div class="col-span-12 md:col-span-5">
          <div class="flex items-baseline gap-1 mb-4">
            <span class="display text-[40px]">chatmedbot</span>
            <span class="h-1.5 w-1.5 rounded-full translate-y-[-9px]" style="background: var(--w-brand-gradient)" />
          </div>
          <p class="max-w-[360px] text-[15px] leading-[1.55] opacity-75">
            Интеллектуальный администратор для медицинских центров.
          </p>
        </div>

        <div class="col-span-6 md:col-span-3">
          <div class="mono opacity-60 mb-4">навигация</div>
          <ul class="space-y-2.5 text-[15px]">
            <li><a href="#features" class="hover:text-[var(--w-peach)] transition-colors">Возможности</a></li>
            <li><a href="#for-whom" class="hover:text-[var(--w-peach)] transition-colors">Для кого</a></li>
            <li><a href="#analytics" class="hover:text-[var(--w-peach)] transition-colors">Аналитика</a></li>
            <li><a href="#contacts" class="hover:text-[var(--w-peach)] transition-colors">Контакты</a></li>
          </ul>
        </div>

        <div class="col-span-6 md:col-span-4">
          <div class="mono opacity-60 mb-4">связь</div>
          <a
            href="https://t.me/order_chatmedbot"
            target="_blank"
            rel="noopener"
            class="block serif text-[20px] hover:text-[var(--w-peach)] transition-colors"
          >
            t.me/order_chatmedbot
          </a>
          <a
            href="mailto:hello@chatmedbot.ru"
            class="mt-2 block serif text-[20px] hover:text-[var(--w-peach)] transition-colors"
          >
            hello@chatmedbot.ru
          </a>
        </div>
      </div>

      <div class="flex flex-wrap items-center justify-between gap-3 pt-6">
        <div class="mono opacity-50">© 2026 chatmedbot · все права защищены</div>
        <div class="mono opacity-50">сделано в москве · with care for clinics</div>
      </div>
    </div>
  </footer>
</template>
