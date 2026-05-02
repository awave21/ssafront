/**
 * useFlowEdgePath — расчёт SVG-путей для рёбер.
 *
 * Поддерживает: straight, smoothstep (с rounded corners), bezier.
 * По умолчанию smoothstep — оптимальный баланс читаемости и производительности.
 */

export type EdgePathType = 'straight' | 'smoothstep' | 'bezier'

export interface EdgeEndpoints {
  sourceX: number
  sourceY: number
  targetX: number
  targetY: number
}

/** Прямая линия. */
export function straightPath({ sourceX, sourceY, targetX, targetY }: EdgeEndpoints): string {
  return `M ${sourceX} ${sourceY} L ${targetX} ${targetY}`
}

/**
 * SmoothStep — ортогональные сегменты со скруглёнными углами.
 * Дешевле bezier, чище визуально для flowcharts.
 */
export function smoothStepPath(
  endpoints: EdgeEndpoints,
  options: { borderRadius?: number; offset?: number } = {},
): string {
  const { sourceX, sourceY, targetX, targetY } = endpoints
  const borderRadius = options.borderRadius ?? 8
  const offset = options.offset ?? 20

  // Вычисляем середину по X — куда идёт «лестница».
  const dx = targetX - sourceX

  // Если target слева от source (обратное направление) — выводим линию вверх/вниз вокруг.
  if (dx < offset * 2) {
    // Hooked path: выходим, идём вертикально вокруг, входим.
    const sourceXOut = sourceX + offset
    const targetXIn = targetX - offset
    const midY = (sourceY + targetY) / 2
    return roundedPath([
      [sourceX, sourceY],
      [sourceXOut, sourceY],
      [sourceXOut, midY],
      [targetXIn, midY],
      [targetXIn, targetY],
      [targetX, targetY],
    ], borderRadius)
  }

  // Стандартный H-путь: середина dx по X.
  const midX = sourceX + dx / 2
  return roundedPath([
    [sourceX, sourceY],
    [midX, sourceY],
    [midX, targetY],
    [targetX, targetY],
  ], borderRadius)
}

/** Cubic bezier — для backwards-compat если нужно. */
export function bezierPath({ sourceX, sourceY, targetX, targetY }: EdgeEndpoints): string {
  const dx = Math.abs(targetX - sourceX) * 0.5
  const c1x = sourceX + dx
  const c2x = targetX - dx
  return `M ${sourceX} ${sourceY} C ${c1x} ${sourceY}, ${c2x} ${targetY}, ${targetX} ${targetY}`
}

/**
 * Строит SVG path по списку точек со скруглёнными углами.
 * Используется для smoothstep — рисует ортогональные сегменты с закруглениями
 * на стыках.
 */
function roundedPath(points: Array<[number, number]>, r: number): string {
  if (points.length < 2) return ''
  if (points.length === 2) {
    return `M ${points[0]![0]} ${points[0]![1]} L ${points[1]![0]} ${points[1]![1]}`
  }

  let d = `M ${points[0]![0]} ${points[0]![1]}`
  for (let i = 1; i < points.length - 1; i++) {
    const prev = points[i - 1]!
    const cur = points[i]!
    const next = points[i + 1]!
    // Вектор входа в угол
    const inDx = cur[0] - prev[0]
    const inDy = cur[1] - prev[1]
    const inLen = Math.hypot(inDx, inDy)
    // Вектор выхода из угла
    const outDx = next[0] - cur[0]
    const outDy = next[1] - cur[1]
    const outLen = Math.hypot(outDx, outDy)

    const radius = Math.min(r, inLen / 2, outLen / 2)

    if (radius < 1) {
      d += ` L ${cur[0]} ${cur[1]}`
      continue
    }

    // Точка начала закругления (от cur назад по in-вектору на radius)
    const startX = cur[0] - (inDx / inLen) * radius
    const startY = cur[1] - (inDy / inLen) * radius
    // Точка конца закругления (от cur вперёд по out-вектору на radius)
    const endX = cur[0] + (outDx / outLen) * radius
    const endY = cur[1] + (outDy / outLen) * radius

    d += ` L ${startX} ${startY} Q ${cur[0]} ${cur[1]} ${endX} ${endY}`
  }
  // Последний сегмент в финальную точку.
  const last = points[points.length - 1]!
  d += ` L ${last[0]} ${last[1]}`
  return d
}

/**
 * Универсальная функция выбора path-генератора.
 */
export function buildEdgePath(type: EdgePathType, endpoints: EdgeEndpoints, options?: { borderRadius?: number; offset?: number }): string {
  switch (type) {
    case 'straight': return straightPath(endpoints)
    case 'bezier': return bezierPath(endpoints)
    case 'smoothstep':
    default: return smoothStepPath(endpoints, options)
  }
}

/**
 * Вычисляет endpoints из source/target node bbox.
 * Source: правый центр source-ноды. Target: левый центр target-ноды.
 * (Для MVP. В Phase 2 будем учитывать handle-positions для condition-веток.)
 */
export function endpointsFromBoxes(
  source: { x: number; y: number; width: number; height: number },
  target: { x: number; y: number; width: number; height: number },
): EdgeEndpoints {
  return {
    sourceX: source.x + source.width,
    sourceY: source.y + source.height / 2,
    targetX: target.x,
    targetY: target.y + target.height / 2,
  }
}
