// TanStack Query kalit-fabrikasi. Invalidatsiya izchil bo'lishi uchun markazlashtirilgan.

export const qk = {
  me: ['me'] as const,
  departments: ['departments'] as const,
  users: (params?: { department_id?: string; status?: string }) =>
    ['users', params ?? {}] as const,
  sites: ['sites'] as const,
  site: (id: string) => ['sites', id] as const,
  occupants: (id: string) => ['sites', id, 'occupants'] as const,
  lastLocations: ['locations', 'last'] as const,
  reviewQueue: ['checkins', 'review-queue'] as const,
  track: (id: string, from: string, to: string) =>
    ['employees', id, 'track', from, to] as const,
  timeline: (id: string, from: string, to: string) =>
    ['employees', id, 'timeline', from, to] as const,
}
