const RELATION_LABELS: Record<string, string> = {
  HAS_SEMANTIC: 'связан с',
  GRAPH_RELATION: 'отношение',
  NEXT_STEP_TO: 'следующий шаг',
  PROVIDED_BY: 'выполняет',
  COVERS_SERVICE: 'покрывает услугу',

  next_step_to: 'следующий шаг',
  occurs_at_stage: 'на этапе',
  uses_variable: 'использует переменную',
  motivated_by: 'мотивировано',
  argues_with: 'аргументируется',
  supported_by_proof: 'подкрепляется',
  handles_objection: 'обрабатывает возражение',
  blocked_by_constraint: 'блокируется ограничением',
  covers_service: 'покрывает услугу',
  provided_by: 'выполняет',
  addresses_concern: 'отвечает на сомнение',
  uses_tactic: 'использует тактику',
  supports_trust: 'формирует доверие',
  references_specialist: 'упоминает специалиста',
  leads_to_outcome: 'ведёт к результату',
  relates_to: 'связан с',
  is_service: 'является услугой',
  is_specialist: 'является специалистом',
}

export function formatRelation(raw: string | null | undefined): string {
  if (!raw) return ''
  const direct = RELATION_LABELS[raw]
  if (direct) return direct
  const upper = RELATION_LABELS[raw.toUpperCase()]
  if (upper) return upper
  const lower = RELATION_LABELS[raw.toLowerCase()]
  if (lower) return lower
  return raw
}
