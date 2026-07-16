import type { Role } from '../api/types'

/** Barcha rollar — select'lar uchun. */
export const ROLE_VALUES: Role[] = [
  'org_admin',
  'hr',
  'dept_head',
  'field_employee',
]

/** Xodim/xodimlarni yaratish/tahrirlash/import — org_admin va hr. */
export function canManageUsers(role: Role | undefined): boolean {
  return role === 'org_admin' || role === 'hr'
}

/** Obyektlarni yaratish/tahrirlash — org_admin va hr. */
export function canManageSites(role: Role | undefined): boolean {
  return role === 'org_admin' || role === 'hr'
}

/** Ko'rib-chiqish navbati — org_admin, hr, dept_head. */
export function canReview(role: Role | undefined): boolean {
  return role === 'org_admin' || role === 'hr' || role === 'dept_head'
}

/** field_employee'dan boshqa har kim menejer-ko'rinishini ko'radi. */
export function isFieldEmployee(role: Role | undefined): boolean {
  return role === 'field_employee'
}
