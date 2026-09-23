import { ApiError, type CareerApi, type RequestOptions } from '../types/api'
import type { ActivityStatus } from '../types/domain'
import { createHttpClient, type HttpClient, type HttpClientOptions } from './httpClient'
import { createHttpDatasetApi } from './httpDatasetApi'
import { getApiToken } from './apiSession'
import { mapEmployee, mapHRAnalytics, mapOverview, number, object, rows, text, type SkillNames } from './httpMappers'

const datasetChanged = () => new ApiError('CONFLICT', 'The dataset changed while loading. Please refresh the view.', { backendCode: 'dataset_changed', status: 409 })

// Retry reads only, and only when the server snapshot changes during assembly.
async function consistent<T>(read: () => Promise<T>): Promise<T> {
  for (let attempt = 0; ; attempt++) {
    try { return await read() } catch (error) {
      if (!(error instanceof ApiError) || error.backendCode !== 'dataset_changed' || attempt >= 2) throw error
    }
  }
}

export async function readAllPages(client: HttpClient, path: string, options?: RequestOptions) {
  return consistent(async () => {
    const all: unknown[] = []
    let version: number | undefined
    for (;;) {
      const response = await client.requestEnvelope<unknown[]>(`${path}?offset=${all.length}&limit=500`, { signal: options?.signal })
      const page = rows(response.data)
      const meta = response.meta
      if (typeof meta?.version !== 'number' || !Number.isInteger(meta.total) || meta.total! < 0 || meta.offset !== all.length) {
        throw new ApiError('INVALID_RESPONSE', 'The paginated API response has incomplete metadata.')
      }
      if (version !== undefined && version !== meta.version) throw datasetChanged()
      version = meta.version
      all.push(...page)
      if (all.length === meta.total) return { data: all, version }
      if (all.length > meta.total! || page.length === 0) throw new ApiError('INVALID_RESPONSE', 'The paginated API response is inconsistent.')
    }
  })
}

export function createHttpApi(options: HttpClientOptions): CareerApi {
  const client = createHttpClient(options)
  const getToken = options.getToken ?? getApiToken
  let sessionToken = getToken()
  const catalogCache = new Map<number, SkillNames>()
  const completionKeys = new Map<string, string>()
  function synchronizeSession() {
    if (sessionToken !== getToken()) { sessionToken = getToken(); catalogCache.clear(); completionKeys.clear() }
  }
  async function skillNames(version: number | undefined, request?: RequestOptions): Promise<SkillNames> {
    synchronizeSession()
    if (version !== undefined && catalogCache.has(version)) return catalogCache.get(version)!
    const catalog = await readAllPages(client, '/skills', request)
    if (version !== undefined && catalog.version !== version) throw datasetChanged()
    const names = new Map(catalog.data.map((value) => { const skill = object(value); return [text(skill.skill_id), text(skill.name)] }))
    catalogCache.clear()
    catalogCache.set(catalog.version, names)
    return names
  }
  return {
    async getEmployees(request) {
      const response = await readAllPages(client, '/employees', request)
      // Directory rows are baseline profiles; current progress comes from detail.
      return response.data.map((employee) => mapEmployee(employee, new Map(), undefined, response.version))
    },
    getEmployee(id, request) {
      return consistent(async () => {
        const response = await client.requestEnvelope<unknown>(`/employees/${encodeURIComponent(id)}`, { signal: request?.signal })
        const detail = object(response.data)
        if (number(response.meta?.version) === undefined) throw new ApiError('INVALID_RESPONSE', 'The profile response is missing its snapshot version.')
        const names = await skillNames(response.meta?.version, request)
        const employee = mapEmployee(detail.employee, names, object(detail.effective_skills, 'effective skills'), response.meta?.version)
        if (employee.id !== id) throw new ApiError('INVALID_RESPONSE', 'The profile response belongs to another employee.')
        return employee
      })
    },
    async getEmployeeHistory(id, request) {
      const response = await readAllPages(client, `/employees/${encodeURIComponent(id)}/history`, request)
      return response.data.map((value) => {
        const record = object(value)
        return { id: text(record.record_id), eventId: text(record.event_id), status: text(record.status) as ActivityStatus,
          updatedAt: typeof record.completed_at === 'string' ? record.completed_at : undefined,
          enrolledOn: text(record.date), completedOn: typeof record.completed_on === 'string' ? record.completed_on : null }
      })
    },
    async getEvents(request) {
      const response = await readAllPages(client, '/events', request)
      return response.data.map((value) => {
        const event = object(value); const duration = number(event.duration_hours)
        if (duration === undefined) throw new ApiError('INVALID_RESPONSE', 'The event duration is missing.')
        return { id: text(event.event_id), title: text(event.title), type: text(event.type), durationMinutes: duration * 60 }
      })
    },
    getRecommendations(id, request) {
      return consistent(async () => {
        const data = object(await client.request(`/employees/${encodeURIComponent(id)}/recommendations`, { signal: request?.signal }))
        if (number(data.version) === undefined) throw new ApiError('INVALID_RESPONSE', 'The career response is missing its snapshot version.')
        return mapOverview(data, await skillNames(number(data.version), request), id)
      })
    },
    async getHRAnalytics(request) {
      const response = await client.requestEnvelope('/hr/analytics', { signal: request?.signal })
      return mapHRAnalytics(response.data, response.meta?.version)
    },
    async completeActivity(employeeId, eventId) {
      synchronizeSession()
      const action = JSON.stringify([employeeId, eventId])
      let key = completionKeys.get(action)
      if (!key) { key = crypto.randomUUID(); completionKeys.set(action, key) }
      const receipt = object(await client.request(`/activities/${encodeURIComponent(eventId)}/complete`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', 'Idempotency-Key': key }, body: JSON.stringify({ employee_id: employeeId }),
      }), 'completion receipt')
      const activity = object(receipt.activity, 'completed activity')
      if (activity.employee_id !== employeeId || activity.event_id !== eventId || activity.status !== 'completed') {
        throw new ApiError('INVALID_RESPONSE', 'The completion response did not acknowledge the selected activity.')
      }
    },
    ...createHttpDatasetApi(client, () => { completionKeys.clear(); catalogCache.clear() }),
  }
}
