import { describe, expect, it } from 'vitest'
import { createMockApi } from './mockApi'
import { hrAnalytics, partialHRAnalytics } from './hrFixtures'
import { scenarioOptions } from './scenarios'
import { createApi } from '../services/api'

describe('HR analytics adapter boundary', () => {
  it('returns isolated fixed aggregates, independent of employee completion', async () => {
    const api = createMockApi({ latencyMs: 0, completionLatencyMs: 0 })
    const response = await api.getHRAnalytics()
    response.commonSkillGaps![0].employeeCount = 999
    response.activityStatuses!.pop()
    await api.completeActivity('demo-aigerim', 'demo-system-design')
    expect(await api.getHRAnalytics()).toEqual(hrAnalytics)
  })

  it('preserves null and omitted metrics without supplying zero defaults', async () => {
    const api = createMockApi({ latencyMs: 0, hrResponse: partialHRAnalytics })
    const result = await api.getHRAnalytics()
    expect(result).toEqual(partialHRAnalytics)
    expect(result.employeesInDevelopment).toBeUndefined()
    expect(result.participationRate).toBeNull()
    expect(result.withoutNextStep).toBe(0)
  })

  it('isolates recoverable HR failure from the employee flow', async () => {
    const api = createMockApi({ ...scenarioOptions('hr-retry'), latencyMs: 0 })
    expect((await api.getEmployees()).length).toBeGreaterThan(0)
    await expect(api.getHRAnalytics()).rejects.toMatchObject({ code: 'NETWORK' })
    expect((await api.getEmployee('demo-aigerim')).name).toBe('Aigerim Sapar')
    expect(await api.getHRAnalytics()).toEqual(hrAnalytics)
  })

  it('honors cancellation for HR requests', async () => {
    const controller = new AbortController()
    const request = createMockApi({ hrLatencyMs: 1000 }).getHRAnalytics({ signal: controller.signal })
    controller.abort()
    await expect(request).rejects.toMatchObject({ name: 'AbortError' })
  })

  it('does not fall back to mock HR data in real mode', async () => {
    await expect(createApi('real').getHRAnalytics()).rejects.toMatchObject({ code: 'CONFIGURATION' })
  })
})
