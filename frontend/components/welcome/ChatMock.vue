<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue'

interface Message { from: 'user' | 'bot'; text: string }

const chatContainer = ref<HTMLDivElement | null>(null)
const visibleMessages = ref<Message[]>([])
const showTyping = ref(false)

const ALL_MESSAGES: Message[] = [
  { from: 'user', text: 'Здравствуйте! Мне нужно к кардиологу записаться' },
  { from: 'bot',  text: 'Здравствуйте! Конечно, помогу записаться. Когда вам удобно?' },
  { from: 'user', text: 'Сегодня, если возможно' },
  { from: 'bot',  text: 'Отлично! У кардиолога сегодня есть время в 15:20 и 17:40. Подойдёт?' },
  { from: 'user', text: 'К сожалению, сегодня не смогу. А завтра?' },
  { from: 'bot',  text: 'На завтра свободно: 10:30, 14:20 и 16:15. Какое время удобно?' },
  { from: 'user', text: '14:20 отлично подходит!' },
  { from: 'bot',  text: 'Для записи нужен ваш номер телефона для напоминаний.' },
  { from: 'user', text: '+7 (905) 123-45-67' },
  { from: 'bot',  text: 'Подтверждаю: завтра 14:20 к кардиологу, тел. +7(905)123-45-67. Всё верно?' },
  { from: 'user', text: 'Да, всё правильно!' },
  { from: 'bot',  text: '✅ Готово! Запись создана. SMS-напоминание придёт за час до приёма.' },
]

const scrollToBottom = () => {
  nextTick(() => {
    if (chatContainer.value) chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  })
}

watch(visibleMessages, scrollToBottom)

const runDialog = () => {
  visibleMessages.value = []
  showTyping.value = false

  const delays = [1000, 2500, 4000, 5200, 6800, 8200, 10000, 11500, 13000, 14500, 16000, 17500]

  delays.forEach((delay, i) => {
    const msg = ALL_MESSAGES[i]
    setTimeout(() => {
      if (msg.from === 'bot') {
        showTyping.value = true
        scrollToBottom()
        setTimeout(() => {
          showTyping.value = false
          visibleMessages.value.push(msg)
        }, 900)
      } else {
        visibleMessages.value.push(msg)
      }
    }, delay)
  })

  setTimeout(() => {
    setTimeout(runDialog, 3000)
  }, 20000)
}

onMounted(() => setTimeout(runDialog, 800))
</script>

<template>
  <div class="relative">
    <div class="absolute -top-8 -right-6 hidden md:flex items-center gap-1.5 mono text-[var(--w-ink-soft)]">
      <span class="h-1.5 w-1.5 rounded-full" style="background: var(--w-brand-gradient)" />
      live · telegram
    </div>

    <div class="rounded-[28px] bg-[var(--w-surface)] border border-[var(--w-rule)] shadow-[0_24px_60px_-24px_rgba(31,36,33,0.18),0_2px_8px_-2px_rgba(31,36,33,0.06)] overflow-hidden">
      <!-- Header -->
      <div class="flex items-center gap-3 px-5 py-3.5 border-b border-[var(--w-rule)]/70 bg-[var(--w-paper-deep)]/40">
        <div class="flex gap-1.5">
          <span class="h-2.5 w-2.5 rounded-full bg-[var(--w-peach)]" />
          <span class="h-2.5 w-2.5 rounded-full bg-[var(--w-green)]" />
          <span class="h-2.5 w-2.5 rounded-full bg-[var(--w-rule)]" />
        </div>
        <div class="flex-1 text-center serif text-[13px] text-[var(--w-ink-soft)]">ChatMedBot AI</div>
        <span class="mono text-[var(--w-green-deep)]">Онлайн · Готов к работе</span>
      </div>

      <!-- Messages -->
      <div ref="chatContainer" class="px-5 py-5 space-y-3 bg-[var(--w-paper)]/40 h-[340px] overflow-y-auto">
        <transition-group name="msg">
          <div
            v-for="(m, i) in visibleMessages"
            :key="i"
            :class="['flex', m.from === 'user' ? 'justify-end' : 'justify-start']"
          >
            <div
              :class="[
                'max-w-[80%] rounded-2xl px-4 py-3 text-[14px] leading-snug',
                m.from === 'user'
                  ? 'bg-[var(--w-ink)] text-[var(--w-paper)] rounded-br-md'
                  : 'bg-gradient-to-r from-[#4A9B7F] to-[#F5A962] text-white rounded-bl-md',
              ]"
            >{{ m.text }}</div>
          </div>
        </transition-group>

        <!-- Typing -->
        <div v-if="showTyping" class="flex justify-start">
          <div class="bg-gradient-to-r from-[#4A9B7F] to-[#F5A962] rounded-2xl rounded-bl-md px-4 py-3">
            <div class="flex items-center gap-1">
              <span class="h-2 w-2 rounded-full bg-white animate-bounce" style="animation-delay:0ms" />
              <span class="h-2 w-2 rounded-full bg-white animate-bounce" style="animation-delay:150ms" />
              <span class="h-2 w-2 rounded-full bg-white animate-bounce" style="animation-delay:300ms" />
            </div>
          </div>
        </div>
      </div>

      <!-- Input area -->
      <div class="border-t border-[var(--w-rule)]/70 p-4">
        <div class="flex items-center gap-2">
          <div class="flex-1 rounded-lg bg-[var(--w-paper-deep)] px-4 py-2 text-sm text-[var(--w-ink-soft)]">Введите сообщение...</div>
          <div class="h-8 w-8 rounded-lg flex items-center justify-center bg-gradient-to-r from-[#4A9B7F] to-[#F5A962]">
            <svg class="h-4 w-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/>
            </svg>
          </div>
        </div>
      </div>
    </div>

    <div aria-hidden="true" class="hidden md:block absolute -left-16 top-1/3 mono text-[var(--w-ink-soft)] -rotate-90 origin-left whitespace-nowrap">
      —— живой диалог · кардиология
    </div>
  </div>
</template>

<style scoped>
.msg-enter-active { transition: all 400ms cubic-bezier(0.22,1,0.36,1); }
.msg-enter-from  { opacity: 0; transform: translateY(12px); }
</style>
