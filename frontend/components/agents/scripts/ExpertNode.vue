<template>
  <div
    class="relative flex flex-col rounded-xl border-2 bg-card shadow-lg transition-shadow duration-200 hover:shadow-xl overflow-visible"
    :style="{
      borderColor: selected
        ? typeColor
        : isExpanded
          ? `${typeColor}60`
          : 'hsl(var(--border))',
      minWidth: isExpanded ? '360px' : isCondition ? '260px' : '220px',
      maxWidth: isExpanded ? '420px' : isCondition ? '320px' : '300px',
    }"
  >
    <!-- Target handle (left center) -->
    <Handle
      type="target"
      :position="Position.Left"
      id="target"
      class="!w-3 !h-3 !border-2 !border-background"
      :style="{ backgroundColor: typeColor }"
    />

    <!-- Header -->
    <div
      class="flex items-center gap-2 px-3 py-2 rounded-t-xl"
      :style="{ background: `${typeColor}18` }"
    >
      <div class="rounded-md p-1.5 shrink-0" :style="{ background: `${typeColor}25`, color: typeColor }">
        <span class="text-base leading-none select-none">{{ typeEmoji }}</span>
      </div>
      <div class="flex-1 min-w-0">
        <span class="text-xs font-semibold truncate block text-foreground">
          {{ localTitle || typeLabel }}
        </span>
        <span class="text-[10px]" :style="{ color: typeColor }">
          {{ typeLabel }}{{ stageBadge ? ` · ${stageBadge}` : '' }}{{ localLevel > 1 ? ` · L${localLevel}` : '' }}
        </span>
      </div>
      <!-- Close button when expanded -->
      <button
        v-if="isExpanded"
        class="shrink-0 rounded-md p-1 text-muted-foreground/60 hover:text-foreground hover:bg-muted/30 transition-colors"
        title="Свернуть"
        @click.stop="setExpandedNodeId(null)"
        @mousedown.stop
        @pointerdown.stop
      >
        <X class="h-3 w-3" />
      </button>
      <ChevronDown v-else class="h-3 w-3 shrink-0 text-muted-foreground/40" />
    </div>

    <!-- ── EXPANDED FORM (all node types) ─────────────────────────────────── -->
    <div
      v-if="isExpanded"
      class="px-3 py-3 space-y-3 overflow-y-auto nodrag nopan"
      :class="isCondition ? 'border-b' : 'rounded-b-xl'"
      style="max-height: 520px;"
      @click.stop
      @mousedown.stop
      @pointerdown.stop
      @wheel.stop
    >
      <!-- Variable picker (shown when flow variables exist) -->
      <div
        v-if="flowVarNames.length"
        class="rounded-lg border border-dashed border-violet-300/60 bg-violet-50/50 dark:bg-violet-950/20 dark:border-violet-600/30 px-2.5 py-2"
      >
        <p class="text-[9px] font-bold uppercase tracking-wider text-violet-500 mb-1.5">Вставить переменную:</p>
        <div class="flex flex-wrap gap-1">
          <button
            v-for="varName in flowVarNames"
            :key="varName"
            type="button"
            class="rounded-md bg-violet-100 dark:bg-violet-800/40 px-2 py-0.5 text-[10px] font-mono font-semibold text-violet-700 dark:text-violet-300 hover:bg-violet-200 dark:hover:bg-violet-700/40 transition-colors"
            :title="`Вставить {{${varName}}} в активное поле`"
            @click.stop="insertVar(varName)"
          >
            &#123;&#123;{{ varName }}&#125;&#125;
          </button>
        </div>
      </div>

      <!-- Title -->
      <div class="space-y-1">
        <label class="node-label">Заголовок</label>
        <input
          v-model="localTitle"
          type="text"
          class="node-input"
          placeholder="Возражение по цене L1"
          @input="flushNode"
          @focus="lastFocusedField = ''"
        />
      </div>

      <p
        v-if="nodeFormHint"
        class="text-[9px] text-muted-foreground leading-snug -mt-1"
      >
        {{ nodeFormHint }}
      </p>

      <!-- Экспертиза / Вопрос: оси Контекст ↔ Содержание -->
      <template v-if="showAxisTabs">
        <div class="flex rounded-lg border border-border bg-muted/40 p-0.5 gap-0.5">
          <button
            type="button"
            class="flex-1 rounded-md px-2 py-1.5 text-[10px] font-semibold transition-colors"
            :class="axisTab === 'context'
              ? 'bg-background text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground'"
            @click.stop="axisTab = 'context'"
          >
            Контекст
          </button>
          <button
            type="button"
            class="flex-1 rounded-md px-2 py-1.5 text-[10px] font-semibold transition-colors"
            :class="axisTab === 'content'
              ? 'bg-background text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground'"
            @click.stop="axisTab = 'content'"
          >
            {{ isExpertise ? 'Содержание' : 'Формулировки' }}
          </button>
        </div>

        <div v-show="axisTab === 'context'" class="space-y-3 pt-1">
          <div class="grid grid-cols-2 gap-2">
            <div class="space-y-1">
              <label class="node-label">Этап</label>
              <select v-model="localStage" class="node-input" @change="flushNode">
                <option :value="null">— Любой —</option>
                <option v-for="st in CONVERSATION_STAGES" :key="st.value" :value="st.value">
                  {{ st.label }}
                </option>
              </select>
            </div>
            <div class="space-y-1">
              <label class="node-label">Уровень</label>
              <input
                v-model.number="localLevel"
                type="number"
                min="1"
                max="5"
                class="node-input"
                @input="flushNode"
              />
            </div>
          </div>
          <div class="flex items-center justify-between rounded-lg border border-border bg-muted/20 px-2.5 py-2">
            <div>
              <p class="text-[10px] font-semibold text-foreground">Глобальный поиск</p>
              <p class="text-[9px] text-muted-foreground leading-snug">Триггер / экспертиза / вопрос</p>
            </div>
            <button
              type="button"
              class="relative inline-flex h-5 w-9 items-center rounded-full transition-colors shrink-0 ml-2"
              :class="localIsEntryPoint ? 'bg-primary' : 'bg-muted-foreground/30'"
              @click.stop="localIsEntryPoint = !localIsEntryPoint; flushNode()"
            >
              <span
                class="inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform"
                :class="localIsEntryPoint ? 'translate-x-4' : 'translate-x-1'"
              />
            </button>
          </div>
          <div class="grid grid-cols-1 gap-2">
            <div class="space-y-1">
              <label class="node-label">Услуги (опц.)</label>
              <div class="max-h-24 overflow-auto rounded-lg border border-border bg-background p-1.5">
                <button
                  v-for="svc in flowServiceOptions"
                  :key="svc.id"
                  type="button"
                  class="mb-1 mr-1 rounded-full border px-2 py-0.5 text-[10px] transition-colors"
                  :class="localServiceIds.includes(svc.id)
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border text-muted-foreground hover:border-primary/50'"
                  @click.stop="toggleService(svc.id)"
                >
                  {{ svc.name }}
                </button>
                <p v-if="!flowServiceOptions.length" class="text-[10px] text-muted-foreground">
                  Нет доступных услуг
                </p>
              </div>
            </div>
            <div class="space-y-1">
              <label class="node-label">Сотрудники (опц.)</label>
              <div class="max-h-24 overflow-auto rounded-lg border border-border bg-background p-1.5">
                <button
                  v-for="emp in flowEmployeeOptions"
                  :key="emp.id"
                  type="button"
                  class="mb-1 mr-1 rounded-full border px-2 py-0.5 text-[10px] transition-colors"
                  :class="localEmployeeIds.includes(emp.id)
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border text-muted-foreground hover:border-primary/50'"
                  @click.stop="toggleEmployee(emp.id)"
                >
                  {{ emp.name }}
                </button>
                <p v-if="!flowEmployeeOptions.length" class="text-[10px] text-muted-foreground">
                  Нет доступных сотрудников
                </p>
              </div>
            </div>
          </div>
          <div class="border-t border-border/40" />
          <div v-if="isExpertise" class="space-y-1">
            <label class="node-label">Возражение / ситуация клиента</label>
            <textarea
              v-model="localSituation"
              rows="3"
              class="node-input resize-none"
              placeholder="Клиент говорит «дорого» после первого аргумента..."
              @input="flushNode"
              @focus="lastFocusedField = 'situation'"
            />
          </div>
        </div>

        <div v-show="axisTab === 'content'" class="space-y-3 pt-1">
          <template v-if="isExpertise">
            <div class="space-y-1">
              <label class="node-label">Мотив (психология)</label>
              <textarea
                v-model="localWhyItWorks"
                rows="2"
                class="node-input resize-none"
                placeholder="Клиент ещё не видит ценность конкретно для себя..."
                @input="flushNode"
                @focus="lastFocusedField = 'why_it_works'"
              />
            </div>
            <div class="space-y-1">
              <label class="node-label">Аргументы и тактика</label>
              <textarea
                v-model="localApproach"
                rows="3"
                class="node-input resize-none"
                placeholder="Не защищай цену. Переведи разговор на персональную ценность..."
                @input="flushNode"
                @focus="lastFocusedField = 'approach'"
              />
            </div>
            <div class="space-y-1">
              <label class="node-label">Вариативные формулировки (опц.)</label>
              <textarea
                v-model="localExamplePhrasesStr"
                rows="3"
                class="node-input resize-none font-mono text-[10px]"
                placeholder="Каждая фраза с новой строки..."
                @input="flushNode"
                @focus="lastFocusedField = 'example_phrases'"
              />
              <p class="text-[9px] text-muted-foreground">Можно оставить пустым</p>
            </div>
            <div class="space-y-1">
              <label class="node-label flex items-center gap-1">
                <AlertTriangle class="h-2.5 w-2.5 text-orange-400" />
                Табу (не делай)
              </label>
              <textarea
                v-model="localWatchOut"
                rows="2"
                class="node-input resize-none"
                placeholder="Не называй скидки сразу..."
                @input="flushNode"
                @focus="lastFocusedField = 'watch_out'"
              />
            </div>
            <div class="space-y-1">
              <label class="node-label flex items-center gap-1">
                <HelpCircle class="h-2.5 w-2.5 text-amber-500" />
                Уточняющий вопрос (опц.)
              </label>
              <input
                v-model="localGoodQuestion"
                type="text"
                class="node-input"
                placeholder="Дополнительный вопрос после ответа..."
                @input="flushNode"
                @focus="lastFocusedField = 'good_question'"
              />
            </div>
          </template>

          <template v-else-if="isQuestion">
            <div class="space-y-1">
              <label class="node-label flex items-center gap-1">
                <HelpCircle class="h-2.5 w-2.5 text-amber-500" />
                Ключевой вопрос клиенту
              </label>
              <textarea
                v-model="localGoodQuestion"
                rows="2"
                class="node-input resize-none"
                placeholder="Основная формулировка вопроса"
                @input="flushNode"
                @focus="lastFocusedField = 'good_question'"
              />
            </div>
            <div class="space-y-1">
              <label class="node-label">Контекст: когда уместен (опц.)</label>
              <textarea
                v-model="localSituation"
                rows="2"
                class="node-input resize-none"
                placeholder="После какого момента диалога задаём вопрос..."
                @input="flushNode"
                @focus="lastFocusedField = 'situation'"
              />
            </div>
            <div class="space-y-1">
              <label class="node-label">Как подвести к вопросу</label>
              <textarea
                v-model="localApproach"
                rows="2"
                class="node-input resize-none"
                placeholder="Коротко, без давления..."
                @input="flushNode"
                @focus="lastFocusedField = 'approach'"
              />
            </div>
            <div class="space-y-1">
              <label class="node-label">Альтернативные формулировки (опц.)</label>
              <textarea
                v-model="localExamplePhrasesStr"
                rows="3"
                class="node-input resize-none font-mono text-[10px]"
                placeholder="Каждая с новой строки"
                @input="flushNode"
                @focus="lastFocusedField = 'example_phrases'"
              />
            </div>
            <div class="space-y-1">
              <label class="node-label flex items-center gap-1">
                <AlertTriangle class="h-2.5 w-2.5 text-orange-400" />
                Не делай
              </label>
              <textarea
                v-model="localWatchOut"
                rows="2"
                class="node-input resize-none"
                placeholder="Не дави, не перебивай..."
                @input="flushNode"
                @focus="lastFocusedField = 'watch_out'"
              />
            </div>
          </template>
        </div>
      </template>

      <template v-else>
        <!-- Остальные типы нод: прежняя одноколоночная форма -->
        <div class="grid grid-cols-2 gap-2">
          <div class="space-y-1">
            <label class="node-label">Этап</label>
            <select v-model="localStage" class="node-input" @change="flushNode">
              <option :value="null">— Любой —</option>
              <option v-for="st in CONVERSATION_STAGES" :key="st.value" :value="st.value">
                {{ st.label }}
              </option>
            </select>
          </div>
          <div class="space-y-1">
            <label class="node-label">Уровень</label>
            <input
              v-model.number="localLevel"
              type="number"
              min="1"
              max="5"
              class="node-input"
              @input="flushNode"
            />
          </div>
        </div>

        <div class="flex items-center justify-between rounded-lg border border-border bg-muted/20 px-2.5 py-2">
          <div>
            <p class="text-[10px] font-semibold text-foreground">Глобальный поиск</p>
            <p class="text-[9px] text-muted-foreground leading-snug">Авто при публикации · ручное переопределение</p>
          </div>
          <button
            type="button"
            class="relative inline-flex h-5 w-9 items-center rounded-full transition-colors shrink-0 ml-2"
            :class="localIsEntryPoint ? 'bg-primary' : 'bg-muted-foreground/30'"
            @click.stop="localIsEntryPoint = !localIsEntryPoint; flushNode()"
          >
            <span
              class="inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform"
              :class="localIsEntryPoint ? 'translate-x-4' : 'translate-x-1'"
            />
          </button>
        </div>

        <div class="grid grid-cols-1 gap-2">
          <div class="space-y-1">
            <label class="node-label">Услуги (опц.)</label>
            <div class="max-h-24 overflow-auto rounded-lg border border-border bg-background p-1.5">
              <button
                v-for="svc in flowServiceOptions"
                :key="svc.id"
                type="button"
                class="mb-1 mr-1 rounded-full border px-2 py-0.5 text-[10px] transition-colors"
                :class="localServiceIds.includes(svc.id)
                  ? 'border-primary bg-primary/10 text-primary'
                  : 'border-border text-muted-foreground hover:border-primary/50'"
                @click.stop="toggleService(svc.id)"
              >
                {{ svc.name }}
              </button>
              <p v-if="!flowServiceOptions.length" class="text-[10px] text-muted-foreground">
                Нет доступных услуг
              </p>
            </div>
          </div>

          <div class="space-y-1">
            <label class="node-label">Сотрудники (опц.)</label>
            <div class="max-h-24 overflow-auto rounded-lg border border-border bg-background p-1.5">
              <button
                v-for="emp in flowEmployeeOptions"
                :key="emp.id"
                type="button"
                class="mb-1 mr-1 rounded-full border px-2 py-0.5 text-[10px] transition-colors"
                :class="localEmployeeIds.includes(emp.id)
                  ? 'border-primary bg-primary/10 text-primary'
                  : 'border-border text-muted-foreground hover:border-primary/50'"
                @click.stop="toggleEmployee(emp.id)"
              >
                {{ emp.name }}
              </button>
              <p v-if="!flowEmployeeOptions.length" class="text-[10px] text-muted-foreground">
                Нет доступных сотрудников
              </p>
            </div>
          </div>
        </div>

        <div class="border-t border-border/40" />

        <div v-if="!isEnd" class="space-y-1">
          <label class="node-label">Клиент говорит / делает</label>
          <textarea
            v-model="localSituation"
            rows="2"
            class="node-input resize-none"
            :placeholder="isBusinessRule
              ? 'Контекст срабатывания правила (например: клиент просит вечерний слот)'
              : 'Клиент говорит «дорого» после первого аргумента...'"
            @input="flushNode"
            @focus="lastFocusedField = 'situation'"
          />
        </div>

        <template v-if="isConversationNode">
          <div class="space-y-1">
            <label class="node-label">{{ isTrigger ? 'Почему это вход в сценарий' : 'Психология момента' }}</label>
            <textarea
              v-model="localWhyItWorks"
              rows="2"
              class="node-input resize-none"
              :placeholder="isTrigger
                ? 'Почему именно эта реплика должна запускать сценарий...'
                : 'Клиент ещё не видит ценность конкретно для себя...'"
              @input="flushNode"
              @focus="lastFocusedField = 'why_it_works'"
            />
          </div>

          <div class="space-y-1">
            <label class="node-label">
              {{ isQuestion ? 'Как подвести к вопросу' : isGoto ? 'Как оформить переход' : 'Тактика ответа' }}
            </label>
            <textarea
              v-model="localApproach"
              rows="3"
              class="node-input resize-none"
              :placeholder="isQuestion
                ? 'Коротко подведи к уточняющему вопросу без давления...'
                : isGoto
                  ? 'Когда и зачем делать переход в другую ветку/поток...'
                  : 'Не защищай цену. Переведи разговор на персональную ценность...'"
              @input="flushNode"
              @focus="lastFocusedField = 'approach'"
            />
          </div>

          <div class="space-y-1">
            <label class="node-label">{{ isQuestion ? 'Формулировки вопроса' : 'Примеры фраз' }}</label>
            <textarea
              v-model="localExamplePhrasesStr"
              rows="3"
              class="node-input resize-none font-mono text-[10px]"
              placeholder="Каждая фраза с новой строки:&#10;Понимаю, давайте посмотрим что именно вам нужно..."
              @input="flushNode"
              @focus="lastFocusedField = 'example_phrases'"
            />
            <p class="text-[9px] text-muted-foreground">Каждая фраза с новой строки</p>
          </div>

          <div class="space-y-1">
            <label class="node-label flex items-center gap-1">
              <AlertTriangle class="h-2.5 w-2.5 text-orange-400" />
              Не делай
            </label>
            <textarea
              v-model="localWatchOut"
              rows="2"
              class="node-input resize-none"
              placeholder="Не называй скидки сразу — это обесценит предложение"
              @input="flushNode"
              @focus="lastFocusedField = 'watch_out'"
            />
          </div>

          <div class="space-y-1">
            <label class="node-label flex items-center gap-1">
              <HelpCircle class="h-2.5 w-2.5 text-amber-500" />
              Вопрос для диалога
            </label>
            <input
              v-model="localGoodQuestion"
              type="text"
              class="node-input"
              placeholder="Вы уже оценивали мышечные паттерны вашего лица?"
              @input="flushNode"
              @focus="lastFocusedField = 'good_question'"
            />
          </div>
        </template>
      </template>

      <!-- Business rule fields -->
      <template v-if="isBusinessRule">
        <div class="space-y-1">
          <label class="node-label">Источник данных</label>
          <select v-model="localDataSource" class="node-input" @change="flushNode">
            <option value="sqns_resources">Таблица сотрудников</option>
            <option value="sqns_services">Таблица услуг</option>
            <option value="custom_table">Другая таблица</option>
          </select>
        </div>

        <div class="grid grid-cols-2 gap-2">
          <div class="space-y-1">
            <label class="node-label">Тип сущности</label>
            <select v-model="localEntityType" class="node-input" @change="flushNode">
              <option value="employee">Сотрудник</option>
              <option value="service">Услуга</option>
              <option value="custom">Custom</option>
            </select>
          </div>
          <div class="space-y-1">
            <label class="node-label">Приоритет</label>
            <input
              v-model.number="localRulePriority"
              type="number"
              min="1"
              max="999"
              class="node-input"
              @input="flushNode"
            />
          </div>
        </div>

        <div class="space-y-1">
          <label class="node-label">Сущность</label>
          <select
            v-if="localEntityType !== 'custom'"
            v-model="localEntityId"
            class="node-input"
            @change="flushNode"
          >
            <option value="">— выбрать —</option>
            <option
              v-for="opt in (localEntityType === 'employee' ? flowEmployeeOptions : flowServiceOptions)"
              :key="opt.id"
              :value="opt.id"
            >
              {{ opt.name }}
            </option>
          </select>
          <input
            v-else
            v-model="localEntityId"
            type="text"
            class="node-input"
            placeholder="ID/ключ сущности"
            @input="flushNode"
          />
        </div>

        <div class="space-y-1">
          <label class="node-label">Условие правила</label>
          <textarea
            v-model="localRuleCondition"
            rows="2"
            class="node-input resize-none"
            placeholder="Если клиент просит вечернее время..."
            @input="flushNode"
          />
        </div>

        <div class="grid grid-cols-2 gap-2">
          <div class="space-y-1">
            <label class="node-label">Обязательная сущность</label>
            <select v-model="localRequiresEntity" class="node-input" @change="flushNode">
              <option value="none">Не требуется</option>
              <option value="service">Только услуга</option>
              <option value="employee">Только сотрудник</option>
              <option value="both">И услуга, и сотрудник</option>
            </select>
          </div>
          <div class="space-y-1">
            <label class="node-label">После нод (обязательно)</label>
            <div class="max-h-24 overflow-auto rounded-lg border border-border bg-background p-1.5">
              <button
                v-for="nref in flowNodeRefOptions.filter((n) => n.id !== id)"
                :key="nref.id"
                type="button"
                class="mb-1 mr-1 rounded-full border px-2 py-0.5 text-[10px] transition-colors"
                :class="localMustFollowNodeRefs.includes(nref.id)
                  ? 'border-primary bg-primary/10 text-primary'
                  : 'border-border text-muted-foreground hover:border-primary/50'"
                @click.stop="toggleMustFollowNodeRef(nref.id)"
              >
                {{ nref.title }} · {{ nref.id }}
              </button>
              <p v-if="!flowNodeRefOptions.length" class="text-[10px] text-muted-foreground">
                Ноды не найдены
              </p>
            </div>
          </div>
        </div>

        <div class="space-y-1">
          <label class="node-label">Действие правила</label>
          <textarea
            v-model="localRuleAction"
            rows="2"
            class="node-input resize-none"
            placeholder="Предлагать только слоты после 18:00 по вт/чт..."
            @input="flushNode"
          />
        </div>

        <div class="flex items-center justify-between rounded-lg border border-border bg-muted/20 px-2.5 py-2">
          <p class="text-[10px] font-semibold text-foreground">Правило активно</p>
          <button
            type="button"
            class="relative inline-flex h-5 w-9 items-center rounded-full transition-colors shrink-0 ml-2"
            :class="localRuleActive ? 'bg-primary' : 'bg-muted-foreground/30'"
            @click.stop="localRuleActive = !localRuleActive; flushNode()"
          >
            <span
              class="inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform"
              :class="localRuleActive ? 'translate-x-4' : 'translate-x-1'"
            />
          </button>
        </div>
      </template>

      <!-- End node fields -->
      <template v-else-if="isEnd">
        <div class="space-y-1">
          <label class="node-label">Итог ветки</label>
          <select v-model="localOutcomeType" class="node-input" @change="flushNode">
            <option :value="null">— Не указан —</option>
            <option v-for="opt in OUTCOME_OPTIONS" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </div>
        <div class="space-y-1">
          <label class="node-label">Финальное действие агента</label>
          <textarea
            v-model="localFinalAction"
            rows="2"
            class="node-input resize-none"
            placeholder="Предложи записаться на ближайшее время..."
            @input="flushNode"
            @focus="lastFocusedField = 'final_action'"
          />
          <p class="text-[9px] text-muted-foreground">Что должен сделать агент достигнув этого узла</p>
        </div>
      </template>
    </div>

    <!-- ── CONDITION rows (always visible for condition nodes) ─────────────── -->
    <template v-if="isCondition">
      <div class="px-3 pt-2 pb-1 space-y-1.5 rounded-b-xl">

        <!-- Situation hint when collapsed -->
        <p v-if="!isExpanded && localSituation" class="text-[10px] text-muted-foreground leading-relaxed line-clamp-2 mb-1">
          {{ localSituation }}
        </p>

        <!-- Condition rows -->
        <div
          v-for="(cond, i) in localConditions"
          :key="`row-${i}`"
          class="group relative flex items-center gap-1 rounded-lg pr-6"
          :style="{ background: `${typeColor}0e`, borderLeft: `2px solid ${typeColor}50` }"
        >
          <button
            class="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity w-5 h-5 flex items-center justify-center rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10 ml-1 my-1"
            title="Удалить вариант"
            @mousedown.stop
            @click.stop="removeCondition(i)"
          >
            <span class="text-[10px] font-bold leading-none">✕</span>
          </button>

          <input
            :value="cond"
            type="text"
            class="flex-1 min-w-0 bg-transparent text-[11px] font-medium text-foreground/80 py-1.5 focus:outline-none placeholder:text-muted-foreground/50"
            :placeholder="`Вариант ${i + 1}…`"
            @mousedown.stop
            @input="updateCondition(i, ($event.target as HTMLInputElement).value)"
          />

          <Handle
            type="source"
            :position="Position.Right"
            :id="`cond-${i}`"
            class="!w-3.5 !h-3.5 !border-2 !border-background !absolute !right-1.5 !top-1/2 !-translate-y-1/2 !transform"
            :style="{ backgroundColor: typeColor }"
          />
        </div>

        <!-- Add condition button -->
        <button
          class="w-full flex items-center justify-center gap-1.5 rounded-lg border border-dashed py-1 text-[10px] font-medium transition-colors"
          :style="{ borderColor: `${typeColor}50`, color: typeColor }"
          @mousedown.stop
          @click.stop="addCondition"
        >
          <span class="text-sm leading-none">+</span>
          Добавить вариант
        </button>

        <!-- Default fallback row -->
        <div
          class="relative flex items-center gap-1 rounded-lg pr-6 mb-1"
          :style="{ background: 'hsl(var(--muted)/0.4)', borderLeft: '2px solid hsl(var(--border))' }"
        >
          <span class="flex-1 min-w-0 pl-2 py-1.5 text-[10px] italic text-muted-foreground select-none">
            По умолчанию
          </span>
          <Handle
            type="source"
            :position="Position.Right"
            id="cond-default"
            class="!w-3.5 !h-3.5 !border-2 !border-background !absolute !right-1.5 !top-1/2 !-translate-y-1/2 !transform"
            style="background: hsl(var(--muted-foreground)/0.5)"
          />
        </div>
      </div>
    </template>

    <!-- ── COLLAPSED PREVIEW (non-condition, non-expanded) ──────────────────── -->
    <template v-else-if="!isExpanded">
      <div class="flex-1 px-3 py-2.5 space-y-1.5">
        <p v-if="localSituation" class="text-[11px] leading-relaxed text-foreground/80 line-clamp-2">
          {{ localSituation }}
        </p>
        <p v-else-if="localApproach" class="text-[11px] leading-relaxed text-muted-foreground line-clamp-2 italic">
          {{ localApproach }}
        </p>
        <p v-else class="text-[11px] text-muted-foreground italic">
          Нет описания…
        </p>

        <div v-if="localGoodQuestion" class="flex items-start gap-1 mt-1">
          <span class="text-[10px] leading-tight text-amber-600 dark:text-amber-400 line-clamp-1">
            ❓ {{ localGoodQuestion }}
          </span>
        </div>
      </div>

      <!-- Footer -->
      <div
        class="flex items-center justify-between border-t px-3 py-1.5 rounded-b-xl"
        :style="{ background: `${typeColor}0a` }"
      >
        <div class="flex items-center gap-1.5">
          <span v-if="localWatchOut" class="text-[10px] text-orange-400">⚠ Осторожно</span>
        </div>
        <div v-if="localIsEntryPoint" class="flex items-center gap-0.5">
          <span class="w-1.5 h-1.5 rounded-full" :style="{ backgroundColor: typeColor }" />
          <span class="text-[10px] text-muted-foreground">Вход</span>
        </div>
      </div>
    </template>

    <!-- Source handle for non-condition nodes -->
    <Handle
      v-if="!isCondition"
      type="source"
      :position="Position.Right"
      id="source"
      class="!w-3 !h-3 !border-2 !border-background"
      :style="{ backgroundColor: typeColor }"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, nextTick, inject } from 'vue'
