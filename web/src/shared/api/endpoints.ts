// Barcha REST endpointlar uchun tiplangan chaqiruvlar (docs/API.md).
import { api } from './client'
import type {
  ActivateResponse,
  CheckinOut,
  CreateSiteInput,
  CreateUserInput,
  DepartmentOut,
  DeviceInfo,
  ImportResult,
  InviteResolveResponse,
  InviteResult,
  LastLocationsResponse,
  LoginResponse,
  MeResponse,
  Occupant,
  OtpRequestResponse,
  ReviewAction,
  SiteOut,
  TimelineSegment,
  TrackResponse,
  UpdateSiteInput,
  UpdateUserInput,
  UserOut,
} from './types'

// --- Auth ---
export const authApi = {
  login: (input: { username: string; password: string }) =>
    api.post<LoginResponse>('/v1/auth/login', input).then((r) => r.data),
  resolveInvite: (token: string) =>
    api
      .post<InviteResolveResponse>('/v1/auth/invites/resolve', { token })
      .then((r) => r.data),
  requestOtp: (token: string) =>
    api
      .post<OtpRequestResponse>('/v1/auth/otp/request', { token })
      .then((r) => r.data),
  activate: (input: { token: string; otp_code: string; device: DeviceInfo }) =>
    api.post<ActivateResponse>('/v1/auth/activate', input).then((r) => r.data),
  me: () => api.get<MeResponse>('/v1/me').then((r) => r.data),
}

// --- Departments ---
export const departmentsApi = {
  list: () =>
    api.get<DepartmentOut[]>('/v1/departments').then((r) => r.data),
  create: (input: { name: string; parent_id?: string | null }) =>
    api.post<DepartmentOut>('/v1/departments', input).then((r) => r.data),
}

// --- Users ---
export const usersApi = {
  list: (params?: { department_id?: string; status?: string }) =>
    api.get<UserOut[]>('/v1/users', { params }).then((r) => r.data),
  create: (input: CreateUserInput) =>
    api.post<UserOut>('/v1/users', input).then((r) => r.data),
  update: (id: string, input: UpdateUserInput) =>
    api.patch<UserOut>(`/v1/users/${id}`, input).then((r) => r.data),
  invite: (id: string) =>
    api.post<InviteResult>(`/v1/users/${id}/invite`).then((r) => r.data),
  import: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api
      .post<ImportResult>('/v1/users/import', form)
      .then((r) => r.data)
  },
}

// --- Sites ---
export const sitesApi = {
  list: () => api.get<SiteOut[]>('/v1/sites').then((r) => r.data),
  get: (id: string) => api.get<SiteOut>(`/v1/sites/${id}`).then((r) => r.data),
  create: (input: CreateSiteInput) =>
    api.post<SiteOut>('/v1/sites', input).then((r) => r.data),
  update: (id: string, input: UpdateSiteInput) =>
    api.patch<SiteOut>(`/v1/sites/${id}`, input).then((r) => r.data),
  occupants: (id: string) =>
    api.get<Occupant[]>(`/v1/sites/${id}/occupants`).then((r) => r.data),
}

// --- Locations ---
export const locationsApi = {
  last: () =>
    api
      .get<LastLocationsResponse>('/v1/locations/last')
      .then((r) => r.data),
}

// --- Check-ins ---
export const checkinsApi = {
  reviewQueue: () =>
    api
      .get<CheckinOut[]>('/v1/checkins/review-queue')
      .then((r) => r.data),
  review: (id: string, input: { action: ReviewAction; reason: string }) =>
    api
      .post<CheckinOut>(`/v1/checkins/${id}/review`, input)
      .then((r) => r.data),
  comment: (id: string, text: string) =>
    api
      .post<CheckinOut>(`/v1/checkins/${id}/comment`, { text })
      .then((r) => r.data),
}

// --- History (employees) ---
export const employeesApi = {
  track: (
    id: string,
    params: {
      ts_from: string
      ts_to: string
      stop_min_seconds?: number
      stop_radius_m?: number
    },
  ) =>
    api
      .get<TrackResponse>(`/v1/employees/${id}/track`, { params })
      .then((r) => r.data),
  timeline: (id: string, params: { ts_from: string; ts_to: string }) =>
    api
      .get<TimelineSegment[]>(`/v1/employees/${id}/timeline`, { params })
      .then((r) => r.data),
}
