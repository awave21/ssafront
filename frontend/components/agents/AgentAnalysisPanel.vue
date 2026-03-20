<template>
  <div
    ref="panelContainer"
    class="flex h-full min-h-0 flex-col gap-6 overflow-y-auto overflow-x-hidden overscroll-y-contain pr-1"
  >
    <div class="flex flex-col gap-4 rounded-xl border border-border bg-card p-4 shadow-sm">
      <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div class="space-y-1">
          <div class="flex items-center gap-2">
            <h2 class="text-2xl font-bold tracking-tight text-foreground">Анализ агента</h2>
            <Badge variant="outline" class="font-normal text-muted-foreground">Центр обучения</Badge>
          </div>
          <p class="text-sm text-muted-foreground">
            Мониторинг качества, проблемных тем и рекомендаций по улучшению.
          </p>
        </div>
        <div class="flex items-center gap-2">
          <Button variant="outline" size="sm" :disabled="isRefreshingJob" @click="handleRefreshJob">
            <RefreshCcw class="mr-2 h-3.5 w-3.5" :class="isRefreshingJob ? 'animate-spin' : ''" />
            Обновить
          </Button>

          <Dialog>
            <DialogTrigger as-child>
              <Button size="sm" :disabled="!canStartNewJob">
                <Play class="mr-2 h-3.5 w-3.5" />
                Запустить анализ
              </Button>
            </DialogTrigger>
            <DialogContent class="sm:max-w-[425px]">
              <DialogHeader>
                <DialogTitle>Запуск анализа</DialogTitle>
                <DialogDescription>
                  Выберите период и настройте параметры для оффлайн-анализа диалогов.
                </DialogDescription>
              </DialogHeader>
              <div class="grid gap-4 py-4">
                <div class="space-y-2">
                  <label class="text-sm font-medium">Период анализа</label>
                  <div class="flex flex-wrap gap-2">
                    <Button
                      v-for="preset in periodPresets"
                      :key="preset.value"
                      :variant="runForm.window_hours === preset.value ? 'default' : 'secondary'"
                      size="sm"
                      class="flex-1"
                      @click="runForm.window_hours = preset.value"
                    >
                      {{ preset.label }}
                    </Button>
                  </div>
                </div>

                <div class="flex items-center justify-between rounded-md border border-border bg-muted/30 px-3 py-2">
                  <span class="text-sm">Только с вмешательством менеджера</span>
                  <Switch v-model="runForm.only_with_manager" />
                </div>

                <div class="space-y-3">
                  <Button variant="link" size="sm" class="h-auto p-0" @click="isAdvancedOpen = !isAdvancedOpen">
                    {{ isAdvancedOpen ? 'Скрыть расширенные настройки' : 'Показать расширенные настройки' }}
                  </Button>

                  <div v-if="isAdvancedOpen" class="grid gap-3 border-t border-border pt-3">
                    <div class="grid grid-cols-2 gap-2">
                      <div class="space-y-1">
                        <label class="text-[10px] uppercase text-muted-foreground">Макс. диалогов</label>
                        <Input v-model="runForm.max_dialogs" type="number" min="1" placeholder="100" />
                      </div>
                      <div class="space-y-1">
                        <label class="text-[10px] uppercase text-muted-foreground">Глубина истории</label>
                        <Input v-model="runForm.history_limit" type="number" min="1" placeholder="10" />
                      </div>
                    </div>
                    <div class="grid grid-cols-2 gap-2">
                      <div class="space-y-1">
                        <label class="text-[10px] uppercase text-muted-foreground">Лимит токенов</label>
                        <Input v-model="runForm.max_tokens_per_job" type="number" min="1" placeholder="50000" />
                      </div>
                      <div class="space-y-1">
                        <label class="text-[10px] uppercase text-muted-foreground">Лимит LLM-запросов</label>
                        <Input v-model="runForm.max_llm_requests_per_job" type="number" min="1" placeholder="500" />
                      </div>
                    </div>
                    <div class="space-y-1">
                      <label class="text-[10px] uppercase text-muted-foreground">Мета-модель</label>
                      <Input v-model="runForm.meta_model" type="text" placeholder="gpt-4o" />
                    </div>
                  </div>
                </div>
              </div>
              <DialogFooter>
                <Button type="submit" class="w-full" :disabled="isStarting" @click="handleStartAnalysis">
                  <Loader2 v-if="isStarting" class="mr-2 h-4 w-4 animate-spin" />
                  <Play v-else class="mr-2 h-4 w-4" />
                  Начать анализ
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          <Button v-if="canCancelCurrentJob" variant="destructive" size="sm" :disabled="isCancelling" @click="cancelCurrentJob">
            <Loader2 v-if="isCancelling" class="mr-2 h-3.5 w-3.5 animate-spin" />
            <StopCircle v-else class="mr-2 h-3.5 w-3.5" />
            Отменить
          </Button>
        </div>
      </div>

      <div class="flex flex-wrap items-center gap-3 border-t border-border pt-4">
        <div class="flex items-center gap-2 text-xs">
          <span class="text-muted-foreground">Метрики качества:</span>
          <div class="flex flex-wrap gap-2">
            <Badge variant="secondary" class="bg-red-50 text-red-700 border-red-100">
              Вмешательства: {{ formatPercent(report?.kpis?.intervention_rate) }}
            </Badge>
            <Badge variant="secondary" class="bg-emerald-50 text-emerald-700 border-emerald-100">
              Ошибки инструментов: {{ formatPercent(report?.kpis?.tool_error_rate) }}
            </Badge>
            <Badge variant="secondary" class="bg-blue-50 text-blue-700 border-blue-100">
              Ошибки аргументов: {{ formatPercent(report?.kpis?.tool_argument_mismatch_rate) }}
            </Badge>
          </div>
        </div>
        <div v-if="!canStartNewJob" class="ml-auto flex items-center gap-2 text-xs text-amber-600">
          <Loader2 class="h-3 w-3 animate-spin" />
          <span>Активный анализ уже выполняется</span>
        </div>
      </div>
    </div>

    <div v-if="currentJob" class="rounded-xl border border-border bg-card p-4 shadow-sm">
      <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div class="flex items-center gap-3">
          <div class="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">
            <Activity v-if="currentJob.status === 'running'" class="h-5 w-5 animate-pulse" />
            <Clock v-else-if="currentJob.status === 'queued'" class="h-5 w-5" />
            <CheckCircle2 v-else-if="currentJob.status === 'succeeded'" class="h-5 w-5" />
            <XCircle v-else class="h-5 w-5" />
          </div>
          <div class="space-y-0.5">
            <div class="flex items-center gap-2">
              <h3 class="font-semibold text-foreground">Текущая задача</h3>
              <Badge :variant="getStatusBadgeVariant(currentJob.status)" :class="getStatusClasses(currentJob.status)" class="text-[10px] uppercase tracking-wider">
                {{ formatStatus(currentJob.status) }}
              </Badge>
            </div>
            <p class="text-xs text-muted-foreground">
              {{ currentJob.stage || 'Подготовка к анализу...' }} · {{ currentJob.window_hours }}ч период
            </p>
          </div>
        </div>

        <div class="flex flex-1 flex-col gap-1.5 sm:max-w-[300px]">
          <div class="flex items-center justify-between text-[10px] font-medium uppercase text-muted-foreground">
            <span>Прогресс выполнения</span>
            <span>{{ normalizedProgress }}%</span>
          </div>
          <div class="h-1.5 w-full overflow-hidden rounded-full bg-secondary">
            <div
              class="h-full bg-primary transition-all duration-500 ease-in-out"
              :style="{ width: `${normalizedProgress}%` }"
            />
          </div>
        </div>

        <div class="flex items-center gap-4">
          <div class="hidden flex-col items-end text-right xl:flex">
            <p class="text-[10px] uppercase text-muted-foreground">Запущено</p>
            <p class="text-xs font-medium">{{ formatDateTime(currentJob.started_at) }}</p>
          </div>
          <Button v-if="canCancelCurrentJob" variant="ghost" size="icon-sm" class="text-muted-foreground hover:text-destructive" :disabled="isCancelling" @click="cancelCurrentJob">
            <StopCircle class="h-4 w-4" />
          </Button>
        </div>
      </div>

      <Alert v-if="terminalWithError" variant="destructive" class="mt-4 py-2">
        <AlertCircle class="h-4 w-4" />
        <AlertDescription class="text-xs">{{ terminalWithError }}</AlertDescription>
      </Alert>
    </div>

    <div class="flex flex-col gap-6">
      <Tabs v-model:value="activeTab" class-name="space-y-6">
        <TabsList class="flex rounded-xl border border-border bg-card p-1 shadow-sm">
          <TabsTrigger value="overview" class="flex-1">Обзор</TabsTrigger>
          <TabsTrigger value="topics" class="flex-1">Темы и проблемы</TabsTrigger>
          <TabsTrigger value="recommendations" class="flex-1">Канбан рекомендаций</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" class="space-y-6">
          <div class="grid gap-6 xl:grid-cols-[1fr_350px]">
            <div class="space-y-6">
              <Card class="overflow-hidden border-none shadow-md">
                <CardHeader class="border-b border-border/50 bg-muted/30 pb-4 pt-5">
                  <div class="flex items-center justify-between">
                    <div class="space-y-1">
                      <CardTitle class="text-lg font-bold">Сводка анализа</CardTitle>
                      <CardDescription class="text-xs">
                        Данные на {{ formatDateTime(report?.meta?.analysis_as_of) }}
                      </CardDescription>
                    </div>
                    <Badge variant="outline" class="font-mono text-[10px] uppercase tracking-tighter text-muted-foreground">
                      v{{ report?.meta?.analyzer_version || '1.0' }}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent class="space-y-6 pt-6">
                  <div class="relative">
                    <Quote class="absolute -left-2 -top-2 h-8 w-8 text-primary/10" />
                    <p class="relative z-10 text-sm leading-relaxed text-foreground/90 italic">
                      {{ report?.summary || 'Отчёт пока не сформирован.' }}
                    </p>
                  </div>
                  
                  <div class="grid grid-cols-2 gap-4 sm:grid-cols-3">
                    <div class="space-y-1 rounded-lg border border-border bg-muted/20 p-3 transition-colors hover:bg-muted/40">
                      <p class="text-[10px] font-medium uppercase text-muted-foreground">Тем найдено</p>
                      <p class="text-2xl font-bold text-foreground">{{ formatNumber(report?.kpis?.topic_count) }}</p>
                    </div>
                    <div class="space-y-1 rounded-lg border border-border bg-muted/20 p-3 transition-colors hover:bg-muted/40">
                      <p class="text-[10px] font-medium uppercase text-muted-foreground">Рекомендаций</p>
                      <p class="text-2xl font-bold text-foreground">{{ formatNumber(report?.kpis?.recommendation_count) }}</p>
                    </div>
                    <div class="col-span-2 space-y-1 rounded-lg border border-primary/10 bg-primary/5 p-3 sm:col-span-1">
                      <p class="text-[10px] font-medium uppercase text-primary/70">Модель</p>
                      <p class="truncate text-sm font-semibold text-primary">{{ report?.meta?.model_name || 'GPT-4o' }}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>

            <div class="space-y-6">
              <Card class="border-none shadow-sm">
                <CardHeader class="pb-3">
                  <div class="flex items-center gap-2">
                    <Zap class="h-4 w-4 text-amber-500" />
                    <CardTitle class="text-sm font-bold uppercase tracking-wider">Что делать сейчас</CardTitle>
                  </div>
                </CardHeader>
                <CardContent class="space-y-0 p-0">
                  <div
                    v-for="(item, index) in topPriorities"
                    :key="item.id"
                    class="group relative flex cursor-pointer items-start gap-3 border-t border-border/50 px-4 py-3 transition-colors hover:bg-muted/30 first:border-t-0"
                    @click="focusRecommendationFromOverview(item.id)"
                  >
                    <div class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-muted text-[10px] font-bold text-muted-foreground group-hover:bg-primary group-hover:text-primary-foreground">
                      {{ index + 1 }}
                    </div>
                    <div class="min-w-0 flex-1 space-y-1">
                      <p class="line-clamp-2 break-words text-xs font-semibold text-foreground group-hover:text-primary" :title="item.title">{{ item.title }}</p>
                      <p class="line-clamp-2 break-words text-[10px] text-muted-foreground" :title="item.meta">{{ item.meta }}</p>
                    </div>
                    <Badge :variant="item.badgeVariant" class="h-5 rounded-sm px-1 text-[9px] uppercase tracking-tighter">{{ item.badge }}</Badge>
                  </div>
                  <div v-if="!topPriorities.length" class="p-8 text-center">
                    <p class="text-xs text-muted-foreground">Рекомендаций пока нет</p>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="topics">
          <div class="grid gap-6 xl:grid-cols-[1fr_400px]">
            <Card class="border-none shadow-sm">
              <CardHeader class="pb-3 pt-5">
                <div class="flex items-center justify-between">
                  <div class="space-y-1">
                    <CardTitle class="text-lg font-bold">Темы и проблемы</CardTitle>
                    <CardDescription class="text-xs text-muted-foreground">Распределение диалогов по категориям</CardDescription>
                  </div>
                  <div class="flex items-center gap-2">
                    <div class="flex items-center gap-1.5 rounded-md bg-muted px-2 py-1 text-[10px] font-medium uppercase text-muted-foreground">
                      <div class="h-2 w-2 rounded-full bg-emerald-500"></div>
                      Здоровье
                    </div>
                  </div>
                </div>
              </CardHeader>
              <CardContent class="p-0">
                <Table>
                  <TableHeader class="bg-muted/30">
                    <TableRow>
                      <TableHead class="h-10 text-[10px] uppercase tracking-wider">Название темы</TableHead>
                      <TableHead class="h-10 text-[10px] uppercase tracking-wider">Доля</TableHead>
                      <TableHead class="h-10 text-[10px] uppercase tracking-wider">Диалоги</TableHead>
                      <TableHead class="h-10 text-[10px] uppercase tracking-wider">Здоровье</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    <TableRow v-for="topic in report?.topics || []" :key="topic.name" 
                      class="group cursor-pointer transition-colors hover:bg-muted/50" 
                      :class="selectedTopicName === topic.name ? 'bg-primary/5' : ''"
                      @click="selectedTopicName = topic.name"
                    >
                      <TableCell class="py-3 font-semibold text-foreground group-hover:text-primary transition-colors">
                        {{ topic.name }}
                      </TableCell>
                      <TableCell class="py-3 text-xs">{{ formatPercent(topic.share) }}</TableCell>
                      <TableCell class="py-3 text-xs font-mono">{{ formatNumber(topic.dialogs_count) }}</TableCell>
                      <TableCell class="py-3">
                        <div class="flex items-center gap-2">
                          <div class="h-1.5 w-12 overflow-hidden rounded-full bg-secondary">
                            <div class="h-full bg-emerald-500" :style="{ width: `${topic.health || 0}%` }"></div>
                          </div>
                          <span class="text-[10px] font-bold">{{ topic.health || 0 }}%</span>
                        </div>
                      </TableCell>
                    </TableRow>
                  </TableBody>
                </Table>
              </CardContent>
            </Card>

            <div class="space-y-6">
              <Card class="border-none bg-gradient-to-br from-primary/5 to-background shadow-md">
                <CardHeader class="pb-3 pt-5">
                  <div class="flex items-center gap-2">
                    <Target class="h-4 w-4 text-primary" />
                    <CardTitle class="text-sm font-bold uppercase tracking-wider">Детализация темы</CardTitle>
                  </div>
                </CardHeader>
                <CardContent class="space-y-4">
                  <div v-if="selectedTopic" class="space-y-4">
                    <div class="space-y-1">
                      <h4 class="text-xl font-bold text-foreground">{{ selectedTopic.name }}</h4>
                      <p class="text-xs text-muted-foreground leading-relaxed">
                        {{ report?.summary || 'Детализация появится после генерации отчёта.' }}
                      </p>
                    </div>
                    
                    <div class="grid grid-cols-2 gap-2">
                      <div class="rounded-lg border border-border bg-background p-2 text-center">
                        <p class="text-[9px] uppercase text-muted-foreground">Доля</p>
                        <p class="text-sm font-bold">{{ formatPercent(selectedTopic.share) }}</p>
                      </div>
                      <div class="rounded-lg border border-border bg-background p-2 text-center">
                        <p class="text-[9px] uppercase text-muted-foreground">Диалоги</p>
                        <p class="text-sm font-bold">{{ formatNumber(selectedTopic.dialogs_count) }}</p>
                      </div>
                    </div>
                  </div>
                  <div v-else class="flex flex-col items-center justify-center py-12 text-center">
                    <MousePointerClick class="mb-2 h-8 w-8 text-muted-foreground/30" />
                    <p class="text-xs text-muted-foreground">Выберите тему из таблицы слева для просмотра деталей</p>
                  </div>
                </CardContent>
              </Card>

              <Card class="border-none shadow-sm">
                <CardHeader class="pb-3 pt-5">
                  <div class="flex items-center gap-2">
                    <AlertTriangle class="h-4 w-4 text-red-500" />
                    <CardTitle class="text-sm font-bold uppercase tracking-wider">Проблемные зоны</CardTitle>
                  </div>
                </CardHeader>
                <CardContent class="p-0">
                  <div v-for="topic in report?.top_failure_topics || []" :key="topic" 
                    class="flex items-center gap-3 border-t border-border/50 px-4 py-3 first:border-t-0"
                  >
                    <div class="h-2 w-2 rounded-full bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.5)]"></div>
                    <span class="text-xs font-medium text-foreground">{{ topic }}</span>
                  </div>
                  <div v-if="!(report?.top_failure_topics || []).length" class="p-8 text-center">
                    <p class="text-xs text-muted-foreground">Проблемные темы не найдены</p>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="recommendations" class="space-y-6">
          <div class="flex flex-col gap-4">
            <div class="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div class="flex items-center gap-4">
                <div class="flex flex-col">
                  <h3 class="text-lg font-bold">Канбан рекомендаций</h3>
                  <p class="text-[10px] text-muted-foreground uppercase tracking-widest">Управление улучшениями</p>
                </div>
                <div class="flex items-center gap-1 rounded-full bg-muted px-2 py-1 text-[10px] font-bold">
                  <span class="text-muted-foreground">Всего:</span>
                  <span>{{ recommendationsTotal }}</span>
                </div>
              </div>

              <div class="flex flex-wrap items-center gap-2">
                <div class="flex items-center gap-1 rounded-lg border border-border bg-card p-1">
                  <Select :model-value="selectedCategoryValue" @update:model-value="handleCategoryChange">
                    <SelectTrigger class="h-8 w-[160px] border-none bg-transparent text-xs shadow-none focus:ring-0">
                      <SelectValue placeholder="Категория" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__all__">Все категории</SelectItem>
                      <SelectItem v-for="category in categories" :key="category" :value="category">{{ category }}</SelectItem>
                    </SelectContent>
                  </Select>
                  <div class="h-4 w-px bg-border"></div>
                  <Select :model-value="selectedLimitValue" @update:model-value="handleLimitSelectChange">
                    <SelectTrigger class="h-8 w-[80px] border-none bg-transparent text-xs shadow-none focus:ring-0">
                      <SelectValue placeholder="Лимит" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="10">10</SelectItem>
                      <SelectItem value="20">20</SelectItem>
                      <SelectItem value="50">50</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>

            <div v-if="isLoadingRecommendations" class="grid h-[calc(100vh-380px)] min-h-[550px] gap-4 xl:grid-cols-3">
              <div v-for="i in 3" :key="i" class="flex flex-col gap-4 rounded-xl border border-border/40 bg-muted/10 p-4">
                <div class="flex items-center justify-between">
                  <Skeleton class="h-4 w-24" />
                  <Skeleton class="h-5 w-8 rounded-full" />
                </div>
                <div class="space-y-4 pt-2">
                  <div v-for="j in 3" :key="j" class="space-y-3 rounded-lg border border-border/50 bg-card p-4 shadow-sm">
                    <div class="space-y-2">
                      <Skeleton class="h-4 w-3/4" />
                      <div class="flex gap-2">
                        <Skeleton class="h-3 w-12" />
                        <Skeleton class="h-3 w-12" />
                      </div>
                    </div>
                    <Skeleton class="h-12 w-full" />
                    <div class="flex justify-between">
                      <Skeleton class="h-6 w-16" />
                      <Skeleton class="h-6 w-16" />
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div v-else class="space-y-4">
              <div class="hidden h-[calc(100vh-380px)] min-h-[550px] gap-4 pb-4 xl:grid xl:grid-cols-3">
                <div
                  v-for="column in recommendationColumns"
                  :key="column.status"
                  class="relative flex min-w-0 flex-col rounded-xl border border-border/40 bg-muted/20 transition-all duration-300"
                  :class="dragOverStatus === column.status ? 'ring-2 ring-primary ring-offset-2 bg-primary/5' : ''"
                  @dragover="handleColumnDragOver($event, column.status)"
                  @dragleave="dragOverStatus = null"
                  @drop.prevent="handleColumnDrop(column.status)"
                >
                  <div class="sticky top-0 z-50 shrink-0 border-b border-border/50 bg-background px-4 py-3 shadow-sm">
                    <div class="flex items-center justify-between">
                      <div class="flex items-center gap-2">
                        <div class="h-2 w-2 rounded-full" :class="{
                          'bg-amber-500': column.status === 'pending',
                          'bg-emerald-500': column.status === 'accepted',
                          'bg-red-500': column.status === 'rejected'
                        }"></div>
                        <h3 class="text-xs font-bold uppercase tracking-wider text-foreground">{{ column.title }}</h3>
                      </div>
                      <Badge variant="secondary" class="h-5 rounded-full px-2 text-[10px] font-bold">
                        {{ recommendationsByStatus[column.status].length }}
                      </Badge>
                    </div>
                  </div>
                  
                  <ScrollArea class="flex-1">
                    <div class="space-y-3 p-3">
                      <Card
                        v-for="recommendation in recommendationsByStatus[column.status]"
                        :key="recommendation.id"
                        class="group relative cursor-grab overflow-hidden border-border/50 bg-card shadow-sm transition-all hover:-translate-y-1 hover:border-primary/40 hover:shadow-md active:cursor-grabbing"
                        :class="focusedRecommendationId === recommendation.id ? 'ring-2 ring-primary/60 ring-offset-1' : ''"
                        :data-recommendation-id="recommendation.id"
                        :draggable="!Boolean(reviewBusyById[recommendation.id])"
                        @dragstart="handleRecommendationDragStart($event, recommendation.id)"
                        @dragend="handleRecommendationDragEnd"
                      >
                        <div class="absolute left-0 top-0 h-full w-1 transition-colors group-hover:bg-primary" :class="{
                          'bg-amber-500/30': column.status === 'pending',
                          'bg-emerald-500/30': column.status === 'accepted',
                          'bg-red-500/30': column.status === 'rejected'
                        }"></div>
                        
                        <CardHeader class="p-3 pb-1">
                          <div class="space-y-1.5">
                            <div class="flex items-start justify-between gap-2">
                              <CardTitle class="text-[13px] font-bold leading-snug group-hover:text-primary transition-colors">
                                {{ recommendation.title }}
                              </CardTitle>
                            </div>
                            <div class="flex flex-wrap items-center gap-1.5">
                              <Badge variant="outline" class="h-4 rounded-sm px-1 text-[9px] font-medium bg-muted/50 border-none uppercase tracking-tighter">
                                {{ recommendation.category || 'Общее' }}
                              </Badge>
                              <div class="flex items-center gap-1 text-[9px] text-muted-foreground font-medium">
                                <Zap class="h-2.5 w-2.5" :class="Number(recommendation.priority) > 7 ? 'text-amber-500' : 'text-muted-foreground/50'" />
                                {{ recommendation.priority ?? '-' }}
                              </div>
                            </div>
                          </div>
                        </CardHeader>
                        
                        <CardContent class="space-y-3 p-3 pt-2">
                          <div class="space-y-2 text-[11px] leading-relaxed text-muted-foreground">
                            <p
                              v-if="recommendation.suggestion"
                              class="italic text-foreground/80"
                              :class="isSuggestionExpanded(recommendation.id) ? 'line-clamp-none' : 'line-clamp-3'"
                            >
                              "{{ recommendation.suggestion }}"
                            </p>
                            <Button
                              v-if="hasLongSuggestion(recommendation.suggestion)"
                              variant="ghost"
                              size="sm"
                              class="h-5 px-0 text-[10px] font-medium text-primary hover:text-primary/80"
                              @click="toggleSuggestionExpanded(recommendation.id)"
                            >
                              {{ isSuggestionExpanded(recommendation.id) ? 'Свернуть' : 'Показать еще' }}
                            </Button>
                          </div>

                          <div class="flex flex-wrap gap-1">
                            <div v-for="dialogId in (recommendation.evidence_dialog_ids || []).slice(0, 3)" :key="dialogId" 
                              class="rounded bg-muted px-1 py-0.5 text-[8px] font-mono text-muted-foreground border border-border/50"
                            >
                              #{{ dialogId.split('-')[0] }}
                            </div>
                            <div v-if="(recommendation.evidence_dialog_ids || []).length > 3" class="text-[8px] text-muted-foreground self-center">
                              +{{ recommendation.evidence_dialog_ids.length - 3 }}
                            </div>
                          </div>

                          <div class="space-y-2 pt-1">
                            <div class="relative">
                              <Textarea
                                v-model="reviewDraftById[recommendation.id]"
                                rows="1"
                                class="min-h-[32px] w-full resize-none border-none bg-muted/50 p-1.5 text-[10px] transition-all focus-visible:bg-background focus-visible:ring-1 focus-visible:ring-primary/30"
                                placeholder="Заметка..."
                              />
                            </div>

                            <div class="flex items-center justify-between gap-2">
                              <div class="flex gap-1">
                                <Button
                                  v-if="column.status !== 'rejected'"
                                  variant="ghost"
                                  size="icon-sm"
                                  class="h-6 w-6 text-muted-foreground hover:bg-red-50 hover:text-red-500"
                                  :disabled="Boolean(reviewBusyById[recommendation.id])"
                                  @click="handleReview(recommendation.id, 'rejected')"
                                >
                                  <X class="h-3 w-3" />
                                </Button>
                                <Button
                                  v-if="column.status !== 'accepted'"
                                  variant="ghost"
                                  size="icon-sm"
                                  class="h-6 w-6 text-muted-foreground hover:bg-emerald-50 hover:text-emerald-500"
                                  :disabled="Boolean(reviewBusyById[recommendation.id])"
                                  @click="handleReview(recommendation.id, 'accepted')"
                                >
                                  <Check class="h-3 w-3" />
                                </Button>
                              </div>
                              <div class="text-[9px] font-bold text-primary/40 uppercase tracking-tighter">
                                {{ formatConfidence(recommendation.confidence) }}
                              </div>
                            </div>
                          </div>
                        </CardContent>
                      </Card>

                      <div v-if="!recommendationsByStatus[column.status].length" class="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-border/20 py-16 text-center">
                        <Bot class="mb-2 h-6 w-6 text-muted-foreground/20" />
                        <p class="max-w-[140px] text-[10px] font-medium text-muted-foreground/40 uppercase tracking-wider">
                          {{ column.emptyDescription }}
                        </p>
                      </div>
                    </div>
                  </ScrollArea>
                </div>
              </div>

              <div class="space-y-3 xl:hidden">
                <div class="flex items-center gap-1 rounded-lg bg-muted p-1 overflow-x-auto">
                  <Button
                    v-for="column in recommendationColumns"
                    :key="`mobile-${column.status}`"
                    size="sm"
                    :variant="selectedMobileStatus === column.status ? 'secondary' : 'ghost'"
                    class="h-8 flex-1 text-[10px] font-bold uppercase tracking-wider"
                    :class="selectedMobileStatus === column.status ? 'bg-background shadow-sm' : ''"
                    @click="selectedMobileStatus = column.status"
                  >
                    {{ column.title }}
                  </Button>
                </div>

                <div
                  class="flex min-h-[400px] flex-col rounded-xl border border-border/50 bg-muted/20"
                  :class="dragOverStatus === selectedMobileColumn.status ? 'ring-2 ring-primary' : ''"
                  @dragover="handleColumnDragOver($event, selectedMobileColumn.status)"
                  @dragleave="dragOverStatus = null"
                  @drop.prevent="handleColumnDrop(selectedMobileColumn.status)"
                >
                  <ScrollArea class="h-[calc(100vh-450px)]">
                    <div class="space-y-3 p-3">
                      <Card
                        v-for="recommendation in recommendationsByStatus[selectedMobileColumn.status]"
                        :key="recommendation.id"
                        class="border-border/50 bg-card shadow-sm"
                      >
                        <CardHeader class="p-3 pb-1">
                          <CardTitle class="text-xs font-bold">{{ recommendation.title }}</CardTitle>
                        </CardHeader>
                        <CardContent class="space-y-3 p-3 pt-2">
                          <p v-if="recommendation.suggestion" class="text-[11px] text-muted-foreground italic">
                            "{{ recommendation.suggestion }}"
                          </p>
                          <div class="flex items-center justify-end gap-2">
                            <Button
                              v-if="selectedMobileColumn.status !== 'rejected'"
                              variant="outline"
                              size="sm"
                              class="h-7 text-[10px]"
                              @click="handleReview(recommendation.id, 'rejected')"
                            >Отклонить</Button>
                            <Button
                              v-if="selectedMobileColumn.status !== 'accepted'"
                              size="sm"
                              class="h-7 text-[10px]"
                              @click="handleReview(recommendation.id, 'accepted')"
                            >Принять</Button>
                          </div>
                        </CardContent>
                      </Card>
                    </div>
                  </ScrollArea>
                </div>
              </div>
            </div>

            <div class="flex items-center justify-between border-t border-border/50 pt-4">
              <p class="text-[10px] font-medium uppercase tracking-widest text-muted-foreground/60">{{ paginationLabel }}</p>
              <div class="flex items-center gap-1">
                <Button variant="ghost" size="sm" class="h-8 w-8 p-0" :disabled="!canPrevPage || isLoadingRecommendations" @click="handlePrevPage">
                  <ChevronLeft class="h-4 w-4" />
                </Button>
                <Button variant="ghost" size="sm" class="h-8 w-8 p-0" :disabled="!canNextPage || isLoadingRecommendations" @click="handleNextPage">
                  <ChevronRight class="h-4 w-4" />
                </Button>
              </div>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>

    <Alert v-if="screenState === 'error'" variant="destructive">
      <AlertTitle>Не удалось загрузить раздел анализа</AlertTitle>
      <AlertDescription class="flex flex-col items-start gap-2">
        <span>{{ errorMessage || 'Попробуйте повторить позже.' }}</span>
        <Button variant="outline" size="sm" @click="initialize">Повторить</Button>
      </AlertDescription>
    </Alert>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  Bot,
  Check,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  Loader2,
  MousePointerClick,
  Play,
  Quote,
  RefreshCcw,
  StopCircle,
  Target,
  X,
  XCircle,
  Zap,
} from 'lucide-vue-next'
import Alert from '~/components/ui/alert/Alert.vue'
import AlertDescription from '~/components/ui/alert/AlertDescription.vue'
import AlertTitle from '~/components/ui/alert/AlertTitle.vue'
import Badge from '~/components/ui/badge/Badge.vue'
import Button from '~/components/ui/button/Button.vue'
import Card from '~/components/ui/card/Card.vue'
import CardContent from '~/components/ui/card/CardContent.vue'
import CardDescription from '~/components/ui/card/CardDescription.vue'
import CardHeader from '~/components/ui/card/CardHeader.vue'
import CardTitle from '~/components/ui/card/CardTitle.vue'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '~/components/ui/dialog'
import Input from '~/components/ui/input/Input.vue'
import Select from '~/components/ui/select/Select.vue'
import SelectContent from '~/components/ui/select/SelectContent.vue'
import SelectItem from '~/components/ui/select/SelectItem.vue'
import SelectTrigger from '~/components/ui/select/SelectTrigger.vue'
import SelectValue from '~/components/ui/select/SelectValue.vue'
import ScrollArea from '~/components/ui/scroll-area/ScrollArea.vue'
import Skeleton from '~/components/ui/skeleton/Skeleton.vue'
import Switch from '~/components/ui/switch/Switch.vue'
import Table from '~/components/ui/table/Table.vue'
import TableBody from '~/components/ui/table/TableBody.vue'
import TableCell from '~/components/ui/table/TableCell.vue'
import TableHead from '~/components/ui/table/TableHead.vue'
import TableHeader from '~/components/ui/table/TableHeader.vue'
import TableRow from '~/components/ui/table/TableRow.vue'
import Tabs from '~/components/ui/tabs/Tabs.vue'
import TabsContent from '~/components/ui/tabs/TabsContent.vue'
import TabsList from '~/components/ui/tabs/TabsList.vue'
import TabsTrigger from '~/components/ui/tabs/TabsTrigger.vue'
import Textarea from '~/components/ui/textarea/Textarea.vue'
import { useAgentAnalysis } from '~/composables/useAgentAnalysis'
import { useToast } from '~/composables/useToast'
import type { AnalysisReviewStatus, AnalysisWindowHours } from '~/types/agent-analysis'