import type { Ref } from 'vue'
import { Handle, Position, useVueFlow } from '@vue-flow/core'
import { X, ChevronDown, AlertTriangle, HelpCircle } from 'lucide-vue-next'
import type { ScriptNodeData, NodeType, ConversationStage } from '~/types/scriptFlow'
import { NODE_TYPE_COLORS, CONVERSATION_STAGES } from '~/types/scriptFlow'

const NODE_EMOJIS: Record<string, string> = {
  trigger:   '⚡',
  expertise: '🧠',
  question:  '❓',
  condition: '🔀',
  goto:      '➡️',
  business_rule: '📋',
  end:       '🔴',
}

const NODE_LABELS: Record<string, string> = {
  trigger:   'Триггер',
  expertise: 'Экспертиза',
  question:  'Вопрос',
  condition: 'Условие',
  goto:      'Переход',
  business_rule: 'Бизнес-правило',
  end:       'Конец',
}

const OUTCOME_OPTIONS = [
  { value: 'success', label: '✅ Успех — клиент записался / согласился' },
  { value: 'pending', label: '⏳ Отложено — думает, перезвонит' },
  { value: 'lost',    label: '❌ Отказ — не готов' },
] as const

const props = defineProps<{
  id: string
  data: ScriptNodeData & { content?: string }
  selected?: boolean
}>()

