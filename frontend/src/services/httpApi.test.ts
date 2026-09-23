import { afterEach, describe, expect, it, vi } from 'vitest'
import recommendationResponse from '../../test-fixtures/api/e0001-recommendations.json'
import { createHttpClient } from './httpClient'
import { createHttpApi, readAllPages } from './httpApi'
import { mapHRAnalytics, mapOverview } from './httpMappers'
import { getApiToken, setApiToken } from './apiSession'

const json = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })
const baseURL = 'https://career.example.test'
const meta = (version = 1, total = 1, offset = 0) => ({ version, total, offset, limit: 500, as_of_date: '2026-10-01' })
const employee = { employee_id: 'opaque/id', full_name: 'Sample Employee', department: 'Engineering', role: 'Engineer', grade: 'Senior',
  tenure_months: 0, preferred_language: 'kk', career_goal: { target_role: 'Architect', target_grade: 'Lead' }, skills: { skill: 1 } }
afterEach(() => { setApiToken(''); vi.restoreAllMocks() })

describe('central HTTP transport', () => {
  it('uses the configured URL and runtime token without persisting credentials', async () => {
    setApiToken(' demo-token ')
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(json({ data: { ok: true } }))
    expect(await createHttpClient({ baseURL, fetcher }).request('/health')).toEqual({ ok: true })
    expect(fetcher.mock.calls[0][0]).toBe(`${baseURL}/health`)
    expect(new Headers(fetcher.mock.calls[0][1]?.headers).get('Authorization')).toBe('Bearer demo-token')
    setApiToken('')
    expect(getApiToken()).toBe('')
  })

  it.each([
    [401, 'invalid_token', 'AUTHENTICATION'], [403, 'forbidden', 'FORBIDDEN'],
    [409, 'ambiguous_activity', 'CONFLICT'], [422, 'invalid_dataset', 'VALIDATION'],
    [409, 'already_completed', 'ALREADY_COMPLETED'], [503, 'recommendation_unavailable', 'UNAVAILABLE'],
  ])('preserves %s backend error details', async (status, backendCode, code) => {
    const details = [{ location: 'body.employee_id', message: 'Example detail' }]
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(json({ error: { code: backendCode, message: 'Backend message', details } }, status))
    await expect(createHttpClient({ baseURL, fetcher }).request('/example')).rejects.toMatchObject({ code, backendCode, status, message: 'Backend message', details })
  })

  it('does not follow redirects with a Bearer token or accept unknown envelopes', async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(json({ items: [] }))
    await expect(createHttpClient({ baseURL, fetcher }).request('/employees')).rejects.toMatchObject({ code: 'INVALID_RESPONSE' })
    expect(fetcher.mock.calls[0][1]?.redirect).toBe('error')
  })

  it('distinguishes request cancellation from connection failure', async () => {
    const controller = new AbortController()
    controller.abort()
    const fetcher = vi.fn<typeof fetch>().mockRejectedValue(new DOMException('cancelled', 'AbortError'))
    await expect(createHttpClient({ baseURL, fetcher }).request('/employees', { signal: controller.signal })).rejects.toMatchObject({ name: 'AbortError' })
    await expect(createHttpClient({ baseURL, fetcher }).request('/employees')).rejects.toMatchObject({ code: 'NETWORK' })
  })

  it('rejects missing configuration before making a request', async () => {
    const fetcher = vi.fn<typeof fetch>()
    await expect(createHttpClient({ baseURL: '', fetcher }).request('/employees')).rejects.toMatchObject({ code: 'CONFIGURATION' })
    expect(fetcher).not.toHaveBeenCalled()
  })
})

