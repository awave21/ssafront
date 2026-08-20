<template>
  <div v-if="open" class="rounded-2xl border border-slate-100 bg-slate-100 p-5">
    <div class="mb-4 flex items-start justify-between gap-3">
      <div class="min-w-0">
        <div class="text-sm font-semibold text-slate-900">
          {{ model?.id ? 'Редактирование действия' : 'Новое действие' }}
        </div>
        <div class="mt-0.5 text-xs text-slate-500">
          Выберите действие и настройте параметры — они сохранятся вместе с функцией.
        </div>
      </div>
      <button
        type="button"
        class="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-slate-400 transition-colors hover:bg-white hover:text-slate-700"
        title="Закрыть"
        @click="$emit('update:open', false)"
      >
        <X class="h-4 w-4" />
      </button>
    </div>

      <div class="flex flex-col gap-3">
        <div class="grid gap-2">
          <label class="text-sm font-medium text-slate-900">Действие</label>
          <OptionCardPicker
            :items="actionPickerItems"
            :model-value="actionPreset"
            @update:model-value="onSelectPreset"
          />
        </div>

        <div v-if="local.action_type === 'send_message'" class="grid gap-1.5">
          <label class="text-sm font-medium text-slate-900">Текст сообщения</label>
          <Textarea v-model="messageText" placeholder="Сообщение пользователю после выполнения функции" />
        </div>

        <div v-else-if="local.action_type === 'set_tag'" class="grid gap-2 md:grid-cols-2">
          <div class="grid gap-1.5">
            <label class="text-sm font-medium text-slate-900">Тег</label>
            <Input v-model="tagName" placeholder="interest_to_service" />
          </div>
          <div class="grid gap-1.5">
            <label class="text-sm font-medium text-slate-900">Уверенность (опц.)</label>
            <Input v-model.number="tagConfidence" type="number" min="0" max="1" step="0.01" />
          </div>
        </div>

        <div v-else-if="local.action_type === 'notify_admin'" class="grid gap-3 rounded-md border border-border bg-muted/20 p-2.5">
          <div class="grid gap-1.5">
            <label class="text-sm font-medium text-slate-900">Текст уведомления</label>
            <Textarea
              v-model="adminMessage"
              placeholder="Например: клиент запросил счёт — нужен менеджер"
            />
            <p v-pre class="text-xs text-muted-foreground">
              Можно подставлять значения из контекста: <code class="rounded bg-slate-100 px-1">{{result}}</code>,
              <code class="rounded bg-slate-100 px-1">{{last_user_message}}</code> и параметры функции.
            </p>
          </div>

          <div class="flex items-center justify-between rounded-md border border-border bg-background px-3 py-2">
            <div class="text-sm text-slate-700">Приложить последнее сообщение клиента</div>
            <Switch :model-value="adminIncludeContext" @update:model-value="adminIncludeContext = !!$event" />
          </div>

          <div class="grid gap-2 md:grid-cols-2">
            <div class="grid gap-1.5">
              <label class="text-sm font-medium text-slate-900">Chat ID (опц.)</label>
              <Input v-model="adminChatId" placeholder="из настроек агента" />
            </div>
            <div class="grid gap-1.5">
              <label class="text-sm font-medium text-slate-900">Токен бота (опц.)</label>
              <Input v-model="adminBotToken" placeholder="из настроек агента" />
            </div>
          </div>

          <p class="text-xs text-muted-foreground">
            Если оба поля пустые — берутся уведомления из настроек агента, и они должны быть включены.
            Заполненная пара «Chat ID + токен» отправит сообщение в свой чат даже при выключенном общем тумблере.
          </p>
        </div>

        <div v-else-if="local.action_type === 'handoff_to_operator'" class="grid gap-3 rounded-md border border-border bg-muted/20 p-2.5">
          <p class="text-xs text-muted-foreground">
            Ставит диалог на паузу, чтобы агент перестал отвечать, и передаёт разговор человеку.
            Снять паузу можно из карточки диалога или действием «Возобновить диалог».
          </p>

          <div class="grid gap-1.5">
            <label class="text-sm font-medium text-slate-900">Сообщение клиенту (опц.)</label>
            <Textarea
              v-model="handoffClientMessage"
              placeholder="Например: передаю вас администратору, он ответит в ближайшее время"
            />
          </div>

          <div class="grid gap-1.5">
            <label class="text-sm font-medium text-slate-900">Причина для администратора</label>
            <Input v-model="handoffReason" placeholder="Например: запрос на возврат средств" />
          </div>

          <div class="flex items-center justify-between rounded-md border border-border bg-background px-3 py-2">
            <div class="text-sm text-slate-700">Уведомить администратора в Telegram</div>
            <Switch :model-value="handoffNotifyAdmin" @update:model-value="handoffNotifyAdmin = !!$event" />
          </div>
        </div>

        <div v-else-if="isWebhookPreset" class="grid gap-3 rounded-md border border-border bg-muted/20 p-2.5">
          <div class="grid gap-1.5">
            <label class="text-sm font-medium text-slate-900">Выберите созданный webhook</label>
            <Select :model-value="selectedToolId" @update:model-value="onSelectTool">
              <SelectTrigger>
                <SelectValue placeholder="Выберите webhook из списка" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">Не выбрано</SelectItem>
                <SelectItem v-for="tool in availableWebhookTools" :key="tool.id" :value="tool.id || ''">
                  {{ tool.input_schema?._displayName || tool.name }}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div v-if="!selectedWebhookTool" class="rounded-md border border-dashed border-border bg-muted/40 p-3 text-xs text-muted-foreground">
            Выберите webhook, чтобы настроить сопоставление параметров.
          </div>

          <div v-else class="grid gap-2 md:grid-cols-2">
            <div class="grid gap-1.5">
              <label class="text-sm font-medium text-slate-900">URL</label>
              <Input v-model="webhookUrl" placeholder="https://example.com/hook" disabled />
            </div>
            <div class="grid gap-1.5">
              <label class="text-sm font-medium text-slate-900">Метод</label>
              <Select :model-value="webhookMethod" @update:model-value="webhookMethod = String($event)" disabled>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="GET">GET</SelectItem>
                  <SelectItem value="POST">POST</SelectItem>
                  <SelectItem value="PUT">PUT</SelectItem>
                  <SelectItem value="PATCH">PATCH</SelectItem>
                  <SelectItem value="DELETE">DELETE</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div v-if="actionPreset === 'webhook_api_call'" class="grid gap-1.5">
            <div v-if="selectedWebhookTool && toolSchemaParams.length" class="grid gap-2 rounded-md border border-border bg-background p-2.5">
              <div class="text-sm font-medium text-slate-900">Параметры webhook</div>
              <div
                v-for="param in toolSchemaParams"
                :key="param.name"
                class="grid gap-1.5"
              >
                <div class="grid gap-2 md:grid-cols-[1fr_1fr] rounded-md border border-border bg-muted/20 p-2 transition-colors hover:bg-muted/35">
                  <div class="grid gap-1">
                    <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">Webhook</div>
                    <div class="flex items-center gap-2">
                      <span class="text-sm font-medium text-slate-900">{{ param.name }}</span>
                      <span class="text-[10px] rounded bg-slate-100 px-1.5 py-0.5 text-slate-600">{{ getTypeLabel(param.type) }}</span>
                      <span class="text-[10px] rounded bg-indigo-50 px-1.5 py-0.5 text-indigo-700">{{ getMappingLabel(param.mappingTarget) }}</span>
                      <span v-if="param.required" class="text-[10px] text-red-500">обязательный</span>
                    </div>
                    <p v-if="param.description" class="text-xs text-slate-500">{{ param.description }}</p>
                  </div>
                  <div class="grid gap-1">
                    <div class="text-xs font-semibold uppercase tracking-wide text-slate-500">Переменная функции</div>
                    <Select
                      :model-value="getVariableSelectValue(param.name)"
                      @update:model-value="onVariableSelectChange(param, String($event))"
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Выберите переменную функции" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem
                          v-for="variable in functionVariableOptions"
                          :key="`var_${param.name}_${variable.name}`"
                          :value="`var:${variable.name}`"
                        >
                          {{ variable.name }}
                        </SelectItem>
                        <SelectItem value="__none__">Не сопоставлено</SelectItem>
                        <SelectItem value="__create__">Создать новую переменную...</SelectItem>
                      </SelectContent>
                    </Select>

                    <div v-if="isCreatingVariableForParam(param.name)" class="grid gap-1.5">
                      <Input
                        :model-value="newVariableDraft[param.name]?.name || ''"
                        placeholder="Имя переменной"
                        @update:model-value="onNewVariableDraftChange(param.name, 'name', String($event))"
                      />
                      <Select
                        :model-value="newVariableDraft[param.name]?.type || normalizeVariableType(param.type)"
                        @update:model-value="onNewVariableDraftChange(param.name, 'type', String($event))"
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="string">Текст</SelectItem>
                          <SelectItem value="number">Число</SelectItem>
                          <SelectItem value="boolean">Логический (Да/Нет)</SelectItem>
                        </SelectContent>
                      </Select>
                      <Input
                        :model-value="newVariableDraft[param.name]?.description || ''"
                        placeholder="Описание для модели (что сюда подставлять)"
                        @update:model-value="onNewVariableDraftChange(param.name, 'description', String($event))"
                      />
                      <Button variant="outline" size="sm" @click="createVariableAndBind(param)">Создать и связать</Button>
                    </div>

                    <div v-else-if="getVariableSelectValue(param.name) === '__none__'" class="rounded-md border border-amber-300/60 bg-amber-50/70 p-2 text-xs text-amber-800">
                      Переменная функции не выбрана.
                    </div>

                    <div v-else class="rounded-md border border-border bg-muted/40 p-2 text-xs text-muted-foreground">
                      Подставляется: {{ getPayloadFieldValue(param.name, '') }}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-else-if="actionPreset === 'webhook_delayed_message'" class="grid gap-2 md:grid-cols-2">
            <div class="grid gap-1.5 md:col-span-2">
              <label class="text-sm font-medium text-slate-900">Текст сообщения</label>
              <Textarea v-model="delayedMessageText" placeholder="Текст отложенного сообщения" />
            </div>
            <div class="grid gap-1.5">
              <label class="text-sm font-medium text-slate-900">Задержка (сек.)</label>
              <Input v-model.number="delayedSeconds" type="number" min="1" />
            </div>
          </div>

          <div v-else-if="actionPreset === 'webhook_admin_message'" class="grid gap-2 md:grid-cols-2">
            <div class="grid gap-1.5 md:col-span-2">
              <label class="text-sm font-medium text-slate-900">Сообщение админу</label>
              <Textarea v-model="adminMessageText" placeholder="Текст сообщения для администратора" />
            </div>
            <div class="grid gap-1.5">
              <label class="text-sm font-medium text-slate-900">Мессенджер</label>
              <Select :model-value="adminMessenger" @update:model-value="adminMessenger = String($event)">
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="telegram">Telegram</SelectItem>
                  <SelectItem value="whatsapp">WhatsApp</SelectItem>
                  <SelectItem value="max">MAX</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <p class="text-xs text-slate-500">
            Для этих сценариев используется действие webhook c конфигурацией выбранной интеграции.
          </p>
        </div>

        <div v-else-if="local.action_type === 'augment_prompt'" class="grid gap-1.5">
          <label class="text-sm font-medium text-slate-900">Текст дополнения</label>
          <Textarea v-model="promptText" placeholder="Что добавить в промпт..." />
        </div>

        <div v-else-if="local.action_type === 'set_result'" class="grid gap-1.5">
          <label class="text-sm font-medium text-slate-900">Готовый ответ</label>
          <Textarea v-model="resultValue" placeholder="Текст, который уйдёт клиенту вместо ответа модели" />
          <p class="text-xs text-muted-foreground">
            Обрывает цепочку: модель не вызывается, клиент получает этот текст как есть.
          </p>
        </div>

        <div
          v-else-if="local.action_type === 'table_find' || local.action_type === 'table_write'"
          class="grid gap-3 rounded-md border border-border bg-muted/20 p-2.5"
        >
          <div class="grid gap-1.5">
            <label class="text-sm font-medium text-slate-900">Таблица</label>
            <!-- Список обновляем при каждом открытии: таблицу могли создать
                 в соседней вкладке, и возвращаться сюда за кнопкой «обновить»
                 пользователь не должен. -->
            <Select
              :model-value="tableId"
              @update:model-value="onSelectTable(String($event))"
              @update:open="$event && reloadTables()"
            >
              <SelectTrigger>
                <SelectValue placeholder="Выберите таблицу" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem v-for="t in availableTables" :key="t.id" :value="t.id">
                  {{ t.name }} · {{ t.records_count }} строк
                </SelectItem>
                <SelectItem :value="CREATE_TABLE_OPTION" class="font-semibold text-primary">
                  + Создать таблицу
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div v-if="tableId && !tableColumns.length" class="text-xs text-muted-foreground">
            У таблицы нет колонок — добавьте их, чтобы настроить действие.
          </div>

          <!-- Поиск строки -->
          <template v-if="local.action_type === 'table_find' && tableColumns.length">
            <div class="grid gap-2 md:grid-cols-2">
              <div class="grid gap-1.5">
                <label class="text-sm font-medium text-slate-900">Искать по колонке</label>
                <Select :model-value="findColumn" @update:model-value="findColumn = String($event)">
                  <SelectTrigger>
                    <SelectValue placeholder="Колонка" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem v-for="c in tableColumns" :key="c.name" :value="c.name">
                      {{ c.label || c.name }}
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div class="grid gap-1.5">
                <label class="text-sm font-medium text-slate-900">Значение</label>
                <Input v-model="findValue" placeholder="Например {{client_phone}}" />
              </div>
            </div>
            <div class="grid gap-1.5">
              <label class="text-sm font-medium text-slate-900">Префикс переменных</label>
              <Input v-model="findPrefix" placeholder="row" />
              <p class="text-xs text-muted-foreground">
                Поля найденной строки лягут в переменные вида
                <code class="rounded bg-slate-100 px-1">{{ findPrefixPreview }}</code>.
                Плюс флаг
                <code class="rounded bg-slate-100 px-1">{{ findFoundPreview }}</code>,
                по которому можно ветвить дальнейшие действия.
              </p>
            </div>
          </template>

          <!-- Запись строки -->
          <template v-if="local.action_type === 'table_write' && tableColumns.length">
            <div class="grid gap-1.5">
              <label class="text-sm font-medium text-slate-900">Что делать</label>
              <Select :model-value="writeMode" @update:model-value="writeMode = String($event)">
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="insert">Добавить строку</SelectItem>
                  <SelectItem value="update">Обновить существующую</SelectItem>
                  <SelectItem value="upsert">Обновить, а если нет — добавить</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div v-if="writeMode !== 'insert'" class="grid gap-2 md:grid-cols-2">
              <div class="grid gap-1.5">
                <label class="text-sm font-medium text-slate-900">Искать строку по колонке</label>
                <Select :model-value="matchColumn" @update:model-value="matchColumn = String($event)">
                  <SelectTrigger>
                    <SelectValue placeholder="Колонка" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem v-for="c in tableColumns" :key="c.name" :value="c.name">
                      {{ c.label || c.name }}
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div class="grid gap-1.5">
                <label class="text-sm font-medium text-slate-900">Значение для поиска</label>
                <Input v-model="matchValue" placeholder="Например {{client_phone}}" />
              </div>
            </div>

            <div class="grid gap-2 rounded-md border border-border bg-background p-2.5">
              <div class="text-sm font-medium text-slate-900">Значения колонок</div>
              <div v-for="c in tableColumns" :key="c.name" class="grid gap-1 md:grid-cols-[180px_1fr] md:items-center">
                <label class="text-xs font-medium text-slate-600">
                  {{ c.label || c.name }}
                  <span v-if="c.is_required" class="text-red-500">*</span>
                  <span class="ml-1 text-[10px] text-slate-400">{{ c.attribute_type }}</span>
                </label>
                <Input
                  :model-value="writeValues[c.name] ?? ''"
                  :placeholder="emptyValueHint"
                  @focus="focusedColumn = c.name"
                  @update:model-value="setWriteValue(c.name, String($event))"
                />
              </div>

              <div v-if="placeholders.length" class="border-t border-slate-100 pt-2.5">
                <div class="mb-1.5 text-xs text-slate-500">
                  Поставьте курсор в нужную колонку и нажмите подстановку:
                </div>
                <div class="flex flex-wrap gap-1.5">
                  <button
                    v-for="item in placeholders"
                    :key="item.token"
                    type="button"
                    class="rounded-lg bg-slate-100 px-2 py-1 font-mono text-[11px] text-slate-600 transition-colors hover:bg-primary/10 hover:text-primary"
                    :title="item.hint"
                    @mousedown.prevent
                    @click="insertPlaceholder(item.token)"
                  >{{ item.token }}</button>
                </div>
              </div>
            </div>
          </template>
        </div>

        <div v-else-if="local.action_type === 'set_variable'" class="grid gap-3 rounded-md border border-border bg-muted/20 p-2.5">
          <div class="grid gap-2 md:grid-cols-2">
            <div class="grid gap-1.5">
              <label class="text-sm font-medium text-slate-900">Имя переменной</label>
              <Input v-model="variableName" placeholder="client_city" />
            </div>
            <div class="grid gap-1.5">
              <label class="text-sm font-medium text-slate-900">Что сделать</label>
              <Select :model-value="variableOperation" @update:model-value="variableOperation = String($event)">
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="set">Записать значение</SelectItem>
                  <SelectItem value="increment">Увеличить на</SelectItem>
                  <SelectItem value="clear">Очистить</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div v-if="variableOperation !== 'clear'" class="grid gap-1.5">
            <label class="text-sm font-medium text-slate-900">
              {{ variableOperation === 'increment' ? 'Шаг' : 'Значение' }}
            </label>
            <Input
              v-model="variableValue"
              :placeholder="variableOperation === 'increment' ? '1' : 'Москва или {{result}}'"
            />
          </div>

          <p class="text-xs text-muted-foreground">
            Переменная хранится в диалоге и доступна дальше по разговору — в текстах других
            действий и в вебхуках через подстановку по имени.
          </p>
        </div>

        <div v-else-if="local.action_type === 'send_delayed'" class="grid gap-3 rounded-md border border-border bg-muted/20 p-2.5">
          <div class="grid gap-1.5">
            <label class="text-sm font-medium text-slate-900">Текст сообщения</label>
            <Textarea v-model="delayedText" placeholder="Например: напоминаем о вашей записи завтра в 15:00" />
          </div>
          <div class="grid gap-2 md:grid-cols-2">
            <div class="grid gap-1.5">
              <label class="text-sm font-medium text-slate-900">Через</label>
              <Input
                :model-value="delayAmount"
                type="number"
                min="1"
                @update:model-value="delayAmount = Number($event); syncDelay()"
              />
            </div>
            <div class="grid gap-1.5">
              <label class="text-sm font-medium text-slate-900">Единица</label>
              <Select :model-value="delayUnit" @update:model-value="delayUnit = String($event); syncDelay()">
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="seconds">секунд</SelectItem>
                  <SelectItem value="minutes">минут</SelectItem>
                  <SelectItem value="hours">часов</SelectItem>
                  <SelectItem value="days">дней</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <p class="text-xs text-muted-foreground">
            Сообщение поставится в очередь и уйдёт отдельно, без участия модели. Максимум — 7 дней.
          </p>
        </div>

        <div
          v-else-if="noConfigHint"
          class="rounded-md border border-border bg-muted/40 p-3 text-xs text-muted-foreground"
        >
          {{ noConfigHint }}
        </div>

        <!-- Общие поля идут после параметров действия: сначала «что делаем»
             и чем это настраивается, потом «когда и в каком порядке». -->
        <div v-if="actionPreset" class="grid gap-3 border-t border-slate-200 pt-4">
          <div class="text-[9px] font-black uppercase tracking-wider text-slate-400">
            Условия выполнения
          </div>

          <div class="grid gap-2 md:grid-cols-2">
            <div class="grid gap-1.5">
              <label class="text-sm font-medium text-slate-900">Когда выполнять</label>
              <Select :model-value="local.on_status" @update:model-value="local.on_status = $event as any">
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="success">При успехе</SelectItem>
                  <SelectItem value="error">При ошибке</SelectItem>
                  <SelectItem value="always">Всегда</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div class="grid gap-1.5">
              <label class="text-sm font-medium text-slate-900">Порядок выполнения</label>
              <Input v-model.number="local.order_index" type="number" min="1" />
            </div>
          </div>

          <div class="flex items-center justify-between rounded-md border border-border bg-muted/30 px-3 py-2">
            <div class="text-sm text-slate-700">Включено</div>
            <Switch :model-value="local.enabled" @update:model-value="local.enabled = !!$event" />
          </div>
        </div>

        <div class="mt-2 flex justify-end gap-2 border-t border-slate-200 pt-4">
          <Button variant="outline" @click="$emit('update:open', false)">Отмена</Button>
          <Button :disabled="!actionPreset" @click="submitAction">Сохранить действие</Button>
        </div>
      </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { Button } from '~/components/ui/button'