const { updateNodeData } = useVueFlow()

// ── Injected from ScriptFlowEditor ────────────────────────────────────────────
const expandedNodeId = inject<Ref<string | null>>('expandedNodeId', ref(null))
const setExpandedNodeId = inject<(id: string | null) => void>('setExpandedNodeId', () => {})
const flowVarNames = inject<Ref<string[]>>('flowVarNames', ref([]))
const flowServiceOptions = inject<Ref<Array<{ id: string; name: string; is_enabled?: boolean }>>>(
  'flowServiceOptions',
  ref([]),
)
const flowEmployeeOptions = inject<Ref<Array<{ id: string; name: string; active?: boolean }>>>(
  'flowEmployeeOptions',
  ref([]),
)
const flowNodeRefOptions = inject<Ref<Array<{ id: string; title: string; node_type: string }>>>(
  'flowNodeRefOptions',
  ref([]),
)

const isExpanded = computed(() => expandedNodeId.value === props.id)

// ── Local reactive state (mirrors node data) ──────────────────────────────────
const localTitle = ref('')
const localNodeType = ref<NodeType>('expertise')
const localStage = ref<ConversationStage | null>(null)
const localLevel = ref(1)
const localIsEntryPoint = ref(true)
const localSituation = ref('')
const localWhyItWorks = ref('')
const localApproach = ref('')
const localExamplePhrasesStr = ref('')
const localWatchOut = ref('')
const localGoodQuestion = ref('')
const localOutcomeType = ref<'success' | 'pending' | 'lost' | null>(null)
const localFinalAction = ref('')
const localConditions = ref<string[]>([])
const localServiceIds = ref<string[]>([])
const localEmployeeIds = ref<string[]>([])
const localDataSource = ref<'sqns_resources' | 'sqns_services' | 'custom_table'>('sqns_resources')
const localEntityType = ref<'employee' | 'service' | 'custom'>('employee')
const localEntityId = ref<string>('')
const localRuleCondition = ref('')
const localRuleAction = ref('')
const localRulePriority = ref(100)
const localRuleActive = ref(true)
const localRequiresEntity = ref<'none' | 'service' | 'employee' | 'both'>('none')
const localMustFollowNodeRefs = ref<string[]>([])
const lastFocusedField = ref<string>('situation')

