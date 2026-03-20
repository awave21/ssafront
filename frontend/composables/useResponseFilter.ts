/**
 * Composable: response filtering / transform logic
 * Handles: field tree, transform generation, preview
 */
import { ref, computed, type Ref } from 'vue'
import type { Tool, ToolTestResponse, ResponseTransform } from '~/types/tool'
import type { FieldNodeData } from '~/components/agents/FieldNode.vue'

export const useResponseFilter = (
  selectedFunction: Ref<Tool | null>,
  testResult: Ref<ToolTestResponse | null>,
  markAsChanged: () => void,
) => {
  const fieldTree = ref<FieldNodeData[]>([])
  const showResponsePanel = ref(true)

  // Build field tree from raw response
  function buildFieldTree(obj: any, prefix = '', parentKey = ''): FieldNodeData[] {
    if (!obj || typeof obj !== 'object') return []

    if (Array.isArray(obj)) {
      if (obj.length === 0) return []
      const arrayNode: FieldNodeData = {
        path: prefix || 'items',
        key: parentKey || `items [${obj.length}]`,
        type: 'array',
        example: `${obj.length} элемент(ов)`,
        selected: true,
        rename: parentKey || 'items',
        children: obj.length > 0 ? buildFieldTree(obj[0], `${prefix}[]`, '') : []
      }
      return [arrayNode]
    }

    return Object.entries(obj).map(([key, value]) => {
      const path = prefix ? `${prefix}.${key}` : key
      const isArray = Array.isArray(value)
      const node: FieldNodeData = {
        path,
        key: isArray ? `${key} [${value.length}]` : key,
        type: isArray ? 'array' : typeof value,
        example: typeof value === 'object' ? undefined : value,
        selected: true,
        rename: key
      }
      if (isArray && value.length > 0) {
        node.children = buildFieldTree(value[0], `${path}[]`, key)
      } else if (typeof value === 'object' && value !== null && !isArray) {
        node.children = buildFieldTree(value, path, key)
      }
      return node
    })
  }

  // Apply saved selection state
  function applySelectionState(freshNodes: FieldNodeData[], savedNodes: FieldNodeData[]) {
    const savedMap = new Map(savedNodes.map(n => [n.path, n]))
    freshNodes.forEach(node => {
      const saved = savedMap.get(node.path)
      if (saved) {
        node.selected = saved.selected
        if (node.children && saved.children) applySelectionState(node.children, saved.children)
      }
    })
  }

  function hasAnySelectedChild(node: FieldNodeData): boolean {
    if (!node.children) return false
    return node.children.some(c => c.selected || hasAnySelectedChild(c))
  }

  // Generate response transform
  function generateResponseTransform(fields: FieldNodeData[]): ResponseTransform {
    const flatFields: FieldNodeData[] = []
    const arrayGroups: Map<string, FieldNodeData[]> = new Map()

    const flatten = (nodes: FieldNodeData[]) => {
      nodes.forEach(node => {
        if (node.selected) {
          const skipParent = hasAnySelectedChild(node)
          if (!skipParent) {
            if (node.path.includes('[]')) {
              const arrayPath = node.path.split('[]')[0]
              if (!arrayGroups.has(arrayPath)) arrayGroups.set(arrayPath, [])
              arrayGroups.get(arrayPath)!.push(node)
            } else {
              flatFields.push(node)
            }
          }
        }
        if (node.children) flatten(node.children)
      })
    }
    flatten(fields)

    return {
      mode: 'fields' as const,
      fields: flatFields.map(f => ({ source: f.path, target: f.path })),
      arrays: Array.from(arrayGroups.entries()).map(([source, fields]) => ({
        source,
        target: source.split('.').pop() || 'items',
        fields: fields.map(f => {
          const pathAfterArray = f.path.split('[]')[1]?.slice(1) || f.key
          return { source: pathAfterArray, target: pathAfterArray }
        })
      }))
    }
  }

  const stripExamples = (nodes: FieldNodeData[]): FieldNodeData[] =>
    nodes.map(n => ({
      ...n,
      example: undefined,
      children: n.children ? stripExamples(n.children) : undefined
    }))

  const handleToggle = (field: FieldNodeData) => {
    field.selected = !field.selected
    updateTransform()
  }

  const updateTransform = () => {
    if (selectedFunction.value) {
      const transform = generateResponseTransform(fieldTree.value) as any
      transform._fieldTree = stripExamples(fieldTree.value)
      selectedFunction.value.response_transform = transform
      markAsChanged()
    }
  }

  // Apply transform for preview
  function resolvePath(obj: any, path: string): any {
    return path.split('.').reduce((curr: any, key: string) => curr?.[key], obj)
  }

  function setNestedValue(obj: any, path: string, value: any) {
    const parts = path.split('.')
    let current = obj
    for (let i = 0; i < parts.length - 1; i++) {
      if (!current[parts[i]]) current[parts[i]] = {}
      current = current[parts[i]]
    }
    current[parts[parts.length - 1]] = value
  }

  function applyTransformLocally(raw: any, transform: ResponseTransform): any {
    if (transform.mode === 'fields') {
      if (Array.isArray(raw)) {
        const rootArrayTransform = transform.arrays?.find(a =>
          a.source === 'items' || a.source === '' || a.source === '[]'
        )
        if (rootArrayTransform && rootArrayTransform.fields) {
          return raw.map(item => {
            const newItem: any = {}
            rootArrayTransform.fields.forEach(({ source: s, target: t }) => {
              const cleanSource = s.replace(/^\[\]\.?/, '')
              const value = cleanSource ? resolvePath(item, cleanSource) : item
              setNestedValue(newItem, t, value)
            })
            return newItem
          })
        }
        return raw
      }
      const result: any = {}
      transform.fields?.forEach(({ source, target }) => {
        const value = resolvePath(raw, source)
        setNestedValue(result, target, value)
      })
      transform.arrays?.forEach(({ source, target, fields }) => {
        const arr = resolvePath(raw, source)
        if (Array.isArray(arr)) {
          result[target] = arr.map(item => {
            const newItem: any = {}
            fields.forEach(({ source: s, target: t }) => {
              const value = resolvePath(item, s)
              setNestedValue(newItem, t, value)
            })
            return newItem
          })
        }
      })
      return result
    }
    return raw
  }

  const previewTransformed = computed(() => {
    if (!testResult.value?.raw_body || !selectedFunction.value?.response_transform) return null
    return applyTransformLocally(testResult.value.raw_body, selectedFunction.value.response_transform)
  })

  // Called after test completes to refresh field tree
  const onTestComplete = (response: ToolTestResponse) => {
    if (response.raw_body) {
      const freshTree = buildFieldTree(response.raw_body)
      const savedTree = (selectedFunction.value?.response_transform as any)?._fieldTree
      if (Array.isArray(savedTree) && savedTree.length > 0) applySelectionState(freshTree, savedTree)
      fieldTree.value = freshTree
      updateTransform()
    }
  }

  return {
    fieldTree,
    showResponsePanel,
    handleToggle,
    updateTransform,
    previewTransformed,
    buildFieldTree,
    applySelectionState,
    onTestComplete,
  }
}
