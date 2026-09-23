import { QueryClient } from '@tanstack/react-query'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createMockApi } from '../mocks/mockApi'
import { queryKeys } from './queryClient'
import { REFRESH_TIMEOUT_MS, refreshEmployeeState } from './refreshEmployeeState'
import type { CareerOverview } from '../types/domain'

afterEach(() => vi.useRealTimers())
describe('refresh consistency', () => {
  it('rejects mismatched or incomplete responses without publishing partial state', async () => {
    const client = new QueryClient()
    const api = createMockApi({ latencyMs: 0, completionLatencyMs: 0 })
    const employee = await api.getEmployee('demo-aigerim')
    const overview = await api.getRecommendations('demo-aigerim')
    client.setQueryData(queryKeys.employee(employee.id), employee)
    client.setQueryData(queryKeys.recommendations(employee.id), overview)
    await api.completeActivity(employee.id, 'demo-system-design')
    vi.spyOn(api, 'getRecommendations').mockResolvedValue({ ...overview, employeeId: 'different' })
    await expect(refreshEmployeeState(api, client, employee.id)).rejects.toMatchObject({ code: 'INVALID_RESPONSE' })
    expect(client.getQueryData(queryKeys.employee(employee.id))).toEqual(employee)
    vi.mocked(api.getRecommendations).mockResolvedValue({ employeeId: employee.id } as CareerOverview)
    await expect(refreshEmployeeState(api, client, employee.id)).rejects.toMatchObject({ code: 'INVALID_RESPONSE' })
    expect(client.getQueryData(queryKeys.recommendations(employee.id))).toEqual(overview)
    client.clear()
  })

  it('bounds a refresh even if a transport fails to honor cancellation', async () => {
    vi.useFakeTimers()
    const client = new QueryClient()
    const api = createMockApi({ latencyMs: 0 })
    const never = new Promise<never>(() => {})
    vi.spyOn(api, 'getEmployee').mockReturnValue(never)
    vi.spyOn(api, 'getRecommendations').mockReturnValue(never)
    const result = refreshEmployeeState(api, client, 'demo-aigerim')
    const assertion = expect(result).rejects.toMatchObject({ code: 'TIMEOUT' })
    await vi.advanceTimersByTimeAsync(REFRESH_TIMEOUT_MS + 1)
    await assertion
    expect(client.getQueryData(queryKeys.employee('demo-aigerim'))).toBeUndefined()
    client.clear()
  })
})