import { Input } from '~/components/ui/input'
import { Textarea } from '~/components/ui/textarea'
import { Switch } from '~/components/ui/switch'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '~/components/ui/select'
import { X } from 'lucide-vue-next'
import OptionCardPicker, { type OptionCardItem } from '~/components/agents/function-rules/OptionCardPicker.vue'
import { useRoute } from 'vue-router'
import { useApiFetch } from '~/composables/useApiFetch'
import { soonActionItems } from '~/utils/ruleActionSoon'
import {
  functionRuleActionDescriptions,
  functionRuleActionLabels,
  type FunctionRuleAction,
} from '~/types/ruleAction'
import { functionRuleActionIcons } from '~/utils/ruleActionIcons'
import type { Tool } from '~/types/tool'

const props = defineProps<{
  open: boolean
  model: FunctionRuleAction | null
  tools?: Tool[]
  ruleVariables?: Array<{ name: string; type?: string; description?: string }>
}>()

const emit = defineEmits<{
  'update:open': [open: boolean]
  submit: [payload: FunctionRuleAction]
  'add-rule-variable': [payload: { name: string; type: string; description?: string }]
}>()

const local = reactive<FunctionRuleAction>({
  id: '',
  rule_id: '',
  action_type: 'noop',
  on_status: 'always',
  enabled: true,
  order_index: 1,
  config: {},
})
// Пусто = действие ещё не выбрано. Раньше по умолчанию стоял noop, и можно было
// случайно сохранить пустышку, ничего не нажав.
const actionPreset = ref<string>('')

