import type { DepartmentOut } from '../api/types'

export interface DeptTreeNode {
  title: string
  key: string
  value: string
  children?: DeptTreeNode[]
}

/** id → name xaritasi (jadval/ustunlarda ko'rsatish uchun). */
export function buildDepartmentMap(
  list: DepartmentOut[],
): Record<string, string> {
  const map: Record<string, string> = {}
  for (const d of list) map[d.id] = d.name
  return map
}

/** parent_id bo'yicha Tree/TreeSelect uchun daraxt tuzadi. */
export function buildDepartmentTree(list: DepartmentOut[]): DeptTreeNode[] {
  const nodes = new Map<string, DeptTreeNode>()
  for (const d of list) {
    nodes.set(d.id, { title: d.name, key: d.id, value: d.id, children: [] })
  }
  const roots: DeptTreeNode[] = []
  for (const d of list) {
    const node = nodes.get(d.id)
    if (!node) continue
    const parent = d.parent_id ? nodes.get(d.parent_id) : undefined
    if (parent) parent.children?.push(node)
    else roots.push(node)
  }
  // Bo'sh children'ni tozalab, barg tugunlarni soddalashtiramiz.
  const prune = (n: DeptTreeNode): DeptTreeNode => {
    if (n.children && n.children.length === 0) {
      const { children: _children, ...rest } = n
      return rest
    }
    return { ...n, children: n.children?.map(prune) }
  }
  return roots.map(prune)
}

/** Bo'lim va uning barcha avlodlari id'lari (subtree filtri uchun). */
export function departmentSubtreeIds(
  list: DepartmentOut[],
  rootId: string,
): Set<string> {
  const root = list.find((d) => d.id === rootId)
  const ids = new Set<string>()
  if (!root) return ids
  for (const d of list) {
    if (d.path === root.path || d.path.startsWith(root.path + '.')) {
      ids.add(d.id)
    }
  }
  ids.add(rootId)
  return ids
}
