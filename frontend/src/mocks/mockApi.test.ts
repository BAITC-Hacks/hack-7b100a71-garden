import { describe, expect, it } from 'vitest'
import { createMockApi } from './mockApi'
import { createApi } from '../services/api'
import { scenarioOptions } from './scenarios'

describe('API adapter boundary', () => {
  it('keeps returned employee records isolated between requests', async () => {
    const api = createMockApi({ latencyMs: 0 })
    const list = await api.getEmployees()
    const original = list[0].name
    list[0].name = 'Changed by a consumer'
    expect((await api.getEmployee(list[0].id)).name).toBe(original)
  })

  it('rejects unknown employee IDs across all employee resources', async () => {
    const api = createMockApi({ latencyMs: 0 })
    for (const request of [api.getEmployee, api.getEmployeeHistory, api.getRecommendations]) {
      await expect(request('not-an-employee')).rejects.toMatchObject({ code: 'NOT_FOUND' })
    }
  })

  it('preserves supplied transition targets and missing next-grade states', async () => {
    const api = createMockApi({ latencyMs: 0 })
    const list = await api.getEmployees()
    const overviews = await Promise.all(list.map((employee) => api.getRecommendations(employee.id)))
    const transition = overviews.find((overview) => overview.trajectory?.kind === 'transition')!
    expect(transition.trajectory?.positions[0].grade).toBe(transition.target?.grade)
    expect(transition.trajectory?.positions[0].role).not.toBe(transition.target?.role)
    const lead = list.find((employee) => employee.grade === 'Lead')!
    expect(await api.getRecommendations(lead.id)).toMatchObject({ target: null, readiness: null, recommendations: [] })
  })

  it('supports an empty employee source and explicit API failure', async () => {
    expect(await createMockApi({ latencyMs: 0, emptyEmployees: true }).getEmployees()).toEqual([])
    await expect(createMockApi({ latencyMs: 0, failReads: true }).getEmployees()).rejects.toMatchObject({ code: 'NETWORK' })
  })

  it('honors cancellation without returning stale data', async () => {
    const controller = new AbortController()
    const request = createMockApi({ latencyMs: 1000 }).getEmployees({ signal: controller.signal })
    controller.abort()
    await expect(request).rejects.toMatchObject({ name: 'AbortError' })
  })

  it('requires an issued validation identifier before the mock import acknowledgement', async () => {
    const api = createMockApi({ latencyMs: 0, datasetLatencyMs: 0 })
    await expect(api.uploadDataset([], 'validation')).rejects.toMatchObject({ code: 'INVALID_RESPONSE' })
  })

  it.each(['real', 'invalid'])('never silently uses fixtures for %s mode', async (mode) => {
    await expect(createApi(mode).getEmployees()).rejects.toMatchObject({ code: 'CONFIGURATION' })
    await expect(createApi(mode).completeActivity('demo-aigerim', 'demo-system-design')).rejects.toMatchObject({ code: 'CONFIGURATION' })
  })

  it('can retry an isolated career failure without losing employee identity', async () => {
    const api = createMockApi({ latencyMs: 0, failFirstOverview: true })
    const [employee] = await api.getEmployees()
    await expect(api.getRecommendations(employee.id)).rejects.toMatchObject({ code: 'NETWORK' })
    expect((await api.getEmployee(employee.id)).id).toBe(employee.id)
    expect((await api.getRecommendations(employee.id)).employeeId).toBe(employee.id)
  })

  it('recovers from the first-read failure scenario on retry', async () => {
    const api = createMockApi({ latencyMs: 0, failFirstRead: true })
    await expect(api.getEmployees()).rejects.toMatchObject({ code: 'NETWORK' })
    expect((await api.getEmployees()).length).toBeGreaterThan(0)
  })

  it('isolates missing-data scenarios and preserves returned trajectory snapshots', async () => {
    const normal = createMockApi({ latencyMs: 0 })
    const [employee] = await normal.getEmployees()
    const missing = createMockApi({ ...scenarioOptions('missing-trajectory'), latencyMs: 0 })
    expect((await missing.getRecommendations(employee.id)).trajectory).toBeNull()
    const overview = await normal.getRecommendations(employee.id)
    const positions = overview.trajectory!.positions.length
    overview.trajectory!.positions.pop()
    expect((await normal.getRecommendations(employee.id)).trajectory!.positions).toHaveLength(positions)
  })

  it('preserves scenario order and isolates recommendation evidence between responses', async () => {
    const api = createMockApi({ ...scenarioOptions('recommendations-order'), latencyMs: 0 })
    const overview = await api.getRecommendations('demo-aigerim')
    expect(overview.recommendations.map((item) => item.eventId)).toEqual(['demo-communication', 'demo-system-design', 'demo-api-design'])
    overview.recommendations[1].skillImpact![0].after = 999
    expect((await api.getRecommendations('demo-aigerim')).recommendations[1].skillImpact![0].after).toBe(3)
    const normal = await createMockApi({ latencyMs: 0 }).getRecommendations('demo-aigerim')
    expect(normal.recommendations[0].eventId).toBe('demo-system-design')
  })

  it('returns fixed after-state and history once, and rejects duplicate completion', async () => {
    const api = createMockApi({ latencyMs: 0, completionLatencyMs: 0 })
    await api.completeActivity('demo-aigerim', 'demo-system-design')
    expect((await api.getEmployee('demo-aigerim')).skills[0].current).toBe(3)
    const overview = await api.getRecommendations('demo-aigerim')
    expect(overview.readiness?.current).toBe(0.79)
    expect(overview.skillGaps[0].gap).toBe(1)
    expect(overview.recommendations.map((item) => item.eventId)).toEqual(['demo-api-design', 'demo-communication'])
    await expect(api.completeActivity('demo-aigerim', 'demo-system-design')).rejects.toMatchObject({ code: 'ALREADY_COMPLETED' })
    expect(await api.getEmployeeHistory('demo-aigerim')).toHaveLength(1)
    expect((await createMockApi({ latencyMs: 0 }).getRecommendations('demo-aigerim')).readiness?.current).toBe(0.67)
  })

  it('supports a different activity order through explicit snapshots', async () => {
    const api = createMockApi({ latencyMs: 0, completionLatencyMs: 0 })
    await api.completeActivity('demo-aigerim', 'demo-api-design')
    expect((await api.getEmployee('demo-aigerim')).skills.map((skill) => skill.current)).toEqual([2, 4, 3])
    await api.completeActivity('demo-aigerim', 'demo-communication')
    expect((await api.getRecommendations('demo-aigerim')).readiness?.current).toBe(0.78)
    await api.completeActivity('demo-aigerim', 'demo-system-design')
    expect((await api.getRecommendations('demo-aigerim')).recommendations).toEqual([])
    expect(await api.getEmployeeHistory('demo-aigerim')).toHaveLength(3)
  })

  it('rejects missing employees and unavailable recommendations without changing the assessment', async () => {
    const api = createMockApi({ latencyMs: 0, completionLatencyMs: 0 })
    await expect(api.completeActivity('unknown', 'demo-system-design')).rejects.toMatchObject({ code: 'NOT_FOUND' })
    await expect(api.completeActivity('demo-aigerim', 'unknown')).rejects.toMatchObject({ code: 'RECOMMENDATION_UNAVAILABLE' })
    expect((await api.getRecommendations('demo-aigerim')).readiness?.current).toBe(0.67)
  })
})