const route = useRoute()
const agentId = computed(() => {
  const id = route.params.id
  return Array.isArray(id) ? id[0] || '' : typeof id === 'string' ? id : ''
})

const { info: toastInfo } = useToast()

const {
  screenState,
  isStarting,
  isCancelling,
  isLoadingRecommendations,
  errorMessage,
  currentJob,
  report,
  recommendations,
  recommendationsTotal,
  recommendationFilters,
  categories,
  canCancelCurrentJob,
  canStartNewJob,
  terminalWithError,
  initialize,
  startJob,
  cancelCurrentJob,
  fetchCurrentJob,
  fetchRecommendations,
  reviewRecommendation
} = useAgentAnalysis(() => agentId.value)

const periodPresets: Array<{ value: AnalysisWindowHours; label: string }> = [
  { value: 24, label: 'За сутки (24h)' },
  { value: 72, label: 'За 3 дня (72h)' },
  { value: 168, label: 'За неделю (168h)' },
]

// Mapping selected Banani screen to current blocks:
// overview-hero -> report summary, kpi-grid -> KPI cards, action-plan-list -> recommendations.
const runForm = reactive({
  window_hours: 72 as AnalysisWindowHours,
  only_with_manager: false,
  max_dialogs: '',
  history_limit: '',
  max_tokens_per_job: '',
  max_llm_requests_per_job: '',
  meta_model: ''
})

