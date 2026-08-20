<template>
  <AgentPageShell :title="flow?.name || 'Навык'" :hide-actions="true" :contained="true">
    <div class="max-w-full space-y-5">
      <!-- Header -->
      <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div class="flex items-center gap-2">
          <NuxtLink
            :to="`/agents/${agentId}/skills`"
            class="inline-flex h-9 items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50"
          >
            <ArrowLeft class="h-4 w-4" />
            К навыкам
          </NuxtLink>
          <span
            v-if="flow"
            class="inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold"
            :class="flow.status === 'published'
              ? 'border border-emerald-200 bg-emerald-50 text-emerald-700'
              : 'border border-slate-200 bg-slate-100 text-slate-600'"
          >
            {{ flow.status === 'published' ? 'Опубликован' : 'Черновик' }}
          </span>
        </div>

        <div class="flex flex-wrap items-center gap-2">
          <button
            type="button"
            class="inline-flex h-9 items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50"
            @click="pickerOpen = true"
          >
            <Stethoscope class="h-4 w-4" />
            Услуги{{ flow?.service_external_ids?.length ? ` (${flow.service_external_ids.length})` : '' }}
          </button>
          <NuxtLink
            :to="`/agents/${agentId}/skills/${skillId}/review`"
            class="inline-flex h-9 items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50"
          >
            <Inbox class="h-4 w-4" />
            Ревью
          </NuxtLink>
          <button
            type="button"
            :disabled="publishing"
            class="inline-flex h-9 items-center gap-1.5 rounded-[11px] bg-gradient-to-r from-[#8168FF] to-[#6042E8] px-4 text-sm font-bold text-white shadow-[0_4px_12px_0_#6042E84D] transition-opacity hover:opacity-90 disabled:opacity-50"
            @click="handlePublish"
          >
            <Loader2 v-if="publishing" class="h-4 w-4 animate-spin" />
            <UploadCloud v-else class="h-4 w-4" />
            Опубликовать
          </button>
        </div>
      </div>

      <!-- Название навыка (крупно, редактируемое) -->
      <div v-if="flow" class="flex items-center gap-3.5">
        <span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-[13px] bg-[#EEEAFF]">
          <GraduationCap class="h-6 w-6 text-[#6042E8]" />
        </span>
        <div class="min-w-0 flex-1">
          <input
            v-model="nameDraft"
            placeholder="Название навыка"
            class="w-full rounded-lg border border-transparent bg-transparent px-1.5 py-0.5 text-[26px] font-bold text-[#16141F] outline-none transition-colors hover:bg-[#F7F6FC] focus:border-[#DED9F0] focus:bg-white"
            title="Название навыка — нажмите, чтобы переименовать"
            @keyup.enter="saveName"
            @blur="saveName"
          >
          <div class="px-1.5 text-[13px] text-[#6C6980]">Навык ассистента · собирается из ваших диалогов</div>
        </div>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="flex justify-center py-16">
        <Loader2 class="h-8 w-8 animate-spin text-indigo-600" />
      </div>

      <template v-else>
        <!-- Two-panel: слева чат эксперта с ИИ, справа навык с метриками -->
        <div class="grid items-start gap-4 lg:grid-cols-[minmax(0,0.92fr)_minmax(0,1.08fr)]">
          <!-- ── ЛЕВО: чат эксперта с ассистентом ── -->
          <div
            class="relative flex h-[75vh] flex-col overflow-hidden rounded-[20px] bg-white shadow-[0_2px_8px_0_#1A153008] lg:sticky lg:top-4 lg:h-[calc(100vh-12rem)]"
            @dragenter.prevent="onDragEnter"
            @dragover.prevent
            @dragleave.prevent="onDragLeave"
            @drop.prevent="onDrop"
          >
            <!-- drop overlay -->
            <div
              v-if="dragActive"
              class="pointer-events-none absolute inset-0 z-20 flex flex-col items-center justify-center gap-2 rounded-[20px] border-2 border-dashed border-[#7B61FF] bg-[#F6F2FF]/90"
            >
              <span class="flex h-14 w-14 items-center justify-center rounded-2xl bg-white shadow-sm">
                <Paperclip class="h-6 w-6 text-[#6042E8]" />
              </span>
              <p class="text-sm font-semibold text-[#6042E8]">Отпустите — прикреплю файлы</p>
              <p class="text-xs text-[#8E76FF]">Можно несколько сразу</p>
            </div>

            <!-- chat header -->
            <div class="flex shrink-0 items-center justify-between border-b border-[#ECEAF4] px-5 py-3.5">
              <div class="flex items-center gap-3">
                <span class="flex h-[38px] w-[38px] items-center justify-center rounded-[12px] bg-gradient-to-br from-[#8E76FF] to-[#6042E8]">
                  <Bot class="h-5 w-5 text-white" />
                </span>
                <div>
                  <div class="flex items-center gap-2">
                    <span class="text-[15px] font-semibold text-[#16141F]">Ассистент</span>
                    <span class="inline-flex items-center gap-1.5 rounded-full bg-[#EEEAFF] px-2 py-0.5">
                      <span class="h-1.5 w-1.5 rounded-full bg-[#7B61FF]" :class="chatBusy && 'animate-pulse'" />
                      <span class="text-[11px] font-medium text-[#6042E8]">{{ chatBusy ? 'печатает' : 'учится' }}</span>
                    </span>
                  </div>
                  <div class="text-xs text-[#6C6980]">Собирает навык из ваших диалогов</div>
                </div>
              </div>
              <select
                v-model="chatModel"
                class="rounded-[11px] border border-[#ECEAF4] bg-[#F7F6FC] py-1.5 pl-2.5 pr-7 text-xs font-medium text-[#16141F] outline-none transition-colors hover:bg-[#F1EFFA] focus:border-[#7B61FF]"
                @change="persistChatModel"
              >
                <option v-for="m in chatModels" :key="m.id" :value="m.id">{{ m.label }} — {{ m.hint }}</option>
              </select>
            </div>

          <!-- chat thread -->
          <div
            ref="chatScroll"
            class="min-h-0 flex-1 space-y-4 overflow-y-auto bg-[#F7F6FC] p-5"
          >
            <div class="flex items-start gap-3 rounded-[14px] border border-[#DED9F0] bg-gradient-to-r from-[#F6F2FF] to-[#F1ECFF] p-3.5">
              <span class="flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-[9px] bg-white">
                <Sparkles class="h-4 w-4 text-[#7B61FF]" />
              </span>
              <p class="text-[13.5px] leading-[20px] text-[#6C6980]">
                Расскажите опыт диалогами: «Пациент говорит… — я отвечаю…». Можно прикрепить
                переписки или файлы — ассистент соберёт навык <b>вашими фразами</b>, а справа он
                растёт в реальном времени.
              </p>
            </div>
            <div v-if="!chat.length" class="py-8 text-center text-sm text-[#A6A2BA]">
              Напишите первое сообщение — например: «При возражении “дорого” я говорю…»
            </div>
            <div
              v-for="(m, i) in chat"
              :key="`msg-${i}`"
              class="flex gap-2.5"
              :class="m.role === 'user' ? 'flex-row-reverse' : ''"
            >
              <span
                class="mt-0.5 flex h-[30px] w-[30px] shrink-0 items-center justify-center rounded-[9px] text-[12px] font-semibold"
                :class="m.role === 'user'
                  ? 'bg-[#EEEAFF] text-[#6042E8]'
                  : 'bg-gradient-to-br from-[#8E76FF] to-[#6042E8] text-white'"
              >
                <Bot v-if="m.role === 'assistant'" class="h-4 w-4" />
                <span v-else>Э</span>
              </span>
              <!-- пузырь: точки-«печатает», пока пусто; иначе markdown -->
              <div
                v-if="m.role === 'assistant' && !m.content"
                class="flex items-center gap-1.5 rounded-[4px_16px_16px_16px] border border-[#ECEAF4] bg-white px-4 py-3.5"
              >
                <span class="h-2 w-2 animate-bounce rounded-full bg-[#7B61FF] [animation-delay:-0.2s]" />
                <span class="h-2 w-2 animate-bounce rounded-full bg-[#B7A8FF] [animation-delay:-0.1s]" />
                <span class="h-2 w-2 animate-bounce rounded-full bg-[#DAD2FF]" />
              </div>
              <div
                v-else
                class="markdown-content max-w-[80%] px-3.5 py-2.5 text-sm leading-relaxed"
                :class="m.role === 'user'
                  ? 'rounded-[16px_16px_4px_16px] bg-gradient-to-br from-[#8168FF] to-[#6042E8] text-white shadow-[0_3px_10px_0_#6042E833]'
                  : 'rounded-[4px_16px_16px_16px] border border-[#ECEAF4] bg-white text-[#16141F] shadow-[0_1px_3px_0_#1A153008]'"
                v-html="renderMd(m.content)"
              />
              <!-- eslint-disable-line vue/no-v-html -->
            </div>
          </div>

          <!-- composer footer -->
          <div class="shrink-0 space-y-3 border-t border-[#ECEAF4] bg-white p-4">
          <!-- attachments + reading -->
          <div v-if="attachments.length || reading.length" class="flex flex-wrap gap-1.5">
            <span
              v-for="(a, i) in attachments"
              :key="`att-${i}`"
              class="inline-flex items-center gap-1 rounded-2xl bg-[#EEEAFF] px-2.5 py-1 text-xs text-[#6042E8]"
            >
              <FileText class="h-3 w-3" />
              {{ a.name }}
              <button type="button" class="text-[#8E76FF] hover:text-[#6042E8]" @click="attachments.splice(i, 1)">
                <X class="h-3 w-3" />
              </button>
            </span>
            <!-- читаются сейчас -->
            <span
              v-for="r in reading"
              :key="`rd-${r.id}`"
              class="inline-flex flex-col gap-1 rounded-2xl border border-[#DED9F0] bg-[#F7F6FC] px-2.5 py-1.5"
            >
              <span class="inline-flex items-center gap-1.5 text-xs text-[#6C6980]">
                <Loader2 class="h-3 w-3 animate-spin text-[#6042E8]" />
                <span class="max-w-[140px] truncate">{{ r.name }}</span>
                <span class="font-mono text-[10px] text-[#6042E8]">{{ r.percent }}%</span>
              </span>
              <span class="h-1 w-full overflow-hidden rounded-full bg-[#DED9F0]">
                <span class="block h-1 rounded-full bg-gradient-to-r from-[#8168FF] to-[#6042E8] transition-all duration-150" :style="{ width: `${r.percent}%` }" />
              </span>
            </span>
          </div>

          <!-- proposal: ассистент предлагает — Принять / Отклонить -->
          <div
            v-if="pendingAdditions"
            class="rounded-[16px] border border-[#DED9F0] bg-[#F6F2FF] p-4"
          >
            <div class="flex items-center gap-2 text-sm font-semibold text-[#6042E8]">
              <Sparkles class="h-4 w-4" /> Ассистент предлагает добавить в навык
            </div>
            <div class="mt-2.5 space-y-1.5">
              <div
                v-for="(o, i) in pendingAdditions.objections"
                :key="`add-obj-${i}`"
                class="flex items-start gap-2 text-sm text-[#16141F]"
              >
                <Plus class="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#12B981]" />
                <span><b class="font-semibold">{{ o.situation }}</b> — {{ o.phrases.length }} фраз</span>
              </div>
              <div
                v-for="(g, i) in pendingAdditions.gaps"
                :key="`add-gap-${i}`"
                class="flex items-start gap-2 text-sm text-[#B4791A]"
              >
                <AlertTriangle class="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>Пробел: {{ g.situation }}</span>
              </div>
            </div>
            <div class="mt-3.5 flex items-center justify-end gap-2">
              <button
                type="button"
                class="rounded-[11px] border border-[#DED9F0] bg-white px-4 py-1.5 text-sm font-semibold text-[#6C6980] transition-colors hover:bg-[#F7F6FC]"
                @click="rejectPending"
              >
                Отклонить
              </button>
              <button
                type="button"
                class="inline-flex items-center gap-1.5 rounded-[11px] bg-gradient-to-r from-[#8168FF] to-[#6042E8] px-4 py-1.5 text-sm font-bold text-white shadow-[0_4px_12px_0_#6042E84D]"
                @click="acceptPending"
              >
                <Check class="h-4 w-4" /> Принять
              </button>
            </div>
          </div>

          <!-- input -->
          <div v-else>
            <!-- строка ввода -->
            <div class="flex items-end gap-2.5 rounded-[16px] border-[1.5px] border-[#DED9F0] bg-[#F7F6FC] p-2.5 transition-shadow focus-within:shadow-[0_0_0_3px_#7B61FF1F]">
              <button
                type="button"
                class="flex h-10 w-10 shrink-0 items-center justify-center rounded-[12px] bg-white text-[#6C6980] transition-colors hover:text-[#6042E8]"
                title="Прикрепить файл"
                @click="fileInput?.click()"
              >
                <Paperclip class="h-[18px] w-[18px]" />
              </button>
              <input ref="fileInput" type="file" multiple accept=".txt,.md,.csv,.json,.text" class="hidden" @change="onFiles">

              <textarea
                ref="chatTextarea"
                v-model="chatInput"
                rows="1"
                placeholder='Напишите приём — например: «При возражении "дорого" я говорю…»'
                class="max-h-40 min-h-[40px] flex-1 resize-none overflow-y-auto border-0 bg-transparent px-1 py-2 text-sm leading-relaxed text-[#16141F] outline-none placeholder:text-[#A6A2BA]"
                @input="autoGrow"
                @keydown.enter.exact.prevent="sendChat"
              />

              <button
                v-if="voiceSupported"
                type="button"
                class="flex h-10 shrink-0 items-center gap-1.5 rounded-[12px] px-3 transition-colors"
                :class="recording ? 'bg-[#FEECEC]' : 'bg-white hover:bg-[#F1EFFA]'"
                :title="recording ? 'Остановить запись' : 'Голосовой ввод'"
                @click="toggleVoice"
              >
                <span v-if="recording" class="flex h-[22px] items-center gap-[2px]">
                  <span class="w-[2.5px] animate-pulse rounded-[2px] bg-[#E24B4A]" style="height:7px" />
                  <span class="w-[2.5px] animate-pulse rounded-[2px] bg-[#E24B4A] [animation-delay:-0.15s]" style="height:16px" />
                  <span class="w-[2.5px] animate-pulse rounded-[2px] bg-[#E24B4A] [animation-delay:-0.3s]" style="height:11px" />
                </span>
                <component :is="recording ? MicOff : Mic" class="h-[17px] w-[17px]" :class="recording ? 'text-[#E24B4A]' : 'text-[#6042E8]'" />
              </button>

              <button
                v-if="chatBusy"
                type="button"
                class="flex h-10 shrink-0 items-center gap-1.5 rounded-[12px] border border-[#F0C1C1] bg-[#FEECEC] px-4 text-sm font-bold text-[#E24B4A]"
                @click="stopChat"
              >
                <Square class="h-3.5 w-3.5 fill-current" />
                Стоп
              </button>
              <button
                v-else
                type="button"
                :disabled="!chatInput.trim() && !attachments.length"
                class="flex h-10 w-10 shrink-0 items-center justify-center rounded-[12px] bg-gradient-to-r from-[#8168FF] to-[#6042E8] text-white shadow-[0_4px_12px_0_#6042E84D] transition-opacity hover:opacity-90 disabled:opacity-50"
                title="Отправить"
                @click="sendChat"
              >
                <SendHorizontal class="h-[18px] w-[18px]" />
              </button>
            </div>
          </div>
          </div>
          <!-- /composer footer -->

          </div>
          <!-- /ЛЕВО -->

          <!-- ── ПРАВО: навык с метриками ── -->
          <div class="space-y-4">
            <!-- Навык -->
            <div class="space-y-4">
              <div
                v-if="!skill"
                class="rounded-3xl border-2 border-dashed border-slate-100 bg-white p-10 text-center"
              >
                <Sparkles class="mx-auto mb-3 h-10 w-10 text-slate-300" />
                <h3 class="text-base font-bold text-slate-900">Навык пока пустой</h3>
                <p class="mx-auto mt-1 max-w-md text-sm text-slate-500">
                  Начните диалог слева — расскажите ассистенту, как вы ведёте пациента.
                  Навык соберётся здесь: ситуации, ваши фразы, метрики и пробелы.
                </p>
              </div>

              <template v-else>
            <!-- Готовность навыка -->
            <div class="rounded-2xl border border-[#ECEAF4] bg-[#F7F6FC] p-3.5">
              <div class="flex items-end justify-between">
                <div>
                  <div class="text-[13px] font-medium text-[#6C6980]">Готовность навыка</div>
                  <div class="text-xs text-[#A6A2BA]">{{ readinessLabel }}</div>
                </div>
                <div class="text-[32px] font-semibold leading-none text-[#6042E8]">{{ readinessPct }}%</div>
              </div>
              <div class="mt-2.5 h-3 w-full overflow-hidden rounded-full bg-[#DED9F0]">
                <div
                  class="h-3 rounded-full bg-gradient-to-r from-[#2DD4E8] to-[#7B61FF] transition-all duration-700"
                  :style="{ width: `${readinessPct}%` }"
                />
              </div>
            </div>

            <!-- Статистика -->
            <div class="grid grid-cols-3 gap-2.5">
              <div class="rounded-2xl border border-[#ECEAF4] bg-white px-3 py-3">
                <div class="font-mono text-[22px] font-semibold leading-none text-[#6042E8]">{{ phraseCount }}</div>
                <div class="mt-1.5 text-[11px] text-[#6C6980]">фраз собрано</div>
              </div>
              <div class="rounded-2xl border border-[#ECEAF4] bg-white px-3 py-3">
                <div class="font-mono text-[22px] font-semibold leading-none text-[#16141F]">{{ skill.objections.length }}</div>
                <div class="mt-1.5 text-[11px] text-[#6C6980]">обработок</div>
              </div>
              <div class="rounded-2xl border border-[#ECEAF4] bg-white px-3 py-3">
                <div class="font-mono text-[22px] font-semibold leading-none text-[#2DA7E8]">{{ coveragePct }}%</div>
                <div class="mt-1.5 text-[11px] text-[#6C6980]">покрытие тем</div>
              </div>
            </div>

            <!-- поиск -->
            <div class="relative">
              <Search class="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                v-model="objSearch"
                type="text"
                placeholder="Поиск по ситуации, триггеру или фразе…"
                class="h-11 w-full rounded-xl border border-slate-200 bg-slate-50 py-2 pl-10 pr-4 text-sm outline-none transition-all focus:border-indigo-400 focus:bg-white focus:ring-4 focus:ring-indigo-500/10"
              >
            </div>

            <!-- действия -->
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div class="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  class="inline-flex h-10 items-center gap-2 rounded-xl border px-3.5 text-sm font-semibold transition-colors"
                  :class="showFullText ? 'border-indigo-300 bg-indigo-50 text-indigo-700' : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'"
                  title="Весь навык одним текстом — так его получает агент"
                  @click="showFullText = !showFullText"
                >
                  <FileText class="h-4 w-4" />
                  Текст навыка
                </button>
                <button
                  type="button"
                  class="inline-flex h-10 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3.5 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-50"
                  @click="allExpanded ? collapseAll() : expandAll()"
                >
                  <component :is="allExpanded ? ChevronsDownUp : ChevronsUpDown" class="h-4 w-4" />
                  {{ allExpanded ? 'Свернуть всё' : 'Развернуть всё' }}
                </button>
              </div>
              <button
                type="button"
                class="inline-flex h-10 items-center gap-2 rounded-xl bg-indigo-600 px-4 text-sm font-bold text-white transition-colors hover:bg-indigo-700"
                @click="addObjection"
              >
                <Plus class="h-4 w-4" /> Обработка
              </button>
            </div>

            <!-- Full skill text (read-only) -->
            <section
              v-if="showFullText"
              class="overflow-hidden rounded-3xl border border-indigo-100 bg-white shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]"
            >
              <div class="flex items-center justify-between border-b border-slate-100 bg-indigo-50/40 px-4 py-2.5">
                <span class="inline-flex items-center gap-1.5 text-xs font-bold text-indigo-700">
                  <FileText class="h-4 w-4" /> Текст навыка — так его получает агент
                </span>
                <button
                  type="button"
                  class="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-medium text-slate-600 hover:bg-slate-50"
                  @click="copyFullText"
                >
                  <component :is="copied ? Check : Copy" class="h-3.5 w-3.5" />
                  {{ copied ? 'Скопировано' : 'Копировать' }}
                </button>
              </div>
              <pre class="max-h-[420px] overflow-auto whitespace-pre-wrap px-5 py-4 text-xs leading-relaxed text-slate-700">{{ fullText }}</pre>
            </section>

            <!-- Контекст навыка — всегда виден и редактируется -->
            <section class="rounded-3xl border border-slate-100 bg-white p-4 shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
              <div class="flex items-baseline gap-2">
                <label class="text-sm font-bold text-slate-900">Контекст навыка</label>
                <span class="text-xs text-slate-400">описание для выбора навыка</span>
              </div>
              <div class="mt-1.5 flex items-start gap-2 rounded-xl bg-indigo-50/50 px-3 py-2 text-[11px] leading-relaxed text-indigo-900">
                <Sparkles class="mt-0.5 h-3.5 w-3.5 shrink-0 text-indigo-500" />
                <p>По этому описанию модель решает, <b>когда подключить навык</b> в разговоре. Пишите, о каких услугах и запросах он — чем яснее, тем точнее выбор.</p>
              </div>
              <textarea
                v-model="skill.context"
                rows="2"
                placeholder="Например: навык про биоревитализацию — приём обращений, выбор инъекционная / безинъекционная, цена, запись."
                class="mt-2 min-h-[64px] w-full resize-y rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm leading-relaxed outline-none transition-all focus:border-indigo-400 focus:bg-white focus:ring-4 focus:ring-indigo-500/10"
                @input="markDirty"
              />
            </section>

            <!-- Навык как ветки условий по этапам диалога -->
            <section class="space-y-4">
              <div v-for="grp in visibleStageGroups" :key="grp.stage">
                <!-- этап -->
                <div class="mb-2 flex items-center gap-2">
                  <span class="flex h-5 w-5 items-center justify-center rounded-full bg-indigo-500">
                    <span class="h-1.5 w-1.5 rounded-full bg-white" />
                  </span>
                  <h4 class="text-sm font-bold text-slate-900">{{ grp.label }}</h4>
                  <span class="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-500">{{ grp.items.length }}</span>
                </div>

                <!-- ветки этапа -->
                <div class="relative space-y-2 pl-5">
                  <div class="absolute bottom-3 left-[9px] top-1 w-px bg-slate-200" />
                  <div
                    v-for="{ obj, index } in grp.items"
                    :key="`obj-${index}`"
                    class="relative overflow-hidden rounded-2xl border border-slate-100 bg-white shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]"
                  >
                    <div class="absolute -left-[14px] top-5 h-2.5 w-2.5 rounded-full border-2 border-white bg-indigo-400" />

                    <!-- ветка: если клиент говорит → ответ -->
                    <div class="flex items-start gap-2 px-4 py-3">
                      <button type="button" class="min-w-0 flex-1 text-left" @click="toggleOpen(obj)">
                        <div class="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                          <ChevronRight class="h-3.5 w-3.5 shrink-0 transition-transform" :class="isOpen(obj) && 'rotate-90'" />
                          Если клиент говорит
                        </div>
                        <p class="mt-0.5 line-clamp-2 pl-[18px] text-sm font-medium text-slate-700">
                          {{ obj.trigger_when || obj.situation || '—' }}
                        </p>
                        <div class="mt-1.5 flex items-start gap-1.5 pl-[18px]">
                          <span class="font-bold text-indigo-400">→</span>
                          <p class="line-clamp-2 text-sm text-slate-800">{{ firstPhrase(obj) || 'ответ не задан' }}</p>
                        </div>
                      </button>
                      <div class="flex shrink-0 items-center gap-1.5">
                        <span
                          v-if="obj.phrases.length > 1"
                          class="rounded-full bg-indigo-50 px-1.5 py-0.5 text-[10px] font-semibold text-indigo-600"
                          :title="`${obj.phrases.length} вариантов ответа`"
                        >+{{ obj.phrases.length - 1 }}</span>
                        <button
                          type="button"
                          class="rounded-lg p-1 text-slate-300 transition-colors hover:bg-red-50 hover:text-red-500"
                          title="Удалить"
                          @click="removeObjection(index)"
                        >
                          <Trash2 class="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>

                    <!-- expanded editor — как мини-диалог -->
                <div v-show="isOpen(obj)" class="space-y-3.5 border-t border-slate-100 px-4 py-4">
                  <!-- этап диалога -->
                  <div class="flex items-center justify-between gap-2">
                    <label class="text-[11px] font-semibold text-slate-500">Этап диалога</label>
                    <select
                      v-model="obj.stage"
                      class="rounded-lg border border-slate-200 bg-white py-1 pl-2 pr-6 text-xs font-medium text-slate-700 outline-none focus:border-indigo-400"
                      title="К какому этапу разговора относится"
                      @change="markDirty"
                    >
                      <option v-for="st in STAGE_ORDER" :key="st" :value="st">{{ STAGE_LABELS[st] }}</option>
                    </select>
                  </div>

                  <!-- когда клиент говорит -->
                  <div>
                    <label class="flex items-center gap-1.5 text-[11px] font-semibold text-slate-500">
                      <MessageSquare class="h-3.5 w-3.5 text-slate-400" /> Когда клиент говорит
                    </label>
                    <input
                      v-model="obj.trigger_when"
                      placeholder="Слова клиента, по которым срабатывает"
                      class="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm outline-none focus:border-indigo-400 focus:bg-white"
                      @input="markDirty"
                    >
                  </div>

                  <!-- ваши ответы -->
                  <div class="space-y-1.5">
                    <div class="flex items-center justify-between">
                      <label class="flex items-center gap-1.5 text-[11px] font-semibold text-indigo-600">
                        <Bot class="h-3.5 w-3.5" /> Вы отвечаете
                      </label>
                      <button
                        type="button"
                        class="inline-flex items-center gap-1 text-[11px] font-medium text-indigo-600 hover:text-indigo-700"
                        @click="addPhrase(obj)"
                      >
                        <Plus class="h-3 w-3" /> Ответ
                      </button>
                    </div>
                    <div
                      v-for="(ph, pi) in obj.phrases"
                      v-show="pi === 0 || isVariantsOpen(obj)"
                      :key="`ph-${index}-${pi}`"
                      class="flex items-start gap-2"
                    >
                      <textarea
                        v-model="ph.text"
                        rows="2"
                        placeholder="Что ответить пациенту"
                        class="min-h-[40px] flex-1 resize-y rounded-lg border border-slate-200 bg-indigo-50/40 px-3 py-1.5 text-sm outline-none focus:border-indigo-400 focus:bg-white"
                        @input="markDirty"
                      />
                      <select
                        v-model="ph.level"
                        class="mt-0.5 shrink-0 rounded-lg border border-slate-200 bg-white py-1 pl-2 pr-6 text-[11px] font-medium text-slate-600 outline-none focus:border-indigo-400"
                        title="Насколько дословно использовать фразу"
                        @change="markDirty"
                      >
                        <option v-for="lvl in levels" :key="lvl" :value="lvl">{{ lvl }}</option>
                      </select>
                      <button
                        type="button"
                        class="mt-1 shrink-0 rounded-lg p-1 text-slate-300 hover:bg-slate-50 hover:text-red-500"
                        @click="removePhrase(obj, pi)"
                      >
                        <X class="h-3.5 w-3.5" />
                      </button>
                    </div>
                    <p v-if="!obj.phrases.length" class="text-[11px] text-amber-600">
                      Без ответов эта ситуация станет пробелом.
                    </p>
                    <button
                      v-if="obj.phrases.length > 1"
                      type="button"
                      class="inline-flex items-center gap-1 text-[11px] font-medium text-slate-400 hover:text-indigo-600"
                      @click="toggleVariants(obj)"
                    >
                      <ChevronRight class="h-3 w-3 transition-transform" :class="isVariantsOpen(obj) && 'rotate-90'" />
                      {{ isVariantsOpen(obj) ? 'Свернуть варианты' : `Ещё ${obj.phrases.length - 1} вариант(а) ответа` }}
                    </button>
                    <p v-if="isVariantsOpen(obj) || obj.phrases.length <= 1" class="text-[10px] text-slate-400">
                      Уровень: <b>пример</b> — можно менять · <b>дословно</b> — близко к тексту · <b>обязательно</b> — слово в слово
                    </p>
                  </div>

                  <!-- тонкости (свёрнуто) -->
                  <div class="overflow-hidden rounded-lg border border-slate-100">
                    <button
                      type="button"
                      class="flex w-full items-center gap-1.5 px-2.5 py-1.5 text-left"
                      @click="toggleDetails(obj)"
                    >
                      <ChevronRight class="h-3.5 w-3.5 shrink-0 text-slate-400 transition-transform" :class="isDetailsOpen(obj) && 'rotate-90'" />
                      <span class="text-[11px] font-semibold text-slate-500">Тонкости</span>
                      <span class="text-[10px] text-slate-400">название, подход, чего избегать</span>
                    </button>
                    <div v-show="isDetailsOpen(obj)" class="space-y-2.5 border-t border-slate-100 px-2.5 py-2.5">
                      <div>
                        <label class="text-[9px] font-black uppercase tracking-wider text-slate-400">Название ситуации</label>
                        <input
                          v-model="obj.situation"
                          placeholder="Короткое имя ситуации"
                          class="mt-1 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs outline-none focus:border-indigo-400 focus:bg-white"
                          @input="markDirty"
                        >
                      </div>
                      <div>
                        <label class="text-[9px] font-black uppercase tracking-wider text-slate-400">Подход</label>
                        <textarea
                          v-model="obj.approach"
                          rows="2"
                          placeholder="Как вести в этой ситуации (для себя)"
                          class="mt-1 w-full resize-none rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs outline-none focus:border-indigo-400 focus:bg-white"
                          @input="markDirty"
                        />
                      </div>
                      <div>
                        <label class="text-[9px] font-black uppercase tracking-wider text-slate-400">Чего избегать</label>
                        <div v-if="obj.forbidden.length" class="mt-1 flex flex-wrap gap-1.5">
                          <span
                            v-for="(fb, fi) in obj.forbidden"
                            :key="`fb-${index}-${fi}`"
                            class="inline-flex items-center gap-1 rounded-2xl bg-red-50/70 px-2 py-0.5 text-[11px] text-red-600"
                          >
                            {{ fb }}
                            <button type="button" class="text-red-300 hover:text-red-600" @click="obj.forbidden.splice(fi, 1); markDirty()">
                              <X class="h-3 w-3" />
                            </button>
                          </span>
                        </div>
                        <p v-else class="mt-1 text-[10px] text-slate-400">Не задано.</p>
                      </div>
                    </div>
                  </div>
                </div>
                  </div>
                </div>
                <!-- /ветки этапа -->
              </div>
              <!-- /этап -->

              <p v-if="!visibleStageGroups.length" class="rounded-2xl border border-slate-100 bg-white px-4 py-6 text-center text-sm text-slate-400">
                {{ objSearch ? `Ничего не найдено по «${objSearch}»` : 'Обработок пока нет — соберите их через чат слева' }}
              </p>
            </section>

            <!-- Gaps (collapsible) -->
            <section v-if="skill.gaps.length" class="overflow-hidden rounded-3xl border border-amber-200 bg-amber-50/40">
              <button type="button" class="flex w-full items-center gap-2 px-5 py-3 text-left" @click="showGaps = !showGaps">
                <ChevronRight class="h-4 w-4 shrink-0 text-amber-500 transition-transform" :class="showGaps && 'rotate-90'" />
                <AlertTriangle class="h-4 w-4 shrink-0 text-amber-500" />
                <span class="text-sm font-bold text-amber-800">Пробелы</span>
                <span class="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-700">{{ skill.gaps.length }}</span>
                <span class="ml-1 text-xs text-amber-700/70">нет готовых фраз эксперта</span>
              </button>
              <div v-show="showGaps" class="space-y-2 border-t border-amber-200 px-4 py-3">
                <div
                  v-for="(gap, gi) in skill.gaps"
                  :key="`gap-${gi}`"
                  class="flex items-start justify-between gap-3 rounded-2xl border border-amber-200 bg-white/70 p-3"
                >
                  <div class="min-w-0 flex-1">
                    <p class="text-sm font-medium text-amber-900">{{ gap.situation }}</p>
                    <p v-if="gap.trigger_when" class="mt-0.5 text-xs text-amber-700/80">{{ gap.trigger_when }}</p>
                  </div>
                  <div class="flex shrink-0 items-center gap-1.5">
                    <button
                      type="button"
                      class="rounded-lg border border-indigo-200 bg-white px-2.5 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-50"
                      title="Заполнить пробел — добавить обработку с этой ситуацией"
                      @click="fillGap(gi)"
                    >
                      Заполнить
                    </button>
                    <button
                      type="button"
                      class="rounded-lg p-1.5 text-amber-400 hover:bg-amber-100 hover:text-red-500"
                      @click="skill.gaps.splice(gi, 1); markDirty()"
                    >
                      <Trash2 class="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              </div>
            </section>

            <!-- Facts / endings (collapsible) -->
            <section v-if="facts.length || endings.length" class="overflow-hidden rounded-3xl border border-slate-100 bg-white shadow-[0_2px_12px_-4px_rgba(0,0,0,0.04)]">
              <button type="button" class="flex w-full items-center gap-2 px-5 py-3 text-left" @click="showExtra = !showExtra">
                <ChevronRight class="h-4 w-4 shrink-0 text-slate-400 transition-transform" :class="showExtra && 'rotate-90'" />
                <span class="text-sm font-bold text-slate-900">Факты и завершения</span>
                <span class="ml-1 text-xs text-slate-400">{{ facts.length }} факт(ов) · {{ endings.length }} завершени(й)</span>
              </button>
              <div v-show="showExtra" class="grid gap-3 border-t border-slate-100 px-5 py-4 md:grid-cols-2">
                <div>
                  <h4 class="text-[9px] font-black uppercase tracking-wider text-slate-400">Факты из инструментов</h4>
                  <ul class="mt-2 space-y-1 text-xs text-slate-600">
                    <li v-for="(f, i) in facts" :key="`fact-${i}`" class="flex gap-1.5">
                      <span class="text-slate-300">·</span><span>{{ f }}</span>
                    </li>
                    <li v-if="!facts.length" class="text-slate-400">—</li>
                  </ul>
                </div>
                <div>
                  <h4 class="text-[9px] font-black uppercase tracking-wider text-slate-400">Варианты завершений</h4>
                  <ul class="mt-2 space-y-1 text-xs text-slate-600">
                    <li v-for="(e, i) in endings" :key="`end-${i}`" class="flex gap-1.5">
                      <span class="text-slate-300">·</span><span>{{ e }}</span>
                    </li>
                    <li v-if="!endings.length" class="text-slate-400">—</li>
                  </ul>
                </div>
              </div>
            </section>
          </template>
            </div>

          </div>
          <!-- /ПРАВО -->
        </div>
      </template>

      <!-- Sticky save bar -->
      <div
        v-if="skill && dirty"
        class="sticky bottom-4 z-30 flex items-center justify-between gap-3 rounded-2xl border border-indigo-200 bg-white/95 px-4 py-3 shadow-[0_10px_30px_-10px_rgba(0,0,0,0.15)] backdrop-blur"
      >
        <span class="text-sm text-slate-600">Есть несохранённые правки навыка</span>
        <div class="flex items-center gap-2">
          <button
            type="button"
            class="rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-sm font-semibold text-slate-600 hover:bg-slate-50"
            @click="reload"
          >
            Отменить
          </button>
          <button
            type="button"
            :disabled="saving"
            class="inline-flex items-center gap-1.5 rounded-xl bg-indigo-600 px-4 py-1.5 text-sm font-bold text-white hover:bg-indigo-700 disabled:opacity-50"
            @click="save"
          >
            <Loader2 v-if="saving" class="h-4 w-4 animate-spin" />
            Сохранить
          </button>
        </div>
      </div>
    </div>

    <SkillServicePicker
      :open="pickerOpen"
      :agent-id="agentId"
      :model-value="flow?.service_external_ids || []"
      :saving="savingLink"
      @update:open="pickerOpen = $event"
      @save="handleSaveLink"
    />
  </AgentPageShell>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { navigateTo, useRoute } from '#app'
import {
  AlertTriangle,
  ArrowLeft,
  Bot,
  Check,
  ChevronRight,
  ChevronsDownUp,
  ChevronsUpDown,
  Copy,
  FileText,
  GraduationCap,
  Inbox,
  LayoutList,
  Loader2,
  MessageSquare,
  Mic,
  MicOff,
  Paperclip,
  Plus,
  Search,
  SendHorizontal,
  Sparkles,
  Square,
  Stethoscope,
  Trash2,
  UploadCloud,
  X,
} from 'lucide-vue-next'
import AgentPageShell from '~/components/agents/AgentPageShell.vue'
import SkillServicePicker from '~/components/agents/skills/SkillServicePicker.vue'
import { useExpertSkills } from '~/composables/useExpertSkills'
import { useToast } from '~/composables/useToast'
import { createSafeMarkdownRenderer } from '~/utils/safe-markdown'
import type {
  ExpertSkill,
  SkillDoc,
  SkillGap,
  SkillObjection,
  SkillPhraseLevel,
  SkillStage,
} from '~/types/scriptFlow'

definePageMeta({
  layout: 'agent' as any,
  middleware: 'auth',
})

const route = useRoute()
const agentId = route.params.id as string
const skillId = route.params.skillId as string
const {
  getSkill,
  updateSkill,
  publishSkill,
  updateSkillDoc,
  skillChat,
  skillChatStream,
  getSkillChatModels,
} = useExpertSkills(agentId)
const { success: toastSuccess, error: toastError } = useToast()

const levels: SkillPhraseLevel[] = ['пример', 'дословно', 'обязательно']

const STAGE_ORDER: SkillStage[] = [
  'приветствие', 'уточнение', 'презентация', 'цена', 'возражения', 'запись', 'завершение', 'другое',
]
const STAGE_LABELS: Record<SkillStage, string> = {
  'приветствие': 'Приветствие',
  'уточнение': 'Уточнение потребности',
  'презентация': 'Презентация',
  'цена': 'Цена',
  'возражения': 'Возражения и сомнения',
  'запись': 'Запись',
  'завершение': 'Завершение',
  'другое': 'Другое',
}
const stageGroups = computed(() => {
  const objs = skill.value?.objections ?? []
  return STAGE_ORDER
    .map((stage) => ({
      stage,
      label: STAGE_LABELS[stage],
      objections: objs.filter((o) => (o.stage || 'другое') === stage),
    }))
    .filter((g) => g.objections.length > 0)
})

// ветки с учётом поиска (для редактируемого вида «Навык»)
const visibleStageGroups = computed(() => {
  const items = visibleObjections.value
  return STAGE_ORDER
    .map((stage) => ({
      stage,
      label: STAGE_LABELS[stage],
      items: items.filter(({ obj }) => (obj.stage || 'другое') === stage),
    }))
    .filter((g) => g.items.length > 0)
})

const flow = ref<ExpertSkill | null>(null)
const skill = ref<SkillDoc | null>(null)
const nameDraft = ref('')
const loading = ref(true)

const saveName = async () => {
  const name = nameDraft.value.trim()
  if (!flow.value || !name || name === flow.value.name) {
    nameDraft.value = flow.value?.name || ''
    return
  }
  try {
    const updated = await updateSkill(skillId, { name })
    flow.value = updated
    nameDraft.value = updated.name
    toastSuccess('Навык переименован')
  } catch (err: unknown) {
    nameDraft.value = flow.value?.name || ''
    toastError(err instanceof Error ? err.message : 'Не удалось переименовать')
  }
}
const saving = ref(false)
const publishing = ref(false)
const dirty = ref(false)

const facts = computed(() => skill.value?.facts_from_tool ?? [])
const endings = computed(() => skill.value?.endings ?? [])

// ── UX-состояние вкладки «Структура» ──────────────────────────────────────────
const objSearch = ref('')
const showFullText = ref(false)
const showContext = ref(false)
const showGaps = ref(false)
const showExtra = ref(false)
const copied = ref(false)
// открытые карточки обработок — по ссылке на объект (устойчиво к смене индексов)
const openObjs = reactive(new Set<SkillObjection>())
// раскрытые «Тонкости» внутри обработки
const openDetails = reactive(new Set<SkillObjection>())
const isDetailsOpen = (obj: SkillObjection) => openDetails.has(obj)
const toggleDetails = (obj: SkillObjection) => {
  if (openDetails.has(obj)) openDetails.delete(obj)
  else openDetails.add(obj)
}
// показаны ли варианты-ответы (кроме основного)
const openVariants = reactive(new Set<SkillObjection>())
const isVariantsOpen = (obj: SkillObjection) => openVariants.has(obj)
const toggleVariants = (obj: SkillObjection) => {
  if (openVariants.has(obj)) openVariants.delete(obj)
  else openVariants.add(obj)
}

const phraseCount = computed(
  () => (skill.value?.objections ?? []).reduce((n, o) => n + (o.phrases?.length ?? 0), 0),
)

// готовность навыка: доля проработанных ситуаций (обработки против обработок+пробелов)
const readinessPct = computed(() => {
  const obj = skill.value?.objections.length ?? 0
  const gaps = skill.value?.gaps.length ?? 0
  const denom = obj + gaps
  return denom > 0 ? Math.round((obj / denom) * 100) : 0
})
const readinessLabel = computed(() => {
  const p = readinessPct.value
  if (p >= 85) return 'Ассистент готов к работе'
  if (p >= 60) return 'Ассистент почти готов'
  if (p >= 30) return 'Навык набирает форму'
  return 'Только начинаем собирать'
})
// покрытие тем: сколько из 7 этапов диалога заполнено
const coveragePct = computed(() => {
  const stages = new Set(
    (skill.value?.objections ?? [])
      .map((o) => o.stage || 'другое')
      .filter((s) => s !== 'другое'),
  )
  return Math.round((stages.size / 7) * 100)
})

const visibleObjections = computed(() => {
  const list = (skill.value?.objections ?? []).map((obj, index) => ({ obj, index }))
  const q = objSearch.value.trim().toLowerCase()
  if (!q) return list
  return list.filter(({ obj }) =>
    obj.situation.toLowerCase().includes(q) ||
    obj.trigger_when.toLowerCase().includes(q) ||
    obj.approach.toLowerCase().includes(q) ||
    obj.phrases.some((p) => p.text.toLowerCase().includes(q)),
  )
})

const allExpanded = computed(() => {
  const objs = skill.value?.objections ?? []
  return objs.length > 0 && objs.every((o) => openObjs.has(o))
})

const isOpen = (obj: SkillObjection) => openObjs.has(obj)
const toggleOpen = (obj: SkillObjection) => {
  if (openObjs.has(obj)) openObjs.delete(obj)
  else openObjs.add(obj)
}
const expandAll = () => {
  for (const o of skill.value?.objections ?? []) openObjs.add(o)
}
const collapseAll = () => openObjs.clear()

const LEVEL_DOT: Record<SkillPhraseLevel, string> = {
  'обязательно': 'bg-rose-500',
  'дословно': 'bg-indigo-500',
  'пример': 'bg-slate-300',
}
const levelDots = (obj: SkillObjection) =>
  obj.phrases.slice(0, 4).map((p) => LEVEL_DOT[p.level] ?? 'bg-slate-300')

// показательная фраза для линии диалога: обязательная → дословная → первая
const firstPhrase = (obj: SkillObjection): string => {
  const byLevel = (lvl: SkillPhraseLevel) => obj.phrases.find((p) => p.level === lvl)?.text
  return (byLevel('обязательно') || byLevel('дословно') || obj.phrases[0]?.text || '').trim()
}

const fullText = computed(() => {
  const s = skill.value
  if (!s) return ''
  const out: string[] = [`# Навык: ${flow.value?.name || ''}`.trim()]
  if (s.context) out.push('', s.context)
  if (s.objections.length) {
    out.push('', '## Как вести диалог по этапам')
    for (const stage of STAGE_ORDER) {
      const stageObjs = s.objections.filter((o) => (o.stage || 'другое') === stage)
      if (!stageObjs.length) continue
      out.push('', `### ${STAGE_LABELS[stage]}`)
      for (const o of stageObjs) {
        out.push('', o.trigger_when ? `— Если клиент: ${o.trigger_when}` : `— ${o.situation || '(без ситуации)'}`)
        if (o.trigger_when && o.situation) out.push(`  (${o.situation})`)
        if (o.approach) out.push(`  Подход: ${o.approach}`)
        for (const p of o.phrases) out.push(`    [${p.level}] ${p.text}`)
        if (o.forbidden.length) out.push(`  Избегать: ${o.forbidden.join('; ')}`)
      }
    }
  }
  if (s.gaps.length) {
    out.push('', '## Пробелы (нет фраз эксперта)')
    for (const g of s.gaps) out.push(`  · ${g.situation}${g.trigger_when ? ` — ${g.trigger_when}` : ''}`)
  }
  if (facts.value.length) {
    out.push('', '## Факты из инструментов')
    for (const f of facts.value) out.push(`  · ${f}`)
  }
  if (endings.value.length) {
    out.push('', '## Завершения')
    for (const e of endings.value) out.push(`  · ${e}`)
  }
  return out.join('\n')
})

const copyFullText = async () => {
  try {
    await navigator.clipboard.writeText(fullText.value)
    copied.value = true
    setTimeout(() => (copied.value = false), 1500)
  } catch {
    toastError('Не удалось скопировать')
  }
}

const markDirty = () => {
  dirty.value = true
}

const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v))