/** Карточка для действия, у которого есть готовые подпись, описание и иконка. */
const fromType = (
  type: keyof typeof functionRuleActionLabels,
  extra: Partial<OptionCardItem> = {},
): OptionCardItem => ({
  value: type,
  label: functionRuleActionLabels[type],
  description: functionRuleActionDescriptions[type],
  icon: functionRuleActionIcons[type],
  ...extra,
})

// Пресет `webhook_api_call` — не тип действия, а вариант действия webhook: он
// раскладывается в action_type='webhook' + config.action_kind (см. onSelectPreset).
// Остальные карточки — обычные типы действий, все поддержаны раннером.
// Порядок: сначала то, что шлёт сообщения, потом контекст, потом управление диалогом.
const actionPickerItems = computed<OptionCardItem[]>(() => [
  {
    value: 'webhook_api_call',
    label: 'API вызов (Webhook)',
    description: functionRuleActionDescriptions.webhook,
    icon: functionRuleActionIcons.webhook,
  },
  fromType('send_message'),
  fromType('send_delayed'),
  fromType('notify_admin'),
  fromType('handoff_to_operator'),
  fromType('set_tag'),
  fromType('set_variable'),
  fromType('table_find'),
  fromType('table_write'),
  fromType('augment_prompt'),
  fromType('set_result'),
  fromType('pause_dialog'),
  fromType('resume_dialog'),
  fromType('block_user'),
  fromType('unblock_user'),
  fromType('noop'),
  ...soonActionItems,
])

