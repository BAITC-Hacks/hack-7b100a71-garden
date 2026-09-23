import { ApiError, type CareerApi, type RequestOptions } from '../types/api'
import type { CareerOverview, DatasetFiles, DatasetMode, Employee, HRAnalytics, SkillGap } from '../types/domain'
import type { EmployeeDetailDTO, EmployeeDTO, Envelope, EventDTO, HRAnalyticsDTO, RecommendationResultDTO, RoleProfileDTO, SkillDTO, ActivityRecordDTO } from '../types/transport'
import { getSession, type Session } from './session'

export interface HttpApiOptions {
  baseUrl: string
  getIdentity?: () => Session | null
  fetch?: typeof globalThis.fetch
}
const invalid = (message: string) => new ApiError('INVALID_RESPONSE', message)
const changed = () => new ApiError('BACKEND', 'The dataset changed while loading. Refresh to use one consistent snapshot.', { status: 409, backendCode: 'dataset_changed' })

export function mapEmployee(row: EmployeeDTO, levels: Record<string, number>, catalog: SkillDTO[], meta?: Envelope<unknown>['meta']): Employee {
  const names = new Map(catalog.map(skill => [skill.skill_id, skill.name]))
  return {
    id: row.employee_id, name: row.full_name, department: row.department, role: row.role, grade: row.grade,
    careerGoal: row.career_goal ? `${row.career_goal.target_role} / ${row.career_goal.target_grade}` : null,
    preferredLanguage: row.preferred_language, tenureMonths: row.tenure_months, tenureLabel: `${row.tenure_months} months`,
    workFormat: row.work_format, lastReviewDate: row.last_review_date,
    skills: Object.entries(levels).map(([id, current]) => ({ id, name: names.get(id) ?? id, current, scaleMax: 5 })),
    assessmentSkills: { ...row.skills }, version: meta?.version, asOf: meta?.as_of_date, raw: row,
  }
}

export function mapCareer(result: RecommendationResultDTO, employee: EmployeeDTO, skills: SkillDTO[], events: EventDTO[], profiles: RoleProfileDTO[]): CareerOverview {
  const names = new Map(skills.map(skill => [skill.skill_id, skill.name]))
  const catalog = new Map(events.map(event => [event.event_id, event]))
  const gap = (row: RecommendationResultDTO['skill_gaps'][number]): SkillGap => ({
    id: row.skill_id, name: names.get(row.skill_id) ?? row.skill_id, current: row.current,
    required: row.required, gap: row.gap, critical: row.critical, scaleMax: 5,
  })
  const target = result.target
  const profile = target ? profiles.find(item => item.role === target.role && item.grade === target.grade) : undefined
  if (target && !profile) throw invalid('The target profile is missing from the current catalog.')
  const levels = result.career_state.skills_reconstruction.effective_skills
  // Only display requirement coverage; readiness/gaps/ranking remain server-owned.
  const targetRequirements = profile ? Object.entries(profile.required_skills).map(([id, required]) => {
    const supplied = result.skill_gaps.find(item => item.skill_id === id)
    return supplied ? gap(supplied) : { id, name: names.get(id) ?? id, current: levels[id] ?? 0, required, gap: 0, critical: profile.critical_skills.includes(id), scaleMax: 5 }
  }) : []
  return {
    employeeId: result.employee_id, target,
    trajectory: target ? { kind: employee.role === target.role ? 'promotion' : 'transition', positions: [
      { role: employee.role, grade: employee.grade, state: 'current' }, { role: target.role, grade: target.grade, state: 'target' },
    ] } : null,
    readiness: result.career_readiness?.current != null ? { current: result.career_readiness.current } : null,
    skillGaps: result.skill_gaps.map(gap), targetRequirements,
    recommendations: result.recommendations.map(item => {
      const event = catalog.get(item.event_id)
      if (!event) throw invalid('A recommended event is missing from the current catalog.')
      return {
        eventId: item.event_id, rank: item.rank, title: item.title, score: item.score,
        type: event.type, format: event.format, durationMinutes: event.duration_hours * 60, careerImpact: null,
        skillImpact: item.simulation.target_skill_impact.map(impact => ({
          skillId: impact.skill_id, name: names.get(impact.skill_id) ?? impact.skill_id,
          current: impact.current, after: impact.after, required: impact.required, critical: impact.critical,
        })),
        readinessBefore: item.simulation.readiness_before, readinessAfter: item.simulation.readiness_after,
        explanation: {
          text: item.explanation?.text ?? null, language: item.explanation?.language, source: item.explanation?.source,
          factors: Object.entries(item.factors).map(([id, factor]) => ({ id, label: id, value: factor.normalized })),
        }, raw: item,
      }
    }),
    version: result.version, asOf: result.as_of, status: result.status, explanationSummary: result.explanation_summary,
    reconstruction: result.career_state.skills_reconstruction,
    skillsEstimated: result.career_state.skills_reconstruction.is_estimate,
    warnings: result.career_state.skills_reconstruction.warnings.map(item => item.message), raw: result,
  }
}