// Guard against feedback loop: when flushNode writes to Vue Flow store,
// the props.data watcher would fire and reset local state.
let _skipSync = false

const syncFromData = () => {
  const d = props.data
  localTitle.value = String(d.title ?? d.label ?? '')
  localNodeType.value = (d.node_type as NodeType) ?? 'expertise'
  localStage.value = (d.stage as ConversationStage) ?? null
  localLevel.value = typeof d.level === 'number' ? d.level : 1
  localIsEntryPoint.value = d.is_entry_point !== false
  localSituation.value = String(d.situation ?? '')
  localWhyItWorks.value = String(d.why_it_works ?? '')
  localApproach.value = String(d.approach ?? '')
  localExamplePhrasesStr.value = Array.isArray(d.example_phrases)
    ? (d.example_phrases as string[]).join('\n')
    : String(d.example_phrases ?? '')
  localWatchOut.value = String(d.watch_out ?? '')
  localGoodQuestion.value = String(d.good_question ?? '')
  localConditions.value = Array.isArray(d.conditions) ? [...(d.conditions as string[])] : []
  localServiceIds.value = Array.isArray(d.service_ids) ? [...(d.service_ids as string[])] : []
  localEmployeeIds.value = Array.isArray(d.employee_ids) ? [...(d.employee_ids as string[])] : []
  localDataSource.value = (d.data_source as 'sqns_resources' | 'sqns_services' | 'custom_table') ?? 'sqns_resources'
  localEntityType.value = (d.entity_type as 'employee' | 'service' | 'custom') ?? 'employee'
  localEntityId.value = typeof d.entity_id === 'string' ? d.entity_id : ''
  localRuleCondition.value = String(d.rule_condition ?? '')
  localRuleAction.value = String(d.rule_action ?? '')
  localRulePriority.value = typeof d.rule_priority === 'number' ? d.rule_priority : 100
  localRuleActive.value = d.rule_active !== false
  const constraints = (d.constraints && typeof d.constraints === 'object')
    ? d.constraints as { requires_entity?: string; must_follow_node_refs?: string[] }
    : {}
  const req = String(constraints.requires_entity || 'none').toLowerCase()
  localRequiresEntity.value = ['none', 'service', 'employee', 'both'].includes(req)
    ? req as 'none' | 'service' | 'employee' | 'both'
    : 'none'
  localMustFollowNodeRefs.value = Array.isArray(constraints.must_follow_node_refs)
    ? constraints.must_follow_node_refs.filter((x) => typeof x === 'string' && x.trim())
    : []
  localOutcomeType.value = (d.outcome_type as 'success' | 'pending' | 'lost' | null) ?? null
  localFinalAction.value = String(d.final_action ?? '')
}