const reload = async () => {
  loading.value = true
  try {
    const f = await getSkill(skillId)
    flow.value = f
    nameDraft.value = f.name
    skill.value = f.skill_doc ? clone(f.skill_doc) : null
    openObjs.clear()
    openDetails.clear()
    pendingAdditions.value = null
    dirty.value = false
  } catch (err: unknown) {
    toastError(err instanceof Error ? err.message : 'Не удалось загрузить навык')
  } finally {
    loading.value = false
  }
}

const save = async () => {
  if (!skill.value) return
  saving.value = true
  try {
    const res = await updateSkillDoc(skillId, skill.value)
    skill.value = clone(res.skill_doc)
    dirty.value = false
    toastSuccess('Навык сохранён')
  } catch (err: unknown) {
    toastError(err instanceof Error ? err.message : 'Не удалось сохранить навык')
  } finally {
    saving.value = false
  }
}

const handlePublish = async () => {
  // сохраним несохранённые правки навыка перед публикацией
  if (dirty.value && skill.value) {
    try {
      await save()
    } catch {
      /* save() уже показал ошибку */
    }
  }
  publishing.value = true
  try {
    await publishSkill(skillId)
    await reload()
    toastSuccess('Навык опубликован — рантайм начнёт его использовать')
  } catch (err: unknown) {
    toastError(err instanceof Error ? err.message : 'Не удалось опубликовать навык')
  } finally {
    publishing.value = false
  }
}