describe('real adapter contracts', () => {
  it('restarts pagination if snapshot versions change without losing or duplicating records', async () => {
    const fetcher = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(json({ data: ['old'], meta: meta(1, 2, 0) }))
      .mockResolvedValueOnce(json({ data: ['mixed'], meta: meta(2, 2, 1) }))
      .mockResolvedValueOnce(json({ data: ['new-first'], meta: meta(2, 2, 0) }))
      .mockResolvedValueOnce(json({ data: ['new-second'], meta: meta(2, 2, 1) }))
    expect(await readAllPages(createHttpClient({ baseURL, fetcher }), '/employees')).toEqual({ data: ['new-first', 'new-second'], version: 2 })
    expect(fetcher.mock.calls.map(([url]) => url)).toEqual([0, 1, 0, 1].map((offset) => `${baseURL}/employees?offset=${offset}&limit=500`))
  })

  it('maps effective profile skills and supplied career goal, preserving opaque IDs and zero tenure', async () => {
    const fetcher = vi.fn<typeof fetch>()
      .mockResolvedValueOnce(json({ data: { employee, effective_skills: { skill: 4 }, role_profile: null }, meta: { version: 7 } }))
      .mockResolvedValueOnce(json({ data: [{ skill_id: 'skill', name: 'System Design' }], meta: meta(7) }))
    const result = await createHttpApi({ baseURL, fetcher }).getEmployee(employee.employee_id)
    expect(result).toMatchObject({ id: 'opaque/id', name: 'Sample Employee', preferredLanguage: 'kk', tenureLabel: '0 months', careerGoal: 'Lead · Architect', snapshotVersion: 7,
      skills: [{ id: 'skill', name: 'System Design', current: 4, scaleMax: 5 }] })
    expect(fetcher.mock.calls[0][0]).toBe(`${baseURL}/employees/opaque%2Fid`)
    expect(employee.skills.skill).toBe(1)
  })

  it('maps the pinned integrated engine response without ranking or calculating business values', () => {
    const source = recommendationResponse.data
    const result = mapOverview(source, new Map([['SK_API_DESIGN', 'API Design']]), source.employee_id)
    expect(result.readiness?.current).toBe(source.career_readiness.current)
    expect(result.trajectory).toBeNull()
    expect(result.recommendations.map((item) => item.eventId)).toEqual(source.recommendations.map((item) => item.event_id))
    const mapped = result.recommendations[0]; const supplied = source.recommendations[0]
    expect(mapped.readinessAfter).toBe(supplied.simulation.readiness_after)
    expect(mapped.skillImpact?.[0]).toMatchObject({ name: 'API Design', gain: supplied.simulation.skill_impact[0].actual_gain,
      required: supplied.simulation.target_skill_impact[0].required, critical: supplied.simulation.target_skill_impact[0].critical })
    expect(mapped.explanation?.text).toBe(supplied.explanation.text)
    expect(mapped.explanation?.language).toBe('kk')
    expect(mapped.explanation?.factors?.[0]).toMatchObject(supplied.factors.critical_skill_impact)
    expect(mapped.supportingEvidence?.find((item) => item.id === 'simulation')?.values).toEqual(supplied.simulation)
    expect(result.skillsEstimated).toBe(source.career_state.skills_reconstruction.is_estimate)
    expect(result.warnings?.map((item) => item.message)).toEqual(source.career_state.skills_reconstruction.warnings.map((item) => item.message))
  })

  it('retains structured evidence when optional AI text is absent', () => {
    const source = structuredClone(recommendationResponse.data)
    const item = source.recommendations[0] as typeof source.recommendations[0] & { explanation?: unknown }
    Reflect.deleteProperty(item, 'explanation')
    const mapped = mapOverview(source, new Map(), source.employee_id)
    expect(mapped.recommendations[0].explanation?.text).toBeUndefined()
    expect(mapped.recommendations[0].explanation?.factors).toHaveLength(Object.keys(item.factors).length)
    expect(mapped.recommendations[0].supportingEvidence).toHaveLength(4)
  })

  it('retains partial HR coverage and does not fabricate rates or development counts', () => {
    const result = mapHRAnalytics({ employee_count: 23, gap_basis: 'effective_skills_against_current_role_and_grade',
      employees_without_next_step: { available: true, count: 2, evaluated_count: 3, pending_count: 20, complete: false },
      activity_participation: { completed: 7, declined: 0 }, participation_summary: { total_records: 9, participating_employees: 4 },
      common_skill_gaps: [{ skill_id: 'a', skill_name: 'Skill A', employee_count: 2 }, { skill_id: 'b', skill_name: 'Skill B', employee_count: 6 }] }, 4)
    expect(result).toMatchObject({ totalEmployees: 23, withoutNextStep: 2, nextStepCoverage: { complete: false, pendingCount: 20 }, participatingEmployees: 4 })
    expect(result.participationRate).toBeUndefined()
    expect(result.employeesInDevelopment).toBeUndefined()
    expect(result.activityParticipation).toBeUndefined()
    expect(result.commonSkillGaps?.map((item) => item.employeeCount)).toEqual([2, 6])
    expect(result.activityStatuses).toEqual([{ status: 'completed', count: 7 }, { status: 'declined', count: 0 }])
  })

  it('reuses the completion idempotency key after a lost response and sends only the permitted identity field', async () => {
    const fetcher = vi.fn<typeof fetch>().mockRejectedValueOnce(new TypeError('Network lost'))
      .mockResolvedValueOnce(json({ data: { activity: { employee_id: 'person', event_id: 'event', status: 'completed' }, replayed: true, version: 2 } }))
    const api = createHttpApi({ baseURL, fetcher })
    await expect(api.completeActivity('person', 'event')).rejects.toMatchObject({ code: 'NETWORK' })
    await api.completeActivity('person', 'event')
    const requests = fetcher.mock.calls.map(([, init]) => init!)
    expect(new Headers(requests[0].headers).get('Idempotency-Key')).toBe(new Headers(requests[1].headers).get('Idempotency-Key'))
    expect(JSON.parse(requests[1].body as string)).toEqual({ employee_id: 'person' })
    expect(fetcher).toHaveBeenCalledTimes(2)
  })
})
