import { describe, expect, it, vi } from 'vitest'
import audit from '../../../docs/integration-phase1-results.json'
import { createHttpApi, mapCareer } from './httpApi'
import type { EmployeeDetailDTO, Envelope, EventDTO, HRAnalyticsDTO, RecommendationResultDTO, RoleProfileDTO, SkillDTO } from '../types/transport'
import type { Session } from './session'

const profile = audit.e0001.before_profile as unknown as Envelope<EmployeeDetailDTO>
const result = audit.e0001.before_recommendations as unknown as Envelope<RecommendationResultDTO>
const skillRows: SkillDTO[] = Object.keys(profile.data.effective_skills).map(id => ({ skill_id: id, name: `Name ${id}`, category: 'technical', type: 'hard', description: '' }))
const eventRows: EventDTO[] = result.data.recommendations.map(row => ({
  event_id: row.event_id, title: row.title, type: 'workshop', format: 'online', duration_hours: 1.5,
  description: '', mandatory: false, target_roles: [], target_grades: [], develops_skills: [], prerequisites: {}, upcoming_sessions: [],
}))
const target: RoleProfileDTO = { role: result.data.target!.role, grade: result.data.target!.grade,
  required_skills: { SK_API_DESIGN: 3, SK_PYTHON: 3 }, critical_skills: ['SK_API_DESIGN'] }
const session: Session = { role: 'employee', employeeId: 'E0001', token: 'test-opaque-token' }
const page = <T,>(data: T[], version = 1, total = data.length, offset = 0) => ({ data, meta: { version, as_of_date: '2026-10-01', total, offset, limit: 500 } })
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

function setup(identity: Session | null = session) {
  const fetcher = vi.fn<typeof fetch>(async input => {
    const path = new URL(String(input)).pathname
    const routes: Record<string, unknown> = {
      '/employees/E0001': profile, '/employees/E0001/recommendations': result,
      '/skills': page(skillRows), '/events': page(eventRows), '/role-profiles': page([target]),
      '/employees': page([profile.data.employee]), '/employees/E0001/history': page([]),
    }
    return response(routes[path] ?? { data: null })
  })
  const api = createHttpApi({ baseUrl: 'http://backend.test/', getIdentity: () => identity, fetch: fetcher })
  return { api, fetcher }
}