// Sync from external changes (e.g. initial load, undo)
watch(
  () => props.data,
  () => {
    if (_skipSync) return
    syncFromData()
  },
  { deep: true, immediate: true },
)

// Re-sync when node is expanded (in case data changed while collapsed)
watch(isExpanded, (expanded) => {
  if (expanded) syncFromData()
})

// ── Computed display helpers ───────────────────────────────────────────────────
const isCondition = computed(() => localNodeType.value === 'condition')
const isTrigger = computed(() => localNodeType.value === 'trigger')
const isExpertise = computed(() => localNodeType.value === 'expertise')
const isQuestion = computed(() => localNodeType.value === 'question')
const isGoto = computed(() => localNodeType.value === 'goto')
const isBusinessRule = computed(() => localNodeType.value === 'business_rule')
const isEnd = computed(() => localNodeType.value === 'end')
const isConversationNode = computed(() => isTrigger.value || isExpertise.value || isQuestion.value || isGoto.value)
/** Вкладки «Контекст / Содержание» — сотрудник·услуга·ситуация vs мотив·аргументы·вопросы */
const showAxisTabs = computed(() => isExpertise.value || isQuestion.value)

const axisTab = ref<'context' | 'content'>('context')
watch(() => props.id, () => {
  axisTab.value = 'context'
})