/** Действия без параметров — показываем пояснение вместо пустого блока. */
const NO_CONFIG_HINTS: Record<string, string> = {
  pause_dialog: 'Агент перестанет отвечать в этом диалоге. Снять паузу можно из карточки диалога или действием «Возобновить диалог».',
  resume_dialog: 'Диалог вернётся в работу, агент снова начнёт отвечать.',
  block_user: 'Агент будет отключён для этого пользователя во всех его диалогах, пока блокировку не снимут.',
  unblock_user: 'Снимает блокировку — агент снова обслуживает пользователя.',
  noop: 'Действие ничего не делает. Используется как отметка в журнале выполнения правила.',
}

// Пока действие не выбрано, local.action_type ещё держит стартовый 'noop' —
// без этой проверки подсказка про «ничего не делает» показывалась бы сразу.
const noConfigHint = computed(() =>
  actionPreset.value ? NO_CONFIG_HINTS[local.action_type] || '' : '',
)

const availableWebhookTools = computed(() =>
  (props.tools || []).filter(
    (tool) =>
      tool.execution_type === 'http_webhook' &&
      Boolean(tool.endpoint) &&
      (tool.webhook_scope === 'function_only' || tool.webhook_scope === 'both') &&
      (tool.status === 'active' || tool.status === undefined),
  ),
)

