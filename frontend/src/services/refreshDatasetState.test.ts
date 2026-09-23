import { QueryClient, QueryObserver } from '@tanstack/react-query'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { createMockApi } from '../mocks/mockApi'
import { DATASET_REFRESH_TIMEOUT_MS, refreshDatasetState } from './refreshDatasetState'
import { queryKeys } from './queryClient'

afterEach(() => vi.useRealTimers())

describe('dataset refresh boundary', () => {
  it('cancels a pending manual employee snapshot read before refreshing imported data', async () => {
    const client = new QueryClient()
    const api = createMockApi({ latencyMs: 0 })
    let aborted = false
    const pending = client.fetchQuery({ queryKey: ['employee-snapshot-refresh', 'demo-aigerim'], queryFn: ({ signal }) =>
      new Promise<never>((_, reject) => signal.addEventListener('abort', () => {
        aborted = true
        reject(new DOMException('Cancelled', 'AbortError'))
      }, { once: true })), retry: false,
    }).catch(() => undefined)
    await refreshDatasetState(api, client, true)
    await pending
    expect(aborted).toBe(true)
    expect(client.getQueryData(queryKeys.employees)).toEqual(await api.getEmployees())
    client.clear()
  })
  it('refreshes active employee resources and directory/HR snapshots while keeping local state', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const api = createMockApi({ latencyMs: 0 })
    const read = vi.fn(() => api.getEmployee('demo-aigerim'))
    const observer = new QueryObserver(client, { queryKey: queryKeys.employee('demo-aigerim'), queryFn: read })
    const unsubscribe = observer.subscribe(() => {})
    client.setQueryData(queryKeys.completion('demo-aigerim'), { phase: 'success' })
    client.setQueryData(['layout-preference'], 'preserved')
    try {
      await refreshDatasetState(api, client)
      expect(read).toHaveBeenCalledTimes(2)
      expect(client.getQueryData(queryKeys.employees)).toEqual(await api.getEmployees())
      expect(client.getQueryData(queryKeys.hr)).toEqual(await api.getHRAnalytics())
      expect(client.getQueryData(queryKeys.completion('demo-aigerim'))).toEqual({ phase: 'success' })
      expect(client.getQueryData(['layout-preference'])).toBe('preserved')
    } finally { unsubscribe(); client.clear() }
  })

  it('times out stalled reads, aborts them, and leaves the last directory snapshot intact', async () => {
    vi.useFakeTimers()
    const client = new QueryClient()
    const api = createMockApi({ latencyMs: 0, hrLatencyMs: DATASET_REFRESH_TIMEOUT_MS * 2 })
    const previous = [{ id: 'previous' }]
    client.setQueryData(queryKeys.employees, previous)
    const refresh = refreshDatasetState(api, client)
    const assertion = expect(refresh).rejects.toMatchObject({ code: 'TIMEOUT' })
    await vi.advanceTimersByTimeAsync(DATASET_REFRESH_TIMEOUT_MS + 1)
    await assertion
    expect(client.getQueryData(queryKeys.employees)).toEqual(previous)
    expect(client.getQueryState(queryKeys.employees)?.isInvalidated).toBe(true)
    await vi.runAllTimersAsync()
    expect(client.getQueryData(queryKeys.employees)).toEqual(previous)
    client.clear()
  })

  it('clears completion acknowledgements only after a confirmed import is refreshed', async () => {
    const client = new QueryClient()
    const api = createMockApi({ latencyMs: 0 })
    client.setQueryData(queryKeys.completion('demo-aigerim'), { phase: 'success' })
    client.setQueryData(['layout-preference'], 'preserved')
    await refreshDatasetState(api, client, true)
    expect(client.getQueryData(queryKeys.completion('demo-aigerim'))).toBeUndefined()
    expect(client.getQueryData(['layout-preference'])).toBe('preserved')
    client.clear()
  })
})
