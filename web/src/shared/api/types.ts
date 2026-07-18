// API kontraktidagi (docs/API.md) barcha response/request shakllari.

export type Role = 'org_admin' | 'hr' | 'dept_head' | 'field_employee'

export type CheckinVerdict = 'pending' | 'verified' | 'flagged' | 'rejected'

// --- Auth ---
export interface InviteResolveResponse {
  org_id: string
  org_name: string
  masked_phone: string
}

export interface OtpRequestResponse {
  sent: boolean
  dev_code?: string | null
}

export interface DeviceInfo {
  platform: string
  fingerprint: string
  model?: string
  pubkey?: string
}

export interface ActivateUser {
  id: string
  role: Role
  org_id: string
  org_name: string
}

export interface ActivateResponse {
  access_token: string
  refresh_token: string
  user: ActivateUser
}

export interface LoginUser {
  id: string
  role: Role
  org_id: string
  full_name: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  user: LoginUser
}

export interface MeResponse {
  id: string
  org_id: string
  role: Role
  full_name: string
}

// --- Departments ---
export interface DepartmentOut {
  id: string
  name: string
  path: string
  parent_id: string | null
  head_user_id: string | null
  created_at: string
}

// --- Users ---
export interface UserOut {
  id: string
  full_name: string
  phone: string
  role: Role
  department_id: string | null
  employee_no: string | null
  status: string
  face_enrolled_at: string | null
  created_at: string
}

export interface CreateUserInput {
  full_name: string
  phone: string
  role?: Role
  department_id?: string | null
  employee_no?: string | null
}

export interface UpdateUserInput {
  full_name?: string
  role?: Role
  department_id?: string | null
  employee_no?: string | null
  status?: string
}

export interface InviteResult {
  token: string
  code: string
  user_id: string
}

export interface ImportRowResult {
  row: number
  status: string
  detail?: string | null
  user_id?: string | null
}

export interface ImportResult {
  total: number
  created: number
  errors: number
  rows: ImportRowResult[]
}

// --- Sites ---
export interface SiteOut {
  id: string
  name: string
  lat: number
  lon: number
  radius_m: number
  min_dwell_minutes: number
  address: string | null
  status: string
}

export interface CreateSiteInput {
  name: string
  lat: number
  lon: number
  radius_m?: number
  min_dwell_minutes?: number
  address?: string | null
}

export interface UpdateSiteInput {
  name?: string
  lat?: number
  lon?: number
  radius_m?: number
  min_dwell_minutes?: number
  address?: string | null
  status?: string
}

export interface Occupant {
  user_id: string
  full_name: string
  entered_at: string
}

// --- Tracking / Locations ---
export interface LivePoint {
  user_id: string
  ts: string
  lat: number
  lon: number
  accuracy_m: number | null
  battery: number | null
  is_mock: boolean
  site_id: string | null
}

export interface LastLocationsResponse {
  points: LivePoint[]
}

// --- Check-ins ---
export interface CheckinOut {
  id: string
  user_id: string
  site_id: string | null
  ts: string
  lat: number
  lon: number
  inside_geofence: boolean
  verdict: CheckinVerdict
  verdict_reasons: string[]
  risk_score: number
  comment: string | null
  duplicate: boolean
}

export type ReviewAction = 'approve' | 'reject'

// --- History (track / timeline). Kontraktda nuqta ichki shakllari to'liq
// ko'rsatilmagan — himoyaviy (optional) maydonlar bilan modellashtirildi. ---
export interface TrackPoint {
  ts: string
  lat: number
  lon: number
  accuracy_m?: number | null
}

export interface TrackStop {
  lat: number
  lon: number
  arrived_at?: string
  departed_at?: string
  entered_at?: string
  exited_at?: string
  started_at?: string
  ended_at?: string
  dwell_seconds?: number
  site_id?: string | null
  site_name?: string | null
}

export interface TrackGap {
  from_ts?: string
  to_ts?: string
  start_ts?: string
  end_ts?: string
  from_lat?: number
  from_lon?: number
  to_lat?: number
  to_lon?: number
  gap_seconds?: number
}

export interface TrackResponse {
  user_id: string
  points: TrackPoint[]
  stops: TrackStop[]
  gaps: TrackGap[]
  checkins: CheckinOut[]
}

export interface TimelineSegment {
  site_id: string
  site_name: string
  entered_at: string
  exited_at: string | null
  dwell_seconds: number
}

// --- WS live-stream xabar-turlari ---
export interface WsSnapshot {
  type: 'snapshot'
  points: LivePoint[]
}

export interface WsPoint extends LivePoint {
  type: 'point'
}

export interface WsSiteEnter {
  type: 'site_enter'
  user_id: string
  site_id: string
  ts: string
  dwell_seconds: null
}

export interface WsSiteExit {
  type: 'site_exit'
  user_id: string
  site_id: string
  ts: string
  dwell_seconds: number
}

export interface WsCheckin {
  type: 'checkin'
  user_id: string
  checkin_id: string
  site_id: string | null
  verdict: CheckinVerdict
  risk_score: number
  ts: string
}

export interface WsPing {
  type: 'ping'
}

export type WsMessage =
  | WsSnapshot
  | WsPoint
  | WsSiteEnter
  | WsSiteExit
  | WsCheckin
  | WsPing