const isWebhookPreset = computed(() => actionPreset.value.startsWith('webhook_'))
type ToolSchemaParam = {
  name: string
  type: string
  description: string
  mappingTarget: string
  required: boolean
  defaultValue: any
}
const selectedWebhookTool = computed(() =>
  availableWebhookTools.value.find((tool) => tool.id === local.config.tool_id),
)
const functionVariableOptions = computed(() =>
  (props.ruleVariables || [])
    .map((item) => ({
      name: String(item.name || '').trim(),
      type: String(item.type || 'string'),
      description: String(item.description || ''),
    }))
    .filter((item) => Boolean(item.name))
    .filter((item, index, all) => all.findIndex((x) => x.name === item.name) === index),
)
const newVariableDraft = reactive<Record<string, { name: string; type: string; description: string }>>({})
const toolSchemaParams = computed<ToolSchemaParam[]>(() => {
  const tool = selectedWebhookTool.value
  const schema = tool?.input_schema
  const properties = schema && typeof schema === 'object' ? schema.properties : null
  if (!properties || typeof properties !== 'object') return []
  const requiredList = Array.isArray(schema.required) ? schema.required.map((v: any) => String(v)) : []
  const seen = new Set<string>()
  return Object.entries(properties)
    .filter(([name, cfg]: [string, any]) => {
      if (!name || seen.has(name)) return false
      if (String(name).startsWith('_')) return false
      if (cfg?.['x-variable'] === true) return false
      seen.add(name)
      return true
    })
    .map(([name, cfg]: [string, any]) => ({
      name,
      type: String(cfg?.type || 'string'),
      description: String(cfg?.description || ''),
      mappingTarget: String(tool?.parameter_mapping?.[name] || 'body'),
      required: requiredList.includes(name),
      defaultValue: cfg?.default,
    }))
})

const messageText = computed({
  get: () => String(local.config.message || ''),
  set: (value: string) => {
    local.config = { ...local.config, message: value }
  },
})

const tagName = computed({
  get: () => String(local.config.tag || ''),
  set: (value: string) => {
    local.config = { ...local.config, tag: value }
  },
})