const isAdvancedOpen = ref(false)
const isRefreshingJob = ref(false)
const reviewBusyById = reactive<Record<string, boolean>>({})
const reviewDraftById = reactive<Record<string, string>>({})
const expandedSuggestionById = reactive<Record<string, boolean>>({})
const focusedRecommendationId = ref<string | null>(null)
const selectedTopicName = ref<string>('')
const activeTab = ref('overview')
const panelContainer = ref<HTMLElement | null>(null)
const draggedRecommendationId = ref<string | null>(null)
const dragOverStatus = ref<AnalysisReviewStatus | null>(null)
const isDraggingCard = ref(false)

const normalizedProgress = computed(() => {
  const value = currentJob.value?.progress_pct
  if (typeof value !== 'number') return 0
  if (value < 0) return 0
  if (value > 100) return 100
  return Math.round(value)
})

const canPrevPage = computed(() => (recommendationFilters.offset || 0) > 0)
const canNextPage = computed(() => {
  const offset = recommendationFilters.offset || 0
  const limit = recommendationFilters.limit || 20
  return offset + limit < recommendationsTotal.value
})

const paginationLabel = computed(() => {
  if (!recommendationsTotal.value) return '0 рекомендаций'
  const offset = recommendationFilters.offset || 0
  const limit = recommendationFilters.limit || 20
  const from = offset + 1
  const to = Math.min(offset + limit, recommendationsTotal.value)
  return `${from}-${to} из ${recommendationsTotal.value}`
})