export function createHttpApi({ baseUrl, getIdentity = getSession, fetch: fetcher = globalThis.fetch }: HttpApiOptions): CareerApi {
  const base = baseUrl.trim().replace(/\/+$/, '')
  const configurationValid = (() => { try { const url = new URL(base); return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password && !url.search && !url.hash } catch { return false } })()
  function identity(employeeId?: string, hrOnly = false) {
    if (!configurationValid) throw new ApiError('CONFIGURATION', 'Set VITE_API_BASE_URL to the FastAPI HTTP(S) address.')
    const session = getIdentity()
    if (!session?.token) throw new ApiError('UNAUTHENTICATED', 'Enter your assigned API token and identity to continue.', { status: 401 })
    if ((hrOnly && session.role !== 'hr') || (employeeId && session.role === 'employee' && session.employeeId !== employeeId)) {
      throw new ApiError('FORBIDDEN', 'This workspace is not available to your identity.', { status: 403 })
    }
    return session
  }
  async function request<T>(path: string, init: RequestInit = {}): Promise<Envelope<T>> {
    const session = identity()
    init.signal?.throwIfAborted()
    const headers = new Headers(init.headers)
    headers.set('Authorization', `Bearer ${session.token}`)
    headers.set('Accept', 'application/json')
    let response: Response
    try { response = await fetcher(`${base}${path}`, { ...init, headers }) }
    catch (error) {
      if (init.signal?.aborted || (error instanceof Error && error.name === 'AbortError')) throw error
      throw new ApiError('NETWORK', 'Cannot reach the backend. Check its address, connection and CORS configuration.')
    }
    init.signal?.throwIfAborted()
    if (getIdentity()?.token !== session.token) throw new ApiError('UNAUTHENTICATED', 'Identity changed; sign in again.', { status: 401 })
    let payload: { data?: T; meta?: Envelope<T>['meta']; error?: { code?: string; message?: string; details?: unknown[] } }
    try { payload = await response.json() }
    catch (error) {
      if (init.signal?.aborted || (error instanceof Error && error.name === 'AbortError')) throw error
      throw new ApiError(response.ok ? 'INVALID_RESPONSE' : 'UNAVAILABLE', 'Backend returned an unreadable response.', { status: response.status })
    }
    init.signal?.throwIfAborted()
    if (getIdentity()?.token !== session.token) throw new ApiError('UNAUTHENTICATED', 'Identity changed; sign in again.', { status: 401 })
    if (!response.ok) {
      const code = response.status === 401 ? 'UNAUTHENTICATED' : response.status === 403 ? 'FORBIDDEN' : response.status === 404 ? 'NOT_FOUND' : response.status >= 500 ? 'UNAVAILABLE' : 'BACKEND'
      throw new ApiError(code, payload?.error?.message ?? `Backend request failed (${response.status}).`, {
        status: response.status, backendCode: payload?.error?.code, details: payload?.error?.details,
      })
    }
    if (!payload || typeof payload !== 'object' || !Object.hasOwn(payload, 'data')) throw invalid('Backend response is missing its data envelope.')
    return payload as Envelope<T>
  }
  async function list<T>(path: string, options?: RequestOptions): Promise<Envelope<T[]>> {
    const data: T[] = []
    let first: Envelope<T[]>['meta']
    for (let offset = 0; ; ) {
      const page = await request<T[]>(`${path}?offset=${offset}&limit=500`, options)
      const meta = page.meta
      if (!Array.isArray(page.data) || !meta || !Number.isInteger(meta.version) || !Number.isInteger(meta.total) || meta.total! < 0 || meta.offset !== offset) throw invalid('Backend pagination metadata is invalid.')
      if (first && (first.version !== meta.version || first.total !== meta.total || first.as_of_date !== meta.as_of_date)) throw changed()
      first ??= meta
      data.push(...page.data)
      if (data.length === meta.total) return { data, meta: { ...meta, offset: 0 } }
      if (!page.data.length || data.length > meta.total!) throw invalid('Backend pagination did not match its total.')
      offset += page.data.length
    }
  }
  function consistent(version: number | undefined, responses: Array<Envelope<unknown>>) {
    if (!Number.isInteger(version)) throw invalid('Backend response is missing its snapshot version.')
    if (responses.some(item => item.meta?.version !== version)) throw changed()
  }
  function datasetBody(files: DatasetFiles, mode: DatasetMode) {
    identity(undefined, true)
    if (!['append', 'replace'].includes(mode)) throw new ApiError('CONFIGURATION', 'Select append or replace mode.')
    const body = new FormData()
    for (const [field, file] of Object.entries(files)) if (file) body.append(field, file)
    return body
  }
  return {
    async getEmployees(options) {
      identity(undefined, true)
      const result = await list<EmployeeDTO>('/employees', options)
      // Directory responses are assessment baselines, not effective skills.
      return result.data.map(row => mapEmployee(row, {}, [], result.meta))
    },
    async getEmployee(id, options) {
      identity(id)
      const [profile, skills] = await Promise.all([
        request<EmployeeDetailDTO>(`/employees/${encodeURIComponent(id)}`, options), list<SkillDTO>('/skills', options),
      ])
      consistent(profile.meta?.version, [skills])
      return mapEmployee(profile.data.employee, profile.data.effective_skills, skills.data, profile.meta)
    },
    async getEmployeeHistory(id, options) {
      identity(id)
      const [history, events] = await Promise.all([list<ActivityRecordDTO>(`/employees/${encodeURIComponent(id)}/history`, options), list<EventDTO>('/events', options)])
      consistent(history.meta?.version, [events])
      return history.data.map(row => ({
        id: row.record_id, eventId: row.event_id, title: events.data.find(event => event.event_id === row.event_id)?.title ?? row.event_id,
        status: row.status, updatedAt: row.completed_at ?? row.completed_on ?? row.date,
        date: row.date, completedAt: row.completed_at, completedOn: row.completed_on, completionPct: row.completion_pct,
        score: row.score, feedbackRating: row.feedback_rating, assignedBy: row.assigned_by, raw: row,
      }))
    },
    async getEvents(options) {
      const result = await list<EventDTO>('/events', options)
      return result.data.map(row => ({ id: row.event_id, title: row.title, type: row.type, format: row.format, durationMinutes: row.duration_hours * 60 }))
    },
    async getRecommendations(id, options) {
      identity(id)
      const [result, profile, skills, events, profiles] = await Promise.all([
        request<RecommendationResultDTO>(`/employees/${encodeURIComponent(id)}/recommendations`, options),
        request<EmployeeDetailDTO>(`/employees/${encodeURIComponent(id)}`, options),
        list<SkillDTO>('/skills', options), list<EventDTO>('/events', options), list<RoleProfileDTO>('/role-profiles', options),
      ])
      consistent(result.data.version, [profile, skills, events, profiles])
      return mapCareer(result.data, profile.data.employee, skills.data, events.data, profiles.data)
    },
    async getHRAnalytics(options): Promise<HRAnalytics> {
      identity(undefined, true)
      const result = await request<HRAnalyticsDTO>('/hr/analytics', options)
      return { ...result.data, version: result.meta?.version, asOf: result.meta?.as_of_date }
    },
    async completeActivity(employeeId, eventId, options) {
      identity(employeeId)
      if (!options.idempotencyKey?.trim()) throw new ApiError('CONFIGURATION', 'A completion action requires its idempotency key.')
      const result = await request<Awaited<ReturnType<CareerApi['completeActivity']>>>(`/activities/${encodeURIComponent(eventId)}/complete`, {
        method: 'POST', signal: options.signal,
        headers: { 'Content-Type': 'application/json', 'Idempotency-Key': options.idempotencyKey },
        body: JSON.stringify({ employee_id: employeeId, ...(options.recordId ? { record_id: options.recordId } : {}),
          ...(options.score !== undefined ? { score: options.score } : {}), ...(options.feedbackRating !== undefined ? { feedback_rating: options.feedbackRating } : {}) }),
      })
      return result.data
    },
    async validateDataset(files, mode = 'append', options) {
      return (await request<Awaited<ReturnType<CareerApi['validateDataset']>>>(`/datasets/validate?mode=${mode}`, { method: 'POST', body: datasetBody(files, mode), signal: options?.signal })).data
    },
    async uploadDataset(files, mode = 'append', options) {
      return (await request<Awaited<ReturnType<CareerApi['uploadDataset']>>>(`/datasets/upload?mode=${mode}`, { method: 'POST', body: datasetBody(files, mode), signal: options?.signal })).data
    },
  }
}