const tagConfidence = computed({
  get: () => Number(local.config.confidence || 0),
  set: (value: number) => {
    local.config = { ...local.config, confidence: value }
  },
})

const adminMessage = computed({
  get: () => String(local.config.message || ''),
  set: (value: string) => {
    local.config = { ...local.config, message: value }
  },
})

// include_context по умолчанию true — как и в раннере, чтобы галка в UI
// совпадала с фактическим поведением у действий, созданных до этого поля.
const adminIncludeContext = computed({
  get: () => local.config.include_context !== false,
  set: (value: boolean) => {
    local.config = { ...local.config, include_context: value }
  },
})

const adminChatId = computed({
  get: () => String(local.config.chat_id || ''),
  set: (value: string) => {
    local.config = { ...local.config, chat_id: value }
  },
})

const adminBotToken = computed({
  get: () => String(local.config.bot_token || ''),
  set: (value: string) => {
    local.config = { ...local.config, bot_token: value }
  },
})

const handoffClientMessage = computed({
  get: () => String(local.config.client_message || ''),
  set: (value: string) => {
    local.config = { ...local.config, client_message: value }
  },
})

const handoffReason = computed({
  get: () => String(local.config.reason || ''),
  set: (value: string) => {
    local.config = { ...local.config, reason: value }
  },
})

const handoffNotifyAdmin = computed({
  get: () => local.config.notify_admin !== false,
  set: (value: boolean) => {
    local.config = { ...local.config, notify_admin: value }
  },
})

const webhookUrl = computed({
  get: () => String(local.config.url || ''),
  set: (value: string) => {
    local.config = { ...local.config, url: value }
  },
})

const webhookMethod = computed({
  get: () => String(local.config.method || 'POST'),
  set: (value: string) => {
    local.config = { ...local.config, method: value }
  },
})

const selectedToolId = computed(() => String(local.config.tool_id || '__none__'))

const delayedMessageText = computed({
  get: () => String(local.config.delayed_message || ''),
  set: (value: string) => {
    local.config = { ...local.config, delayed_message: value }
  },
})

const delayedSeconds = computed({
  get: () => Number(local.config.delay_seconds || 60),
  set: (value: number) => {
    local.config = { ...local.config, delay_seconds: value }
  },
})

const adminMessageText = computed({
  get: () => String(local.config.admin_message || ''),
  set: (value: string) => {
    local.config = { ...local.config, admin_message: value }
  },
})

const adminMessenger = computed({
  get: () => String(local.config.admin_messenger || 'telegram'),
  set: (value: string) => {
    local.config = { ...local.config, admin_messenger: value }
  },
})

const promptText = computed({
  get: () => String(local.config.prompt || ''),
  set: (value: string) => {
    local.config = { ...local.config, prompt: value }
  },
})

const DELAY_UNITS: Record<string, number> = { seconds: 1, minutes: 60, hours: 3600, days: 86400 }
const delayAmount = ref(5)
const delayUnit = ref<string>('minutes')

/** Записывает delay_seconds из пары «число + единица». Раннер клампит 1 сек…7 дней. */
const syncDelay = () => {
  const factor = DELAY_UNITS[delayUnit.value] || 1
  const seconds = Math.round((Number(delayAmount.value) || 0) * factor)
  local.config = { ...local.config, delay_seconds: Math.min(Math.max(seconds, 1), 86400 * 7) }
}

/** Раскладывает сохранённые секунды обратно в удобную единицу. */
const restoreDelay = (raw: unknown) => {
  const total = Number(raw || 0)
  if (!total) {
    delayAmount.value = 5
    delayUnit.value = 'minutes'
    return
  }
  const unit = (['days', 'hours', 'minutes'] as const).find(
    (u) => total % DELAY_UNITS[u] === 0,
  )
  delayUnit.value = unit || 'seconds'
  delayAmount.value = total / (DELAY_UNITS[delayUnit.value] || 1)
}

type TableListItem = { id: string; name: string; records_count: number }
type TableColumn = {
  name: string
  label: string
  attribute_type: string
  is_required: boolean
}

const apiFetch = useApiFetch()
const route = useRoute()
const availableTables = ref<TableListItem[]>([])
const tableColumns = ref<TableColumn[]>([])
const tablesLoading = ref(false)

/** Раздел «База знаний → Таблицы» того же агента. */
const tablesPageUrl = computed(
  () => `/agents/${route.params.id}/knowledge?knowledgeTab=tables`,
)

const fetchTables = async () => {
  tablesLoading.value = true
  try {
    availableTables.value = await apiFetch<TableListItem[]>('/tables')
  } catch (err) {
    console.warn('Не удалось загрузить список таблиц', err)
    availableTables.value = []
  } finally {
    tablesLoading.value = false
  }
}

/** Список таблиц тянем один раз при открытии редактора — он общий на тенант. */
const loadTables = async () => {
  if (availableTables.value.length) return
  await fetchTables()
}

/** Принудительное обновление — после того как таблицу создали в соседней вкладке. */
const reloadTables = () => fetchTables()

// id и created_at платформа проставляет сама при вставке строки (см.
// user_table/runtime.insert_record). Предлагать их для заполнения нельзя:
// значение всё равно будет перезаписано, а обязательная звёздочка рядом
// заставляет думать, что поле нужно заполнить руками.
const SYSTEM_COLUMNS = new Set(['id', 'created_at'])

const loadTableColumns = async (id: string) => {
  if (!id) {
    tableColumns.value = []
    return
  }
  try {
    const columns = await apiFetch<TableColumn[]>(`/tables/${id}/attributes`)
    tableColumns.value = columns.filter((column) => !SYSTEM_COLUMNS.has(column.name))
  } catch (err) {
    console.warn('Не удалось загрузить колонки таблицы', err)
    tableColumns.value = []
  }
}