const selectedCategoryValue = computed(() => recommendationFilters.category || '__all__')
const selectedLimitValue = computed(() => String(recommendationFilters.limit || 20))
const getRecommendationStatus = (status?: AnalysisReviewStatus | null): AnalysisReviewStatus =>
  status === 'accepted' || status === 'rejected' ? status : 'pending'

const recommendationColumns: Array<{ status: AnalysisReviewStatus; title: string; emptyDescription: string }> = [
  {
    status: 'pending',
    title: 'Ожидает решения',
    emptyDescription: 'Нет задач в ожидании.'
  },
  {
    status: 'accepted',
    title: 'Принято',
    emptyDescription: 'Ещё нет принятых рекомендаций.'
  },
  {
    status: 'rejected',
    title: 'Отклонено',
    emptyDescription: 'Ещё нет отклонённых рекомендаций.'
  }
]
const selectedMobileStatus = ref<AnalysisReviewStatus>('pending')
const selectedMobileColumn = computed(() =>
  recommendationColumns.find((column) => column.status === selectedMobileStatus.value) || recommendationColumns[0]
)

const recommendationsByStatus = computed(() => {
  const grouped: Record<AnalysisReviewStatus, typeof recommendations.value> = {
    pending: [],
    accepted: [],
    rejected: []
  }

  recommendations.value.forEach((recommendation) => {
    grouped[getRecommendationStatus(recommendation.status)].push(recommendation)
  })

  return grouped
})