describe('real HTTP adapter', () => {
  it('maps employee identity and EFFECTIVE skills, preserving assessment baseline separately', async () => {
    const { api, fetcher } = setup()
    const employee = await api.getEmployee('E0001')
    expect(employee.id).toBe(profile.data.employee.employee_id)
    expect(employee.name).toBe(profile.data.employee.full_name)
    expect(employee.preferredLanguage).toBe('kk')
    expect(employee.skills.find(skill => skill.id === 'SK_APP_SECURITY')?.current).toBe(1)
    expect(employee.assessmentSkills?.SK_APP_SECURITY).toBe(0)
    expect(employee.version).toBe(1)
    expect(fetcher.mock.calls.map(([url]) => String(url))).not.toContain('http://backend.test/employees')
    for (const [, init] of fetcher.mock.calls) expect(new Headers(init?.headers).get('Authorization')).toBe('Bearer test-opaque-token')
  })

  it('preserves server order, rank, scores, full evidence and localized explanations', async () => {
    const { api } = setup()
    const mapped = await api.getRecommendations('E0001')
    expect(mapped.recommendations.map(item => [item.eventId, item.rank, item.score])).toEqual(result.data.recommendations.map(item => [item.event_id, item.rank, item.score]))
    expect(mapped.raw).toEqual(result.data)
    expect(mapped.recommendations[0].raw).toEqual(result.data.recommendations[0])
    expect(mapped.recommendations[0].explanation.text).toBe(result.data.recommendations[0].explanation?.text)
    expect(mapped.recommendations[0].durationMinutes).toBe(90)
    expect(mapped.readiness?.current).toBe(0.5897435897435898)
    expect(mapped.trajectory?.positions.map(item => item.state)).toEqual(['current', 'target'])
    expect(mapped.targetRequirements?.find(skill => skill.id === 'SK_PYTHON')).toMatchObject({ current: 3, required: 3, gap: 0 })
  })

  it.each(['kk', 'ru', 'en'] as const)('passes through %s explanation text without generating claims', language => {
    const input = structuredClone(result.data)
    input.recommendations[0].explanation!.language = language
    input.recommendations[0].explanation!.text = `${language}: supplied backend explanation`
    const mapped = mapCareer(input, profile.data.employee, skillRows, eventRows, [target])
    expect(mapped.recommendations[0].explanation).toMatchObject({ language, text: `${language}: supplied backend explanation` })
    expect(mapped.recommendations[0].score).toBe(input.recommendations[0].score)
  })

  it.each(['no_next_grade', 'target_satisfied', 'no_eligible_recommendations'] as const)('keeps normal HTTP 200 status %s as a result', async status => {
    const { api, fetcher } = setup()
    const raw = structuredClone(result.data)
    Object.assign(raw, { status, recommendations: [], recommendation_count: 0 })
    if (status === 'no_next_grade') Object.assign(raw, { target: null, career_readiness: null })
    const original = fetcher.getMockImplementation()!
    fetcher.mockImplementation((input, init) => String(input).endsWith('/recommendations') ? Promise.resolve(response({ data: raw })) : original(input, init))
    const mapped = await api.getRecommendations('E0001')
    expect(mapped.status).toBe(status)
    expect(mapped.recommendations).toEqual([])
    if (status === 'no_next_grade') expect(mapped.trajectory).toBeNull()
  })

  it('paginates HR directory without exposing assessment skills as current', async () => {
    const { api, fetcher } = setup({ role: 'hr', token: 'test-hr' })
    fetcher.mockImplementation(async input => {
      const offset = Number(new URL(String(input)).searchParams.get('offset'))
      return response(page([{ ...profile.data.employee, employee_id: `unseen-${offset}` }], 1, 2, offset))
    })
    const rows = await api.getEmployees()
    expect(rows.map(row => row.id)).toEqual(['unseen-0', 'unseen-1'])
    expect(rows.every(row => row.skills.length === 0)).toBe(true)
    expect(String(fetcher.mock.calls[1][0])).toContain('offset=1')
  })

  it('rejects mixed snapshot pages instead of joining inconsistent employee data', async () => {
    const { api, fetcher } = setup({ role: 'hr', token: 'test-hr' })
    fetcher.mockResolvedValueOnce(response(page([profile.data.employee], 1, 2, 0)))
      .mockResolvedValueOnce(response(page([profile.data.employee], 2, 2, 1)))
    await expect(api.getEmployees()).rejects.toMatchObject({ status: 409, backendCode: 'dataset_changed' })
  })

  it('rejects mixed profile/catalog versions', async () => {
    const { api, fetcher } = setup()
    fetcher.mockResolvedValueOnce(response(profile)).mockResolvedValueOnce(response(page(skillRows, 2)))
    await expect(api.getEmployee('E0001')).rejects.toMatchObject({ backendCode: 'dataset_changed' })
  })

  it('never sends employee directory, HR, import or another employee requests for employee identity', async () => {
    const { api, fetcher } = setup()
    for (const attempt of [() => api.getEmployees(), () => api.getHRAnalytics(), () => api.validateDataset({}), () => api.uploadDataset({}), () => api.getEmployee('someone-else')]) {
      await expect(attempt()).rejects.toMatchObject({ code: 'FORBIDDEN' })
    }
    expect(fetcher).not.toHaveBeenCalled()
  })

  it.each([[401, 'UNAUTHENTICATED'], [403, 'FORBIDDEN'], [404, 'NOT_FOUND'], [422, 'BACKEND'], [503, 'UNAVAILABLE']] as const)('preserves HTTP %s backend code and structured details', async (status, code) => {
    const { api, fetcher } = setup()
    fetcher.mockResolvedValue(response({ error: { code: 'provided_code', message: 'Provided message', details: [{ field: 'example' }] } }, status))
    await expect(api.getEvents()).rejects.toMatchObject({ code, status, backendCode: 'provided_code', details: [{ field: 'example' }], message: 'Provided message' })
  })

  it('handles unavailable backend, missing envelope, and configuration explicitly', async () => {
    const { api, fetcher } = setup()
    fetcher.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    await expect(api.getEvents()).rejects.toMatchObject({ code: 'NETWORK' })
    fetcher.mockResolvedValueOnce(response({ unexpected: [] }))
    await expect(api.getEvents()).rejects.toMatchObject({ code: 'INVALID_RESPONSE' })
    await expect(createHttpApi({ baseUrl: 'bad-url', fetch: fetcher }).getEvents()).rejects.toMatchObject({ code: 'CONFIGURATION' })
    await expect(setup(null).api.getEvents()).rejects.toMatchObject({ code: 'UNAUTHENTICATED' })
  })

  it('honors cancellation before network and after a pending response', async () => {
    const { api, fetcher } = setup()
    const controller = new AbortController()
    controller.abort()
    await expect(api.getEvents({ signal: controller.signal })).rejects.toMatchObject({ name: 'AbortError' })
    expect(fetcher).not.toHaveBeenCalled()
    const pending = new AbortController()
    fetcher.mockImplementationOnce(async () => { pending.abort(); return response(page(eventRows)) })
    await expect(api.getEvents({ signal: pending.signal })).rejects.toMatchObject({ name: 'AbortError' })
  })

  it('sends exact completion body and reuses caller idempotency key on retry', async () => {
    const { api, fetcher } = setup()
    const receipt = audit.e0001.completion
    fetcher.mockRejectedValueOnce(new TypeError('Lost connection')).mockResolvedValueOnce(response(receipt))
    const options = { idempotencyKey: 'one-action-key' }
    await expect(api.completeActivity('E0001', 'EV_005', options)).rejects.toMatchObject({ code: 'NETWORK' })
    expect(await api.completeActivity('E0001', 'EV_005', options)).toEqual(receipt.data)
    for (const [url, init] of fetcher.mock.calls) {
      expect(url).toBe('http://backend.test/activities/EV_005/complete')
      expect(new Headers(init?.headers).get('Idempotency-Key')).toBe('one-action-key')
      expect(JSON.parse(String(init?.body))).toEqual({ employee_id: 'E0001' })
    }
  })

  it('preserves cancellation while the response body is being read', async () => {
    const { api, fetcher } = setup()
    const controller = new AbortController()
    const pending = response({})
    vi.spyOn(pending, 'json').mockImplementation(async () => {
      controller.abort()
      throw new DOMException('Body aborted', 'AbortError')
    })
    fetcher.mockResolvedValueOnce(pending)
    await expect(api.getEvents({ signal: controller.signal })).rejects.toMatchObject({ name: 'AbortError' })
  })

  it('discards a response when identity changes during JSON body reading', async () => {
    let active: Session | null = session
    const pending = response({})
    vi.spyOn(pending, 'json').mockImplementation(async () => { active = null; return page(eventRows) })
    const api = createHttpApi({ baseUrl: 'http://backend.test', getIdentity: () => active, fetch: vi.fn<typeof fetch>().mockResolvedValue(pending) })
    await expect(api.getEvents()).rejects.toMatchObject({ code: 'UNAUTHENTICATED' })
  })

  it('keeps partial HR coverage and gap basis without manufacturing KPIs', async () => {
    const { api, fetcher } = setup({ role: 'hr', token: 'test-hr' })
    const counts = { completed: 0, in_progress: 0, dropped: 0, no_show: 0, declined: 0, overdue: 0 }
    const data: HRAnalyticsDTO = { employee_count: 200, gap_basis: 'effective_skills_against_current_role_and_grade',
      employees_without_next_step: { available: true, count: null, evaluated_count: 0, pending_count: 200, complete: false },
      common_skill_gaps: [], activity_participation: counts,
      participation_summary: { total_records: 0, participating_employees: 0, voluntary: counts, mandatory: counts } }
    fetcher.mockResolvedValueOnce(response({ data, meta: { version: 7, as_of_date: '2026-10-01' } }))
    expect(await api.getHRAnalytics()).toEqual({ ...data, version: 7, asOf: '2026-10-01' })
  })

  it('uses real multipart names and mode for validation/upload without validationId', async () => {
    const { api, fetcher } = setup({ role: 'hr', token: 'test-hr' })
    const files = { employees_file: new File(['{}'], 'jury-people.json', { type: 'application/json' }), activity_history_file: new File(['record_id'], 'jury-history.csv') }
    const validation = { valid: true, counts: { employees: 1 }, errors: [], mode: 'append', version: 4 }
    const uploaded = { uploaded: true, counts: { employees: 1 }, mode: 'append', version: 5 }
    fetcher.mockResolvedValueOnce(response({ data: validation })).mockResolvedValueOnce(response({ data: uploaded }))
    expect(await api.validateDataset(files, 'append')).toEqual(validation)
    expect(await api.uploadDataset(files, 'append')).toEqual(uploaded)
    for (const [url, init] of fetcher.mock.calls) {
      expect(String(url)).toContain('?mode=append')
      expect(new Headers(init?.headers).has('Content-Type')).toBe(false)
      const body = init?.body as FormData
      expect([...body.keys()]).toEqual(['employees_file', 'activity_history_file'])
      expect((body.get('employees_file') as File).name).toBe('jury-people.json')
    }
  })
})