const tableId = computed(() => String(local.config.table_id || ''))

/** Псевдо-значение последнего пункта списка. */
const CREATE_TABLE_OPTION = '__create_table__'

const onSelectTable = (value: string) => {
  if (value === CREATE_TABLE_OPTION) {
    // Новая вкладка, а не переход: уход со страницы потерял бы недосохранённую функцию.
    window.open(tablesPageUrl.value, '_blank', 'noopener')
    return
  }

  // Колонки у другой таблицы свои, поэтому старое сопоставление сбрасываем —
  // иначе в values остались бы имена колонок, которых в новой таблице нет.
  local.config = {
    ...local.config,
    table_id: value,
    values: {},
    column: '',
    match_column: '',
  }
  loadTableColumns(value)
}

const cfgField = (key: string, fallback = '') =>
  computed({
    get: () => String(local.config[key] ?? fallback),
    set: (value: string) => {
      local.config = { ...local.config, [key]: value }
    },
  })

const findColumn = cfgField('column')
const findValue = cfgField('value')
const findPrefix = cfgField('store_prefix', 'row')
const writeMode = cfgField('mode', 'insert')
const matchColumn = cfgField('match_column')
const matchValue = cfgField('match_value')

const resolvedPrefix = computed(() => findPrefix.value.trim() || 'row')
const findPrefixPreview = computed(() => {
  const column = tableColumns.value[0]?.name || 'колонка'
  return `{{${resolvedPrefix.value}_${column}}}`
})
const findFoundPreview = computed(() => `{{${resolvedPrefix.value}_found}}`)

const writeValues = computed<Record<string, string>>(() =>
  (local.config.values && typeof local.config.values === 'object' ? local.config.values : {}),
)

// При добавлении пустое поле означает «колонку не заполняем», при обновлении —
// «не трогаем существующее значение». Разные вещи, поэтому и подсказка разная.
const emptyValueHint = computed(() =>
  writeMode.value === 'insert'
    ? 'Пусто — колонка останется незаполненной'
    : 'Пусто — колонка не изменится',
)

const focusedColumn = ref('')

/**
 * Что можно подставить в значение колонки: параметры самой функции плюс
 * стандартные ключи контекста. Раньше об этом сообщал только текст «работают
 * подстановки» — какие именно, приходилось угадывать.
 */
const placeholders = computed(() => [
  ...(props.ruleVariables || [])
    .map((v) => String(v.name || '').trim())
    .filter(Boolean)
    .map((name) => ({ token: `{{${name}}}`, hint: 'параметр функции' })),
  { token: '{{result}}', hint: 'результат выполнения функции' },
  { token: '{{last_user_message}}', hint: 'последнее сообщение клиента' },
])

/** Дописывает подстановку в колонку, на которой стоял курсор. */
const insertPlaceholder = (token: string) => {
  const column = focusedColumn.value || tableColumns.value[0]?.name
  if (!column) return
  setWriteValue(column, `${writeValues.value[column] || ''}${token}`)
}

const setWriteValue = (column: string, value: string) => {
  const next = { ...writeValues.value }
  // Пустое поле означает «не трогать колонку», поэтому ключ убираем совсем,
  // а не пишем пустую строку — иначе update затёр бы значение.
  if (value.trim()) next[column] = value
  else delete next[column]
  local.config = { ...local.config, values: next }
}

const variableName = computed({
  get: () => String(local.config.name || ''),
  set: (value: string) => {
    local.config = { ...local.config, name: value }
  },
})

const variableOperation = computed({
  get: () => String(local.config.operation || 'set'),
  set: (value: string) => {
    local.config = { ...local.config, operation: value }
  },
})

const variableValue = computed({
  get: () => String(local.config.value ?? ''),
  set: (value: string) => {
    local.config = { ...local.config, value }
  },
})

const delayedText = computed({
  get: () => String(local.config.message || ''),
  set: (value: string) => {
    local.config = { ...local.config, message: value }
  },
})

const resultValue = computed({
  get: () => String(local.config.value || ''),
  set: (value: string) => {
    local.config = { ...local.config, value: value }
  },
})

watch(
  () => props.model,
  (model) => {
    if (!model) {
      Object.assign(local, {
        id: '',
        rule_id: '',
        action_type: 'noop',
        on_status: 'always',
        enabled: true,
        order_index: 1,
        config: {},
      })
      actionPreset.value = ''
      return
    }
    Object.assign(local, {
      ...model,
      config: { ...(model.config || {}) },
    })
    if (model.action_type === 'webhook') {
      actionPreset.value = String(model.config?.action_kind || 'webhook_api_call')
    } else {
      actionPreset.value = model.action_type
    }
    if (model.action_type === 'send_delayed') restoreDelay(model.config?.delay_seconds)
    if (model.action_type === 'table_find' || model.action_type === 'table_write') {
      loadTableColumns(String(model.config?.table_id || ''))
    }
  },
  { immediate: true },
)

// Список таблиц нужен обеим табличным карточкам, поэтому тянем его при
// открытии редактора, а не по клику — иначе селект пустой первую секунду.
watch(
  () => props.open,
  (open) => {
    if (open) loadTables()
  },
  { immediate: true },
)

const onSelectPreset = (value: string) => {
  actionPreset.value = value
  if (value.startsWith('webhook_')) {
    local.action_type = 'webhook'
    local.config = { ...local.config, action_kind: value }
    return
  }
  local.action_type = value as FunctionRuleAction['action_type']
  local.config = {}
  if (value === 'send_delayed') syncDelay()
}

