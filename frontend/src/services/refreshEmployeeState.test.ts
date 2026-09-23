import { QueryClient } from '@tanstack/react-query'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createMockApi } from '../mocks/mockApi'
import { queryKeys } from './queryClient'
import { REFRESH_TIMEOUT_MS, refreshEmployeeState } from './refreshEmployeeState'
import type { CareerOverview, Employee } from '../types/domain'

afterEach(() => vi.useRealTimers())
describe('refresh consistency', () => {
  it('does not publish a late manual refresh after its caller is cancelled', async () => {
    const client = new QueryClient()
    const api = createMockApi({ latencyMs: 0 })
    const employee = await api.getEmployee('demo-aigerim')
    const overview = await api.getRecommendations(employee.id)
    let resolveEmployee!: (value: Employee) => void
    let resolveOverview!: (value: CareerOverview) => void
    vi.spyOn(api, 'getEmployee').mockReturnValue(new Promise<Employee>((resolve) => { resolveEmployee = resolve }))
    vi.spyOn(api, 'getRecommendations').mockReturnValue(new Promise<CareerOverview>((resolve) => { resolveOverview = resolve }))
    const controller = new AbortController()
    const pending = refreshEmployeeState(api, client, employee.id, controller.signal)
    const rejected = expect(pending).rejects.toMatchObject({ name: 'AbortError' })
    await vi.waitFor(() => expect(api.getEmployee).toHaveBeenCalledTimes(1))
    controller.abort()
    client.clear()
    resolveEmployee(employee)
    resolveOverview(overview)
    await rejected
    expect(client.getQueryData(queryKeys.employee(employee.id))).toBeUndefined()
    expect(client.getQueryData(queryKeys.recommendations(employee.id))).toBeUndefined()
  })
  it('retains the previous snapshot when dataset versions disagree', async () => {
    const client = new QueryClient()
    const api = createMockApi({ latencyMs: 0 })
    const employee = await api.getEmployee('demo-aigerim')
    const overview = await api.getRecommendations(employee.id)
    client.setQueryData(queryKeys.employee(employee.id), employee)
    client.setQueryData(queryKeys.recommendations(employee.id), overview)
    vi.spyOn(api, 'getEmployee').mockResolvedValue({ ...employee, snapshotVersion: 1 })
    vi.spyOn(api, 'getRecommendations').mockResolvedValue({ ...overview, snapshotVersion: 2 })
    await expect(refreshEmployeeState(api, client, employee.id)).rejects.toMatchObject({ code: 'CONFLICT' })
    expect(client.getQueryData(queryKeys.employee(employee.id))).toEqual(employee)
    expect(client.getQueryData(queryKeys.recommendations(employee.id))).toEqual(overview)
    client.clear()
  })
  it('publishes supplied partial skill evidence without inventing optional fields', async () => {
    const client = new QueryClient()
    const api = createMockApi({ latencyMs: 0, overviewPatch: { skillGaps: [{ id: 'partial', name: 'Partial skill', current: 0, scaleMax: 5 }] } })
    await refreshEmployeeState(api, client, 'demo-aigerim')
    const result = client.getQueryData<CareerOverview>(queryKeys.recommendations('demo-aigerim'))
    expect(result?.skillGaps).toEqual([{ id: 'partial', name: 'Partial skill', current: 0, scaleMax: 5 }])
    expect(result?.skillGaps[0].gap).toBeUndefined()
    expect(result?.skillGaps[0].critical).toBeUndefined()
    client.clear()
  })
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