const nodeFormHint = computed((): string | null => {
  if (!showAxisTabs.value)
    return null
  return isExpertise.value
    ? 'Контекст: этап, услуги, сотрудники, возражение. Содержание: мотив, аргументы, фразы, табу.'
    : 'Контекст: где в воронке задаём вопрос. Формулировки: сам вопрос и варианты.'
})

const typeColor = computed(() => NODE_TYPE_COLORS[localNodeType.value] || '#6b7280')
const typeEmoji = computed(() => NODE_EMOJIS[localNodeType.value] || '🧠')
const typeLabel = computed(() => NODE_LABELS[localNodeType.value] || 'Узел')

const stageBadge = computed(() => {
  const s = localStage.value
  if (!s) return null
  return CONVERSATION_STAGES.find(st => st.value === s)?.label ?? s
})

// ── Flush all fields to Vue Flow store ────────────────────────────────────────
const flushNode = () => {
  _skipSync = true
  updateNodeData(props.id, {
    title: localTitle.value,
    label: localTitle.value,
    node_type: localNodeType.value,
    stage: localStage.value,
    level: localLevel.value,
    is_entry_point: localIsEntryPoint.value,
    situation: localSituation.value,
    why_it_works: localWhyItWorks.value || null,
    approach: localApproach.value || null,
    example_phrases: localExamplePhrasesStr.value
      .split('\n')
      .map((s) => s.trim())
      .filter(Boolean),
    watch_out: localWatchOut.value || null,
    good_question: localGoodQuestion.value || null,
    conditions: localConditions.value.filter(Boolean),
    service_ids: [...localServiceIds.value],
    employee_ids: [...localEmployeeIds.value],
    data_source: localDataSource.value,
    entity_type: localEntityType.value,
    entity_id: localEntityId.value || null,
    rule_condition: localRuleCondition.value || null,
    rule_action: localRuleAction.value || null,
    rule_priority: localRulePriority.value,
    rule_active: localRuleActive.value,
    constraints: {
      requires_entity: localRequiresEntity.value,
      must_follow_node_refs: [...localMustFollowNodeRefs.value],
    },
    outcome_type: localNodeType.value === 'end' ? (localOutcomeType.value ?? null) : null,
    final_action: localNodeType.value === 'end' ? (localFinalAction.value || null) : null,
  })
  nextTick(() => { _skipSync = false })
}