// ── AI-ассистент авторинга ────────────────────────────────────────────────────
const chat = ref<Array<{ role: 'user' | 'assistant'; content: string }>>([])
const chatInput = ref('')
const chatBusy = ref(false)
const MODEL_LS_KEY = 'skill_chat_model'
const chatModels = ref<Array<{ id: string; label: string; hint: string }>>([])
const chatModel = ref<string>('')

const persistChatModel = () => {
  try {
    localStorage.setItem(MODEL_LS_KEY, chatModel.value)
  } catch {
    /* localStorage может быть недоступен */
  }
}

const loadChatModels = async () => {
  try {
    const res = await getSkillChatModels()
    chatModels.value = res.models
    const saved = (() => {
      try { return localStorage.getItem(MODEL_LS_KEY) } catch { return null }
    })()
    const valid = res.models.some((m) => m.id === saved)
    chatModel.value = valid && saved ? saved : (res.default || res.models[0]?.id || '')
  } catch {
    /* если список не загрузился — бэкенд возьмёт модель по умолчанию */
  }
}
const attachments = ref<Array<{ name: string; text: string }>>([])
const chatScroll = ref<HTMLElement | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const chatTextarea = ref<HTMLTextAreaElement | null>(null)
let chatController: AbortController | null = null

// авто-рост поля ввода по содержимому (до предела max-h-40 = 160px)
const autoGrow = () => {
  const el = chatTextarea.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 160)}px`
}
// программные изменения (голос, подсказки, очистка) — тоже пересчитать высоту
watch(chatInput, () => {
  void nextTick(autoGrow)
})

// ── Markdown в сообщениях ─────────────────────────────────────────────────────
const md = createSafeMarkdownRenderer({ linkify: true, breaks: true, typographer: true })
const renderMd = (content: unknown) => (typeof content === 'string' ? md.render(content) : '')

// ── Голосовой ввод (Web Speech API) ───────────────────────────────────────────
const recording = ref(false)
const voiceSupported = ref(false)
let recognition: any = null

const setupVoice = () => {
  if (typeof window === 'undefined') return
  const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
  if (!SR) return
  voiceSupported.value = true
  recognition = new SR()
  recognition.lang = 'ru-RU'
  recognition.interimResults = true
  recognition.continuous = true
  let base = ''
  recognition.onresult = (e: any) => {
    let interim = ''
    let final = ''
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const t = e.results[i][0].transcript
      if (e.results[i].isFinal) final += t
      else interim += t
    }
    if (final) base = (base + final).replace(/\s+/g, ' ')
    chatInput.value = (base + interim).trim()
  }
  recognition.onend = () => {
    recording.value = false
  }
  recognition.onerror = () => {
    recording.value = false
  }
  const _start = recognition.start.bind(recognition)
  recognition.start = () => {
    base = chatInput.value ? chatInput.value + ' ' : ''
    _start()
  }
}

const toggleVoice = () => {
  if (!recognition) return
  if (recording.value) {
    recognition.stop()
    recording.value = false
  } else {
    try {
      recognition.start()
      recording.value = true
    } catch {
      recording.value = false
    }
  }
}

const stopChat = () => {
  chatController?.abort()
}

const scrollChat = async () => {
  await nextTick()
  if (chatScroll.value) chatScroll.value.scrollTop = chatScroll.value.scrollHeight
}

// Предложение ассистента (дельта), ожидающее подтверждения (Принять/Отклонить)
const pendingAdditions = ref<{ objections: SkillObjection[]; gaps: SkillGap[] } | null>(null)

const emptySkill = (): SkillDoc => ({
  context: '',
  objections: [],
  sequence: [],
  facts_from_tool: [],
  endings: [],
  gaps: [],
})

const acceptPending = () => {
  const add = pendingAdditions.value
  if (!add) return
  const doc = skill.value ? clone(skill.value) : emptySkill()
  doc.objections.push(...add.objections)
  doc.gaps.push(...add.gaps)
  skill.value = doc
  pendingAdditions.value = null
  markDirty()
}
const rejectPending = () => {
  pendingAdditions.value = null
}

// файлы, читаемые прямо сейчас (с прогрессом)
const reading = ref<Array<{ id: number; name: string; percent: number }>>([])
let readSeq = 0

const readFileWithProgress = (
  file: File,
  entry: { percent: number },
): Promise<string> =>
  new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onprogress = (e) => {
      if (e.lengthComputable) entry.percent = Math.round((e.loaded / e.total) * 100)
    }
    reader.onload = () => {
      entry.percent = 100
      resolve(String(reader.result || ''))
    }
    reader.onerror = () => reject(reader.error)
    reader.readAsText(file)
  })

const addFiles = async (files: FileList | File[] | null | undefined) => {
  if (!files) return
  for (const f of Array.from(files)) {
    const entry = { id: ++readSeq, name: f.name, percent: 0 }
    reading.value.push(entry)
    try {
      const text = await readFileWithProgress(f, entry)
      attachments.value.push({ name: f.name, text })
    } catch {
      toastError(`Не удалось прочитать файл ${f.name}`)
    } finally {
      reading.value = reading.value.filter((r) => r.id !== entry.id)
    }
  }
}

const onFiles = async (e: Event) => {
  await addFiles((e.target as HTMLInputElement).files)
  if (fileInput.value) fileInput.value.value = ''
}

// ── Drag & drop файлов в чат ───────────────────────────────────────────────────
const dragActive = ref(false)
let dragDepth = 0
const onDragEnter = () => {
  dragDepth += 1
  dragActive.value = true
}
const onDragLeave = () => {
  dragDepth = Math.max(0, dragDepth - 1)
  if (dragDepth === 0) dragActive.value = false
}
const onDrop = async (e: DragEvent) => {
  dragDepth = 0
  dragActive.value = false
  await addFiles(e.dataTransfer?.files)
}

const removeMsg = (m: { role: string; content: string }) => {
  const ai = chat.value.indexOf(m)
  if (ai >= 0) chat.value.splice(ai, 1)
}

const sendChat = async () => {
  const text = chatInput.value.trim()
  if ((!text && !attachments.value.length) || chatBusy.value) return
  if (text) chat.value.push({ role: 'user', content: text })
  const sentAttachments = [...attachments.value]
  const history = [...chat.value] // без плейсхолдера ассистента — это и уходит на бэкенд
  chatInput.value = ''
  attachments.value = []
  chatBusy.value = true
  chatController = new AbortController()
  const assistantMsg = reactive({ role: 'assistant' as const, content: '' })
  chat.value.push(assistantMsg)
  await scrollChat()

  const payload = {
    messages: history,
    attachments: sentAttachments,
    skill_doc: skill.value,
    model: chatModel.value || undefined,
  }
  const applyResult = (res: { reply: string; additions: { objections: SkillObjection[]; gaps: SkillGap[] } } | null) => {
    if (!res) return
    if (res.reply) assistantMsg.content = res.reply
    const add = res.additions
    if (add && (add.objections.length || add.gaps.length)) pendingAdditions.value = add
  }

  try {
    const res = await skillChatStream(skillId, payload, {
      signal: chatController.signal,
      onDelta: (t) => {
        assistantMsg.content += t
        void scrollChat()
      },
    })
    applyResult(res)
    // стрим прошёл, но текста нет — добираем обычным запросом
    if (!assistantMsg.content.trim() && !pendingAdditions.value) {
      applyResult(await skillChat(skillId, payload))
    }
  } catch (err: unknown) {
    if (chatController?.signal.aborted) {
      removeMsg(assistantMsg)
      if (text) chatInput.value = text
      if (chat.value[chat.value.length - 1]?.role === 'user') chat.value.pop()
      attachments.value = sentAttachments
    } else {
      // стрим не сработал (нет эндпоинта/ошибка) — пробуем обычный запрос
      try {
        applyResult(await skillChat(skillId, payload))
      } catch (err2: unknown) {
        toastError(err2 instanceof Error ? err2.message : 'Ассистент недоступен')
      }
    }
  } finally {
    // если ответ так и остался пустым — убрать пустой пузырь
    if (!assistantMsg.content.trim()) removeMsg(assistantMsg)
    chatBusy.value = false
    chatController = null
    void nextTick(autoGrow)
    await scrollChat()
  }
}

// ── Редактирование структуры ──────────────────────────────────────────────────
const addObjection = () => {
  if (!skill.value) return
  const obj: SkillObjection = {
    situation: '',
    trigger_when: '',
    stage: 'другое',
    approach: '',
    phrases: [{ text: '', level: 'пример' }],
    forbidden: [],
  }
  skill.value.objections.push(obj)
  objSearch.value = ''
  openObjs.add(obj) // сразу раскрыть новую карточку
  markDirty()
}
const removeObjection = (i: number) => {
  skill.value?.objections.splice(i, 1)
  markDirty()
}
const addPhrase = (obj: SkillObjection) => {
  obj.phrases.push({ text: '', level: 'пример' })
  markDirty()
}
const removePhrase = (obj: SkillObjection, i: number) => {
  obj.phrases.splice(i, 1)
  markDirty()
}
const fillGap = (gi: number) => {
  const gap = skill.value?.gaps[gi]
  if (!gap || !skill.value) return
  const obj: SkillObjection = {
    situation: gap.situation,
    trigger_when: gap.trigger_when,
    stage: 'другое',
    approach: '',
    phrases: [{ text: '', level: 'пример' }],
    forbidden: [],
  }
  skill.value.objections.push(obj)
  skill.value.gaps.splice(gi, 1)
  objSearch.value = ''
  openObjs.add(obj)
  markDirty()
}

const levelActiveClass = (lvl: SkillPhraseLevel) => {
  if (lvl === 'обязательно') return 'bg-rose-500 text-white'
  if (lvl === 'дословно') return 'bg-indigo-500 text-white'
  return 'bg-slate-600 text-white'
}
const levelHint = (lvl: SkillPhraseLevel) => {
  if (lvl === 'обязательно') return 'Критичная формулировка — использовать буквально'
  if (lvl === 'дословно') return 'Сохранять формулировку максимально близко'
  return 'Образец интонации — можно адаптировать'
}

// ── Услуги ────────────────────────────────────────────────────────────────────
const pickerOpen = ref(false)
const savingLink = ref(false)
const handleSaveLink = async (ids: string[]) => {
  savingLink.value = true
  try {
    const updated = await updateSkill(skillId, { service_external_ids: ids })
    flow.value = updated
    toastSuccess('Услуги навыка обновлены')
    pickerOpen.value = false
  } catch (err: unknown) {
    toastError(err instanceof Error ? err.message : 'Не удалось сохранить услуги')
  } finally {
    savingLink.value = false
  }
}

onMounted(() => {
  reload()
  loadChatModels()
  setupVoice()
})
</script>

<style scoped>
.markdown-content :deep(p) { margin-bottom: 0.4rem; }
.markdown-content :deep(p:last-child) { margin-bottom: 0; }
.markdown-content :deep(ul), .markdown-content :deep(ol) { margin-left: 1.15rem; margin-bottom: 0.4rem; }
.markdown-content :deep(ul) { list-style-type: disc; }
.markdown-content :deep(ol) { list-style-type: decimal; }
.markdown-content :deep(li) { margin-bottom: 0.15rem; }
.markdown-content :deep(strong) { font-weight: 600; }
.markdown-content :deep(em) { font-style: italic; }
.markdown-content :deep(a) { color: #4f46e5; text-decoration: underline; }
.markdown-content :deep(code) { background-color: #eef2ff; padding: 0.1rem 0.35rem; border-radius: 0.25rem; font-family: monospace; font-size: 0.85em; }
.markdown-content :deep(pre) { background-color: #f1f5f9; padding: 0.75rem; border-radius: 0.5rem; overflow-x: auto; margin-bottom: 0.4rem; }
.markdown-content :deep(pre code) { background-color: transparent; padding: 0; }
.markdown-content :deep(blockquote) { border-left: 3px solid #c7d2fe; padding-left: 0.6rem; color: #475569; margin: 0.3rem 0; }
.markdown-content :deep(h1), .markdown-content :deep(h2), .markdown-content :deep(h3) { font-weight: 700; margin: 0.4rem 0 0.2rem; }
.markdown-content :deep(table) { border-collapse: collapse; margin: 0.3rem 0; }
.markdown-content :deep(th), .markdown-content :deep(td) { border: 1px solid #e2e8f0; padding: 0.2rem 0.5rem; }
.markdown-content :deep(hr) { border: 0; border-top: 1px solid #e2e8f0; margin: 0.5rem 0; }
</style>
