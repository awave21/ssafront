import { computed, nextTick, ref, watch, type InjectionKey, type Ref } from 'vue'
import { nanoid } from 'nanoid'
import { useVueFlow } from '@vue-flow/core'
import { AGENT_SCRIPT_FLOW_VUE_FLOW_ID } from '~/constants/agentScriptFlow'
import type { FlowBranch, ScriptNodeData, NodeType, ConversationStage } from '~/types/scriptFlow'
import { CONVERSATION_STAGES } from '~/types/scriptFlow'
import {
  branchSourceHandleId,
  normalizeConditionsToBranches,
  parseBranchHandleId,
} from '~/utils/scriptFlowNodeRole'

/**
 * Состояние формы редактирования узла потока (инспектор справа).
 * Синхронизируется с Vue Flow через updateNodeData.
 */
export function useScriptFlowInspectorModel(nodeId: Ref<string | null>) {
  const { findNode, updateNodeData, edges, getNodes } = useVueFlow(AGENT_SCRIPT_FLOW_VUE_FLOW_ID)

  type StepConnectionSummary = {
    edgeId: string
    nodeId: string
    title: string
    nodeType: string
    relationLabel: string
    direction: 'incoming' | 'outgoing'
  }

  const localTitle = ref('')
  const localNodeType = ref<NodeType>('expertise')
  const localStage = ref<ConversationStage | null>(null)
  const localLevel = ref(1)
  const localIsEntryPoint = ref(true)
  /** Только trigger: точка входа в сценарий */
  const localIsFlowEntry = ref(true)
  const localSituation = ref('')
  const localWhyItWorks = ref('')
  const localApproach = ref('')
  const localExamplePhrasesStr = ref('')
  const localWatchOut = ref('')
  const localGoodQuestion = ref('')
  /** Wave 7 / trigger */
  const localWhenRelevant = ref('')
  const localClientPhraseExamplesStr = ref('')
  const localKeywordHintsStr = ref('')
  /** Wave 7 / question */
  const localWhyWeAsk = ref('')
  const localAlternativePhrasingsStr = ref('')
  const localExpectedAnswerType = ref('open')
  /** Wave 7 / condition */
  const localRoutingHint = ref('')
  /** Wave 7 / goto */
  const localTransitionPhrase = ref('')
  const localTriggerSituation = ref('')
  const localOutcomeType = ref<'success' | 'pending' | 'lost' | null>(null)
  const localFinalAction = ref('')
  const localBranches = ref<FlowBranch[]>([])
  // service_ids / employee_ids removed: use flow_metadata.variables + function bindings instead
  const localDataSource = ref<'sqns_resources' | 'sqns_services' | 'custom_table'>('sqns_resources')
  const localEntityType = ref<'employee' | 'service' | 'custom'>('employee')
  const localEntityId = ref<string>('')
  const localRuleCondition = ref('')
  const localRuleAction = ref('')
  const localRulePriority = ref(100)
  const localRuleActive = ref(true)
  const localRequiresEntity = ref<'none' | 'service' | 'employee' | 'both'>('none')
  const localMustFollowNodeRefs = ref<string[]>([])
  const localMotiveIds = ref<string[]>([])
  const localArgumentIds = ref<string[]>([])
  const localProofIds = ref<string[]>([])
  const localObjectionIds = ref<string[]>([])
  const localConstraintIds = ref<string[]>([])
  const localOutcomeId = ref<string | null>(null)
  const localTargetFlowId = ref<string | null>(null)
  const localTargetNodeRef = ref<string | null>(null)
  /** Только для node_type === business_rule: карточка каталога без рёбер сценария */
  const localIsCatalogRule = ref(true)
  const lastFocusedField = ref<string>('situation')
  const syncingFromGraph = ref(false)

  let _skipSync = false

  const syncFromNode = () => {
    const id = nodeId.value
    if (!id) return
    syncingFromGraph.value = true
    const n = findNode(id)
    const d = (n?.data || {}) as ScriptNodeData & { content?: string }
    localTitle.value = String(d.title ?? d.label ?? '')
    localNodeType.value = (d.node_type as NodeType) ?? 'expertise'
    localStage.value = (d.stage as ConversationStage) ?? null
    localLevel.value = typeof d.level === 'number' ? d.level : 1
    const searchableTypes: NodeType[] = ['trigger', 'expertise', 'question']
    if (searchableTypes.includes(localNodeType.value)) {
      localIsEntryPoint.value = typeof d.is_searchable === 'boolean'
        ? d.is_searchable
        : (d.is_entry_point !== false)
    }
    else {
      localIsEntryPoint.value = false
    }
    localIsFlowEntry.value = localNodeType.value === 'trigger'
      ? (typeof d.is_flow_entry === 'boolean'
          ? d.is_flow_entry
          : (d.is_entry_point !== false))
      : false
    localSituation.value = String(d.situation ?? '')
    localWhyItWorks.value = String(d.why_it_works ?? '')
    localApproach.value = String(d.approach ?? '')
    localExamplePhrasesStr.value = Array.isArray(d.example_phrases)
      ? (d.example_phrases as string[]).join('\n')
      : String(d.example_phrases ?? '')
    localWatchOut.value = String(d.watch_out ?? '')
    localGoodQuestion.value = String(d.good_question ?? '')
    localWhenRelevant.value = String(d.when_relevant ?? d.situation ?? '')
    localClientPhraseExamplesStr.value = Array.isArray(d.client_phrase_examples)
      ? (d.client_phrase_examples as string[]).join('\n')
      : Array.isArray(d.example_phrases)
        ? (d.example_phrases as string[]).join('\n')
        : ''
    localKeywordHintsStr.value = Array.isArray(d.keyword_hints)
      ? (d.keyword_hints as string[]).join('\n')
      : ''
    localWhyWeAsk.value = String(d.why_we_ask ?? d.situation ?? '')
    if (Array.isArray(d.alternative_phrasings) && (d.alternative_phrasings as string[]).length) {
      localAlternativePhrasingsStr.value = (d.alternative_phrasings as string[]).join('\n')
    }
    else if (Array.isArray(d.example_phrases)) {
      const gq = String(d.good_question ?? '').trim()
      localAlternativePhrasingsStr.value = (d.example_phrases as string[])
        .map(x => String(x).trim())
        .filter(x => x && x !== gq)
        .join('\n')
    }
    else {
      localAlternativePhrasingsStr.value = ''
    }
    localExpectedAnswerType.value = String(d.expected_answer_type ?? 'open')
    localRoutingHint.value = String(d.routing_hint ?? d.situation ?? '')
    localTransitionPhrase.value = String(d.transition_phrase ?? '')
    localTriggerSituation.value = String(d.trigger_situation ?? d.situation ?? '')
    localBranches.value = normalizeConditionsToBranches(d.conditions)
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
    const links = (d.kg_links && typeof d.kg_links === 'object')
      ? d.kg_links as Record<string, unknown>
      : {}
    const readIds = (v: unknown): string[] =>
      Array.isArray(v) ? (v as unknown[]).filter((x) => typeof x === 'string') as string[] : []
    localMotiveIds.value = readIds(links.motive_ids)
    localArgumentIds.value = readIds(links.argument_ids)
    localProofIds.value = readIds(links.proof_ids)
    localObjectionIds.value = readIds(links.objection_ids)
    localConstraintIds.value = readIds(links.constraint_ids)
    localOutcomeId.value = typeof links.outcome_id === 'string' ? (links.outcome_id as string) : null
    localTargetFlowId.value = typeof d.target_flow_id === 'string' && d.target_flow_id ? d.target_flow_id : null
    localTargetNodeRef.value = typeof d.target_node_ref === 'string' && d.target_node_ref ? d.target_node_ref : null
    if (localNodeType.value === 'business_rule')
      localIsCatalogRule.value = d.is_catalog_rule === true
    else
      localIsCatalogRule.value = true

    nextTick(() => {
      syncingFromGraph.value = false
    })
  }

  watch(
    nodeId,
    () => {
      if (!nodeId.value) return
      syncFromNode()
    },
    { immediate: true },
  )

  watch(
    () => {
      const id = nodeId.value
      if (!id) return null
      return findNode(id)?.data
    },
    () => {
      if (_skipSync || !nodeId.value) return
      syncFromNode()
    },
    { deep: true },
  )

  const flushNode = () => {
    const id = nodeId.value
    if (!id) return
    _skipSync = true
    const nt = localNodeType.value
    const title = localTitle.value
    const label = localTitle.value

    const kg_links = {
      motive_ids: [...localMotiveIds.value],
      argument_ids: [...localArgumentIds.value],
      proof_ids: [...localProofIds.value],
      objection_ids: [...localObjectionIds.value],
      constraint_ids: [...localConstraintIds.value],
      outcome_id: localOutcomeId.value,
    }

    const branchRows = localBranches.value
      .filter(b => b.label.trim())
      .map(b => ({ id: b.id, label: b.label.trim() }))

    if (nt === 'trigger') {
      updateNodeData(id, {
        node_type: 'trigger',
        title,
        label,
        client_phrase_examples: localClientPhraseExamplesStr.value
          .split('\n')
          .map(s => s.trim())
          .filter(Boolean),
        when_relevant: localWhenRelevant.value.trim() || null,
        keyword_hints: localKeywordHintsStr.value
          .split('\n')
          .map(s => s.trim())
          .filter(Boolean),
        is_flow_entry: localIsFlowEntry.value,
        is_searchable: localIsEntryPoint.value,
        is_entry_point: localIsEntryPoint.value,
      }, { replace: true })
    }
    else if (nt === 'question') {
      updateNodeData(id, {
        node_type: 'question',
        title,
        label,
        good_question: localGoodQuestion.value.trim(),
        alternative_phrasings: localAlternativePhrasingsStr.value
          .split('\n')
          .map(s => s.trim())
          .filter(Boolean),
        expected_answer_type: localExpectedAnswerType.value,
        why_we_ask: localWhyWeAsk.value.trim() || null,
        stage: localStage.value,
        level: localLevel.value,
        is_searchable: localIsEntryPoint.value,
        is_entry_point: localIsEntryPoint.value,
        kg_links,
        conditions: branchRows,
      }, { replace: true })
    }
    else if (nt === 'condition') {
      updateNodeData(id, {
        node_type: 'condition',
        title,
        label,
        routing_hint: localRoutingHint.value.trim() || null,
        conditions: branchRows,
      }, { replace: true })
    }
    else if (nt === 'goto') {
      updateNodeData(id, {
        node_type: 'goto',
        title,
        label,
        target_flow_id: localTargetFlowId.value || '',
        target_node_ref: localTargetNodeRef.value || null,
        transition_phrase: localTransitionPhrase.value.trim() || null,
        trigger_situation: localTriggerSituation.value.trim() || null,
      }, { replace: true })
    }
    else if (nt === 'expertise') {
      updateNodeData(id, {
        node_type: 'expertise',
        title,
        label,
        stage: localStage.value,
        level: localLevel.value,
        is_searchable: localIsEntryPoint.value,
        is_entry_point: localIsEntryPoint.value,
        is_flow_entry: false,
        situation: localSituation.value,
        why_it_works: localWhyItWorks.value || null,
        approach: localApproach.value || null,
        example_phrases: localExamplePhrasesStr.value
          .split('\n')
          .map((s) => s.trim())
          .filter(Boolean),
        watch_out: localWatchOut.value || null,
        good_question: localGoodQuestion.value || null,
        kg_links,
      }, { replace: true })
    }
    else if (nt === 'end') {
      updateNodeData(id, {
        node_type: 'end',
        title,
        label,
        outcome_type: localOutcomeType.value ?? null,
        final_action: localFinalAction.value || null,
        kg_links,
      }, { replace: true })
    }
    else if (nt === 'business_rule') {
      updateNodeData(id, {
        node_type: 'business_rule',
        title,
        label,
        stage: localStage.value,
        level: localLevel.value,
        is_searchable: false,
        situation: localSituation.value,
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
        is_catalog_rule: localIsCatalogRule.value,
      }, { replace: true })
    }
    nextTick(() => { _skipSync = false })
  }

  const toggleKgLink = (
    bucket: 'motive' | 'argument' | 'proof' | 'objection' | 'constraint',
    id: string,
  ) => {
    const map: Record<string, Ref<string[]>> = {
      motive: localMotiveIds,
      argument: localArgumentIds,
      proof: localProofIds,
      objection: localObjectionIds,
      constraint: localConstraintIds,
    }
    const target = map[bucket]
    if (!target) return
    if (target.value.includes(id))
      target.value = target.value.filter((x) => x !== id)
    else
      target.value = [...target.value, id]
    flushNode()
  }

  const setOutcomeEntity = (id: string | null) => {
    localOutcomeId.value = id
    flushNode()
  }

  const persistedBranches = (): FlowBranch[] =>
    localBranches.value.filter(b => b.label.trim()).map(b => ({ id: b.id, label: b.label.trim() }))

  const flushConditions = () => {
    const id = nodeId.value
    if (!id) return
    const n = findNode(id)
    if (!n) return
    _skipSync = true
    updateNodeData(id, {
      ...(n.data as Record<string, unknown>),
      conditions: persistedBranches(),
    } as ScriptNodeData, { replace: true })
    nextTick(() => { _skipSync = false })
  }

  const insertVar = (varName: string) => {
    const snippet = `{{${varName}}}`
    switch (lastFocusedField.value) {
      case 'why_it_works': localWhyItWorks.value += snippet; break
      case 'approach': localApproach.value += snippet; break
      case 'example_phrases': localExamplePhrasesStr.value += snippet; break
      case 'watch_out': localWatchOut.value += snippet; break
      case 'good_question': localGoodQuestion.value += snippet; break
      case 'final_action': localFinalAction.value += snippet; break
      case 'when_relevant': localWhenRelevant.value += snippet; break
      case 'client_phrase_examples': localClientPhraseExamplesStr.value += snippet; break
      case 'keyword_hints': localKeywordHintsStr.value += snippet; break
      case 'why_we_ask': localWhyWeAsk.value += snippet; break
      case 'alternative_phrasings': localAlternativePhrasingsStr.value += snippet; break
      case 'routing_hint': localRoutingHint.value += snippet; break
      case 'transition_phrase': localTransitionPhrase.value += snippet; break
      case 'trigger_situation': localTriggerSituation.value += snippet; break
      default: localSituation.value += snippet
    }
    flushNode()
  }

  const updateCondition = (index: number, value: string) => {
    const row = localBranches.value[index]
    if (!row) return
    localBranches.value[index] = { id: row.id, label: value }
    flushConditions()
  }

  const addCondition = () => {
    localBranches.value.push({ id: nanoid(), label: '' })
    flushConditions()
  }

  const removeCondition = (index: number) => {
    const id = nodeId.value
    const branch = localBranches.value[index]
    if (id && branch?.id) {
      const hid = branchSourceHandleId(branch.id)
      edges.value = edges.value.filter(
        e =>
          !(e.source === id
            && (e.sourceHandle === hid || e.sourceHandle === branch.id)),
      )
    }
    localBranches.value.splice(index, 1)
    flushConditions()
  }

  const toggleMustFollowNodeRef = (nid: string) => {
    if (localMustFollowNodeRefs.value.includes(nid))
      localMustFollowNodeRefs.value = localMustFollowNodeRefs.value.filter((x) => x !== nid)
    else
      localMustFollowNodeRefs.value = [...localMustFollowNodeRefs.value, nid]
    flushNode()
  }

  watch(localEntityType, (value) => {
    if (!nodeId.value || syncingFromGraph.value) return
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

  const isTrigger = computed(() => localNodeType.value === 'trigger')
  const isExpertise = computed(() => localNodeType.value === 'expertise')
  const isQuestion = computed(() => localNodeType.value === 'question')
  const isGoto = computed(() => localNodeType.value === 'goto')
  const isBusinessRule = computed(() => localNodeType.value === 'business_rule')
  const isEnd = computed(() => localNodeType.value === 'end')
  const isCondition = computed(() => localNodeType.value === 'condition')
  const isConversationNode = computed(() =>
    isTrigger.value || isExpertise.value || isQuestion.value || isGoto.value,
  )
  const showAxisTabs = computed(() => isExpertise.value || isQuestion.value)

  const axisTab = ref<'context' | 'content'>('context')
  watch(nodeId, () => {
    axisTab.value = 'context'
  })

  const nodeFormHint = computed((): string | null => {
    if (!showAxisTabs.value) return null
    return isExpertise.value
      ? 'Контекст: этап воронки, источники данных функций. Содержание: мотив, аргументы, фразы, табу.'
      : 'Контекст: где в воронке задаём вопрос, источники данных. Формулировки: сам вопрос и варианты.'
  })

  const connectionTitle = (nid: string): string => {
    const n = findNode(nid)
    const d = (n?.data || {}) as ScriptNodeData
    return String(d.title ?? d.label ?? nid)
  }

  const connectionNodeType = (nid: string): string => {
    const n = findNode(nid)
    const d = (n?.data || {}) as ScriptNodeData
    return String(d.node_type ?? '')
  }

  const branchLabelFromHandle = (sourceNid: string, sourceHandle?: string | null): string | null => {
    const branchId = parseBranchHandleId(sourceHandle)
    if (!branchId)
      return null
    const n = findNode(sourceNid)
    const d = (n?.data || {}) as ScriptNodeData
    const branches = Array.isArray(d.conditions) ? d.conditions : []
    const branch = branches.find(b => b?.id === branchId)
    const label = String(branch?.label ?? '').trim()
    return label || null
  }

  const incomingConnections = computed<StepConnectionSummary[]>(() => {
    const id = nodeId.value
    if (!id) return []
    return edges.value
      .filter(e => e.target === id)
      .map((e) => {
        const branchLabel = branchLabelFromHandle(String(e.source ?? ''), e.sourceHandle)
        return {
          edgeId: String(e.id ?? ''),
          nodeId: String(e.source ?? ''),
          title: connectionTitle(String(e.source ?? '')),
          nodeType: connectionNodeType(String(e.source ?? '')),
          relationLabel: branchLabel ? `По ветке: ${branchLabel}` : 'Прямой переход',
          direction: 'incoming' as const,
        }
      })
  })

  const outgoingConnections = computed<StepConnectionSummary[]>(() => {
    const id = nodeId.value
    if (!id) return []
    return edges.value
      .filter(e => e.source === id)
      .map((e) => {
        const branchLabel = branchLabelFromHandle(id, e.sourceHandle)
        return {
          edgeId: String(e.id ?? ''),
          nodeId: String(e.target ?? ''),
          title: connectionTitle(String(e.target ?? '')),
          nodeType: connectionNodeType(String(e.target ?? '')),
          relationLabel: branchLabel ? `Если: ${branchLabel}` : 'Следующий шаг',
          direction: 'outgoing' as const,
        }
      })
  })

  const hasScenarioConnections = computed(() =>
    incomingConnections.value.length > 0 || outgoingConnections.value.length > 0,
  )

  const availableScenarioStepOptions = computed(() => {
    const currentId = String(nodeId.value ?? '')
    return getNodes.value
      .map((n) => {
        const nid = String(n.id ?? '')
        const d = (n.data || {}) as ScriptNodeData
        return {
          id: nid,
          title: String(d.title ?? d.label ?? nid),
          nodeType: String(d.node_type ?? ''),
        }
      })
      .filter((row) => row.id && row.id !== currentId)
      .sort((a, b) => a.title.localeCompare(b.title, 'ru'))
  })

  return {
    localTitle,
    localNodeType,
    localStage,
    localLevel,
    localIsEntryPoint,
    localIsFlowEntry,
    localSituation,
    localWhyItWorks,
    localApproach,
    localExamplePhrasesStr,
    localWatchOut,
    localGoodQuestion,
    localWhenRelevant,
    localClientPhraseExamplesStr,
    localKeywordHintsStr,
    localWhyWeAsk,
    localAlternativePhrasingsStr,
    localExpectedAnswerType,
    localRoutingHint,
    localTransitionPhrase,
    localTriggerSituation,
    localOutcomeType,
    localFinalAction,
    localBranches,
    localDataSource,
    localEntityType,
    localEntityId,
    localRuleCondition,
    localRuleAction,
    localRulePriority,
    localRuleActive,
    localRequiresEntity,
    localMustFollowNodeRefs,
    localMotiveIds,
    localArgumentIds,
    localProofIds,
    localObjectionIds,
    localConstraintIds,
    localOutcomeId,
    localTargetFlowId,
    localTargetNodeRef,
    localIsCatalogRule,
    lastFocusedField,
    flushNode,
    insertVar,
    updateCondition,
    addCondition,
    removeCondition,
    toggleMustFollowNodeRef,
    toggleKgLink,
    setOutcomeEntity,
    isTrigger,
    isExpertise,
    isQuestion,
    isGoto,
    isBusinessRule,
    isEnd,
    isCondition,
    isConversationNode,
    showAxisTabs,
    axisTab,
    nodeFormHint,
    incomingConnections,
    outgoingConnections,
    hasScenarioConnections,
    availableScenarioStepOptions,
    CONVERSATION_STAGES,
  }
}

export type ScriptFlowInspectorModel = ReturnType<typeof useScriptFlowInspectorModel>

export const SCRIPT_FLOW_INSPECTOR_KEY: InjectionKey<ScriptFlowInspectorModel> = Symbol('scriptFlowInspector')