const topics = computed(() => report.value?.topics || [])

const selectedTopic = computed(() => {
  if (!topics.value.length) return null
  if (!selectedTopicName.value) return topics.value[0]
  return topics.value.find((item) => item.name === selectedTopicName.value) || topics.value[0]
})

type PriorityBadgeVariant = 'success' | 'destructive' | 'default' | 'secondary' | 'outline'

const topPriorities = computed(() =>
  recommendationsByStatus.value.pending.slice(0, 4).map((recommendation, index) => ({
    id: recommendation.id,
    title: `${index + 1}. ${recommendation.title}`,
    meta: recommendation.impact || recommendation.reasoning || 'Нет дополнительного описания',
    badge: index === 0 ? 'Срочно' : index === 1 ? 'Сегодня' : index === 2 ? 'На неделе' : 'Гипотеза',
    badgeVariant: (index === 0 ? 'destructive' : index === 1 ? 'default' : index === 2 ? 'secondary' : 'outline') as PriorityBadgeVariant
  }))
)

const toOptionalNumber = (value: string) => {
  const trimmed = value.trim()
  if (!trimmed) return undefined
  const parsed = Number(trimmed)
  if (!Number.isFinite(parsed) || parsed <= 0) return undefined
  return Math.floor(parsed)
}

const formatDateTime = (value?: string | null) => {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleString('ru-RU')
}