// ── Variable insertion (appends to last focused text field) ───────────────────
const insertVar = (varName: string) => {
  const snippet = `{{${varName}}}`
  switch (lastFocusedField.value) {
    case 'why_it_works':    localWhyItWorks.value       += snippet; break
    case 'approach':        localApproach.value         += snippet; break
    case 'example_phrases': localExamplePhrasesStr.value += snippet; break
    case 'watch_out':       localWatchOut.value         += snippet; break
    case 'good_question':   localGoodQuestion.value     += snippet; break
    case 'final_action':    localFinalAction.value      += snippet; break
    default:                localSituation.value        += snippet
  }
  flushNode()
}

// ── Condition helpers ─────────────────────────────────────────────────────────
const flushConditions = () => {
  _skipSync = true
  updateNodeData(props.id, { conditions: [...localConditions.value] })
  nextTick(() => { _skipSync = false })
}

const updateCondition = (index: number, value: string) => {
  localConditions.value[index] = value
  flushConditions()
}

const addCondition = () => {
  localConditions.value.push('')
  flushConditions()
}

const removeCondition = (index: number) => {
  localConditions.value.splice(index, 1)
  flushConditions()
}

const toggleService = (id: string) => {
  if (localServiceIds.value.includes(id))
    localServiceIds.value = localServiceIds.value.filter((x) => x !== id)
  else
    localServiceIds.value = [...localServiceIds.value, id]
  flushNode()
}

