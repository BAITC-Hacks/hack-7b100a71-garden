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

  it('never reports successful mutations before they are implemented', async () => {
    const api = createMockApi({ latencyMs: 0 })
    await expect(api.completeActivity('employee', 'event', { idempotencyKey: 'mock-test' })).rejects.toMatchObject({ code: 'UNAVAILABLE' })
    await expect(api.validateDataset({})).rejects.toMatchObject({ code: 'UNAVAILABLE' })
    await expect(api.uploadDataset({}, 'append')).rejects.toMatchObject({ code: 'UNAVAILABLE' })
  })

  it('never silently uses fixtures for real or invalid mode', async () => {
    await expect(createApi('real').getEmployees()).rejects.toMatchObject({ code: 'UNAUTHENTICATED' })
    await expect(createApi('invalid').getEmployees()).rejects.toMatchObject({ code: 'CONFIGURATION' })
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
})