const formatPercent = (value?: number | null) => {
  if (typeof value !== 'number' || Number.isNaN(value)) return '-'
  return `${(value * 100).toFixed(1)}%`
}

const formatNumber = (value?: number | null) => {
  if (typeof value !== 'number' || Number.isNaN(value)) return '-'
  return value.toLocaleString('ru-RU')
}

const formatConfidence = (value?: number | null) => {
  if (typeof value !== 'number' || Number.isNaN(value)) return '-'
  return `${(value * 100).toFixed(0)}%`
}

const formatStatus = (status?: string | null) => {
  if (!status) return 'unknown'
  const map: Record<string, string> = {
    queued: 'В очереди',
    running: 'Выполняется',
    succeeded: 'Завершено успешно',
    failed: 'Завершено с ошибкой',
    cancelled: 'Отменено',
    unknown: 'Неизвестно'
  }
  return map[status] || status
}

const formatReviewStatus = (status: AnalysisReviewStatus) => {
  if (status === 'accepted') return 'Принято'
  if (status === 'rejected') return 'Отклонено'
  return 'Ожидает решения'
}

const hasLongSuggestion = (value?: string | null) => Boolean(value && value.trim().length > 220)
const isSuggestionExpanded = (recommendationId: string) => Boolean(expandedSuggestionById[recommendationId])
const toggleSuggestionExpanded = (recommendationId: string) => {
  expandedSuggestionById[recommendationId] = !expandedSuggestionById[recommendationId]
}