const toggleEmployee = (id: string) => {
  if (localEmployeeIds.value.includes(id))
    localEmployeeIds.value = localEmployeeIds.value.filter((x) => x !== id)
  else
    localEmployeeIds.value = [...localEmployeeIds.value, id]
  flushNode()
}

const toggleMustFollowNodeRef = (id: string) => {
  if (localMustFollowNodeRefs.value.includes(id))
    localMustFollowNodeRefs.value = localMustFollowNodeRefs.value.filter((x) => x !== id)
  else
    localMustFollowNodeRefs.value = [...localMustFollowNodeRefs.value, id]
  flushNode()
}

watch(localEntityType, (value) => {
  if (value === 'employee') {
    localDataSource.value = 'sqns_resources'
    localEntityId.value = ''
  } else if (value === 'service') {
    localDataSource.value = 'sqns_services'
    localEntityId.value = ''
  } else {
    localDataSource.value = 'custom_table'
    localEntityId.value = ''
  }
  flushNode()
})
</script>

<style scoped>
.node-label {
  @apply block text-[10px] font-semibold uppercase tracking-wider text-muted-foreground;
}

.node-input {
  @apply w-full rounded-lg border border-border bg-background px-2.5 py-1.5 text-[11px]
         transition-colors focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/20;
}

/* Scrollbar for expanded form */
div::-webkit-scrollbar { width: 3px; }
div::-webkit-scrollbar-track { background: transparent; }
div::-webkit-scrollbar-thumb { border-radius: 9999px; background: hsl(var(--muted-foreground) / 0.2); }
div::-webkit-scrollbar-thumb:hover { background: hsl(var(--muted-foreground) / 0.4); }
</style>
