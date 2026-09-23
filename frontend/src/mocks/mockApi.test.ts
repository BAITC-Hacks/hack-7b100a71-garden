import { describe, expect, it } from 'vitest'
import { createMockApi } from './mockApi'
import { createApi } from '../services/api'

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
    await expect(api.completeActivity('employee', 'event')).rejects.toMatchObject({ code: 'UNAVAILABLE' })
    await expect(api.validateDataset([])).rejects.toMatchObject({ code: 'UNAVAILABLE' })
    await expect(api.uploadDataset([], 'validation')).rejects.toMatchObject({ code: 'UNAVAILABLE' })
  })

  it.each(['real', 'invalid'])('never silently uses fixtures for %s mode', async (mode) => {
    await expect(createApi(mode).getEmployees()).rejects.toMatchObject({ code: 'CONFIGURATION' })
  })
})