const focusRecommendationFromOverview = async (recommendationId: string) => {
  activeTab.value = 'recommendations'
  selectedMobileStatus.value = 'pending'
  focusedRecommendationId.value = recommendationId

  await nextTick()

  if (typeof document !== 'undefined') {
    const cardElement = document.querySelector<HTMLElement>(`[data-recommendation-id="${recommendationId}"]`)
    cardElement?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  setTimeout(() => {
    if (focusedRecommendationId.value === recommendationId) {
      focusedRecommendationId.value = null
    }
  }, 1800)
}

const getStatusClasses = (status: string) => {
  if (status === 'succeeded') return 'bg-emerald-100 text-emerald-700'
  if (status === 'failed') return 'bg-red-100 text-red-700'
  if (status === 'cancelled') return 'bg-slate-100 text-slate-700'
  if (status === 'running') return 'bg-blue-100 text-blue-700'
  if (status === 'queued') return 'bg-amber-100 text-amber-700'
  return 'bg-slate-100 text-slate-700'
}

const getStatusBadgeVariant = (status: string) => {
  if (status === 'succeeded') return 'success'
  if (status === 'failed') return 'destructive'
  return 'secondary'
}

const getReviewStatusClasses = (status: AnalysisReviewStatus) => {
  if (status === 'accepted') return 'bg-emerald-100 text-emerald-700'
  if (status === 'rejected') return 'bg-red-100 text-red-700'
  return 'bg-slate-100 text-slate-700'
}

const getReviewBadgeVariant = (status: AnalysisReviewStatus) => {
  if (status === 'accepted') return 'success'
  if (status === 'rejected') return 'destructive'
  return 'secondary'
}

const handleStartAnalysis = async () => {
  await startJob({
    window_hours: runForm.window_hours,
    only_with_manager: runForm.only_with_manager,
    max_dialogs: toOptionalNumber(runForm.max_dialogs),
    history_limit: toOptionalNumber(runForm.history_limit),
    max_tokens_per_job: toOptionalNumber(runForm.max_tokens_per_job),
    max_llm_requests_per_job: toOptionalNumber(runForm.max_llm_requests_per_job),
    meta_model: runForm.meta_model.trim() || undefined
  })
}

const handleRefreshJob = async () => {
  if (!currentJob.value) return
  isRefreshingJob.value = true
  try {
    await fetchCurrentJob()
  } finally {
    isRefreshingJob.value = false
  }
}

const handleReview = async (recommendationId: string, decision: Exclude<AnalysisReviewStatus, 'pending'>) => {
  reviewBusyById[recommendationId] = true
  try {
    await reviewRecommendation(recommendationId, decision, reviewDraftById[recommendationId] || '')
  } finally {
    reviewBusyById[recommendationId] = false
  }
}

const handleCategoryChange = async (value: string | number) => {
  const category = String(value)
  await fetchRecommendations({ category: category === '__all__' ? '' : category, offset: 0 })
}

const handleLimitSelectChange = async (value: string | number) => {
  const parsed = Number(value)
  const limit = Number.isFinite(parsed) && parsed > 0 ? parsed : 20
  await fetchRecommendations({ limit, offset: 0 })
}

const handleLimitChange = async () => {
  await fetchRecommendations({ offset: 0, limit: recommendationFilters.limit || 20 })
}

const handlePrevPage = async () => {
  const limit = recommendationFilters.limit || 20
  const nextOffset = Math.max(0, (recommendationFilters.offset || 0) - limit)
  await fetchRecommendations({ offset: nextOffset })
}

const handleNextPage = async () => {
  const limit = recommendationFilters.limit || 20
  const nextOffset = (recommendationFilters.offset || 0) + limit
  await fetchRecommendations({ offset: nextOffset })
}

const findScrollableParent = (element: HTMLElement | null) => {
  let current = element?.parentElement ?? null
  while (current) {
    const styles = window.getComputedStyle(current)
    const isScrollableY = /(auto|scroll|overlay)/.test(styles.overflowY)
    if (isScrollableY && current.scrollHeight > current.clientHeight) return current
    current = current.parentElement
  }
  return null
}

watch(
  () => activeTab.value,
  async () => {
    if (typeof window === 'undefined') return
    const pageScroller = document.scrollingElement as HTMLElement | null
    const parentScroller = findScrollableParent(panelContainer.value)
    const pageScrollTop = pageScroller?.scrollTop ?? 0
    const parentScrollTop = parentScroller?.scrollTop ?? 0
    const panelScrollTop = panelContainer.value?.scrollTop ?? 0

    await nextTick()

    if (pageScroller) pageScroller.scrollTop = pageScrollTop
    if (parentScroller) parentScroller.scrollTop = parentScrollTop
    if (panelContainer.value) panelContainer.value.scrollTop = panelScrollTop
  },
  { flush: 'post' }
)

const getRecommendationById = (recommendationId: string) =>
  recommendations.value.find((recommendation) => recommendation.id === recommendationId) || null

const isDropAllowed = (sourceStatus: AnalysisReviewStatus, targetStatus: AnalysisReviewStatus) =>
  sourceStatus !== targetStatus && targetStatus !== 'pending'

const handleRecommendationDragStart = (event: DragEvent, recommendationId: string) => {
  isDraggingCard.value = true
  draggedRecommendationId.value = recommendationId
  if (typeof document !== 'undefined') {
    document.body.classList.add('select-none')
  }
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', recommendationId)
  }
}