const onSelectTool = (value: string) => {
  const toolId = value === '__none__' ? null : value
  const selectedTool = availableWebhookTools.value.find((tool) => tool.id === toolId)
  const existingPayload = local.config.payload && typeof local.config.payload === 'object'
    ? { ...local.config.payload }
    : {}
  const schemaProps = selectedTool?.input_schema?.properties
  if (schemaProps && typeof schemaProps === 'object') {
    Object.entries(schemaProps).forEach(([key, cfg]: [string, any]) => {
      if (existingPayload[key] === undefined && cfg?.default !== undefined) {
        existingPayload[key] = cfg.default
      }
    })
  }
  local.config = {
    ...local.config,
    tool_id: toolId,
    url: selectedTool?.endpoint || local.config.url || '',
    method: selectedTool?.http_method || local.config.method || 'POST',
    payload: existingPayload,
  }
}

const getTypeLabel = (type: string) => {
  if (type === 'number' || type === 'integer') return 'число'
  if (type === 'boolean') return 'да/нет'
  if (type === 'array') return 'массив'
  if (type === 'object') return 'объект'
  return 'текст'
}

const getMappingLabel = (target: string) => {
  if (target === 'path') return 'path'
  if (target === 'query') return 'query'
  if (target === 'header') return 'header'
  return 'body'
}

const getPayloadFieldValue = (key: string, fallback: any) => {
  const payload = local.config.payload
  if (payload && typeof payload === 'object' && payload[key] !== undefined) return payload[key]
  return fallback
}

const setPayloadFieldValue = (key: string, value: any) => {
  const payload = local.config.payload && typeof local.config.payload === 'object'
    ? { ...local.config.payload }
    : {}
  payload[key] = value
  local.config = { ...local.config, payload }
}

const extractVariableToken = (value: any): string | null => {
  if (typeof value !== 'string') return null
  const match = value.trim().match(/^\{\{\s*([a-zA-Z_][\w]*)\s*\}\}$/)
  return match?.[1] || null
}

const getVariableSelectValue = (paramName: string) => {
  const currentValue = getPayloadFieldValue(paramName, undefined)
  const token = extractVariableToken(currentValue)
  if (token) return `var:${token}`
  if (newVariableDraft[paramName]?.name) return '__create__'
  return '__none__'
}

const isCreatingVariableForParam = (paramName: string) => getVariableSelectValue(paramName) === '__create__'

const normalizeVariableType = (type: string) => {
  if (type === 'number' || type === 'integer') return 'number'
  if (type === 'boolean') return 'boolean'
  return 'string'
}

const onNewVariableDraftChange = (
  paramName: string,
  field: 'name' | 'type' | 'description',
  value: string,
) => {
  const current = newVariableDraft[paramName] || {
    name: '',
    type: 'string',
    description: '',
  }
  newVariableDraft[paramName] = {
    ...current,
    [field]: value,
  }
}

const onVariableSelectChange = (param: ToolSchemaParam, value: string) => {
  if (value === '__none__') {
    delete newVariableDraft[param.name]
    const payload = local.config.payload && typeof local.config.payload === 'object'
      ? { ...local.config.payload }
      : {}
    delete payload[param.name]
    local.config = { ...local.config, payload }
    return
  }
  if (value === '__create__') {
    const defaultName = `${param.name}_value`
    newVariableDraft[param.name] = newVariableDraft[param.name] || {
      name: defaultName,
      type: normalizeVariableType(param.type),
      description: param.description || `Переменная для ${param.name}`,
    }
    return
  }
  if (value.startsWith('var:')) {
    const variableName = value.slice(4).trim()
    if (!variableName) return
    delete newVariableDraft[param.name]
    setPayloadFieldValue(param.name, `{{${variableName}}}`)
  }
}

const createVariableAndBind = (param: ToolSchemaParam) => {
  const draft = newVariableDraft[param.name]
  const variableName = String(draft?.name || '').trim()
  if (!variableName) return
  const variableType = String(draft?.type || normalizeVariableType(param.type))
  const variableDescription = String(draft?.description || '').trim()
  emit('add-rule-variable', {
    name: variableName,
    type: variableType === 'number' || variableType === 'boolean' ? variableType : 'string',
    description: variableDescription || param.description || `Переменная для ${param.name}`,
  })
  setPayloadFieldValue(param.name, `{{${variableName}}}`)
  delete newVariableDraft[param.name]
}

const submitAction = () => {
  const payloadConfig = { ...local.config }

  if (isWebhookPreset.value) {
    payloadConfig.action_kind = actionPreset.value
    const linkedTool = availableWebhookTools.value.find((tool) => tool.id === payloadConfig.tool_id)
    if (!payloadConfig.url && linkedTool?.endpoint) {
      payloadConfig.url = linkedTool.endpoint
    }
    if (!payloadConfig.method && linkedTool?.http_method) {
      payloadConfig.method = linkedTool.http_method
    }
    payloadConfig.method = String(payloadConfig.method || 'POST').toUpperCase()
    if (actionPreset.value === 'webhook_api_call') {
      // keep payload as is
    } else if (actionPreset.value === 'webhook_delayed_message') {
      payloadConfig.payload = {
        message: String(payloadConfig.delayed_message || ''),
        delay_seconds: Number(payloadConfig.delay_seconds || 60),
      }
    } else if (actionPreset.value === 'webhook_admin_message') {
      payloadConfig.payload = {
        message: String(payloadConfig.admin_message || ''),
        messenger: String(payloadConfig.admin_messenger || 'telegram'),
      }
    }
  }

  emit('submit', { ...local, config: payloadConfig })
  emit('update:open', false)
}
</script>