const handleRecommendationDragEnd = () => {
  isDraggingCard.value = false
  draggedRecommendationId.value = null
  dragOverStatus.value = null
  if (typeof document !== 'undefined') {
    document.body.classList.remove('select-none')
  }
}

const handleColumnDragOver = (event: DragEvent, targetStatus: AnalysisReviewStatus) => {
  if (!draggedRecommendationId.value) return
  const recommendation = getRecommendationById(draggedRecommendationId.value)
  const sourceStatus = getRecommendationStatus(recommendation?.status)
  if (!isDropAllowed(sourceStatus, targetStatus)) return

  event.preventDefault()
  dragOverStatus.value = targetStatus
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
}

const handleColumnDrop = async (targetStatus: AnalysisReviewStatus) => {
  isDraggingCard.value = false
  const recommendationId = draggedRecommendationId.value
  draggedRecommendationId.value = null
  dragOverStatus.value = null
  if (!recommendationId) return

  const recommendation = getRecommendationById(recommendationId)
  const sourceStatus = getRecommendationStatus(recommendation?.status)
  if (!isDropAllowed(sourceStatus, targetStatus)) {
    if (targetStatus === 'pending' && sourceStatus !== 'pending') {
      toastInfo('Возврат в pending недоступен', 'API поддерживает только решения: принять или отклонить')
    }
    return
  }

  if (targetStatus === 'accepted' || targetStatus === 'rejected') {
    await handleReview(recommendationId, targetStatus)
  }
}

const preventBrowserDropNavigation = (event: DragEvent) => {
  if (!isDraggingCard.value) return
  event.preventDefault()
}

watch(
  () => route.params.id,
  async () => {
    await initialize()
  }
)

onMounted(async () => {
  window.addEventListener('dragover', preventBrowserDropNavigation)
  window.addEventListener('drop', preventBrowserDropNavigation)
  await initialize()
})

onBeforeUnmount(() => {
  window.removeEventListener('dragover', preventBrowserDropNavigation)
  window.removeEventListener('drop', preventBrowserDropNavigation)
  if (typeof document !== 'undefined') {
    document.body.classList.remove('select-none')
  }
})
</script>
