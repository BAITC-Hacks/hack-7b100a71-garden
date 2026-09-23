import { ApiError, type CareerApi, type RequestOptions } from '../types/api'
import type { CareerOverview } from '../types/domain'
import { activities, careerOverviews, employeeHistories, employees, hrAnalytics } from './fixtures'

export type MockOptions = {
  latencyMs?: number
  failReads?: boolean
  emptyEmployees?: boolean
  failFirstRead?: boolean
  failFirstOverview?: boolean
  overviewLatencyMs?: number
  overviewPatch?: Partial<Pick<CareerOverview, 'trajectory' | 'readiness' | 'skillGaps'>>
}

export function createMockApi({ latencyMs = 240, failReads = false, emptyEmployees = false, failFirstRead = false, failFirstOverview = false, overviewLatencyMs = latencyMs, overviewPatch = {} }: MockOptions = {}): CareerApi {
  let pendingReadFailure = failFirstRead
  let pendingOverviewFailure = failFirstOverview
  async function read<T>(resolve: () => T, options?: RequestOptions, delay = latencyMs): Promise<T> {
    const signal = options?.signal
    signal?.throwIfAborted()
    await new Promise<void>((done, reject) => {
      const onAbort = () => {
        clearTimeout(timer)
        signal?.removeEventListener('abort', onAbort)
        reject(signal?.reason ?? new DOMException('Request aborted', 'AbortError'))
      }
      const timer = setTimeout(() => {
        signal?.removeEventListener('abort', onAbort)
        done()
      }, delay)
      signal?.addEventListener('abort', onAbort, { once: true })
    })
    signal?.throwIfAborted()
    if (failReads || pendingReadFailure) {
      pendingReadFailure = false
      throw new ApiError('NETWORK', 'The demo request could not be completed.')
    }
    return structuredClone(resolve())
  }

  function requireEmployee(id: string) {
    const employee = emptyEmployees ? undefined : employees.find((item) => item.id === id)
    if (!employee) throw new ApiError('NOT_FOUND', 'This employee could not be found.')
    return employee
  }

  const unavailable = () => Promise.reject(new ApiError('UNAVAILABLE', 'This action is not available yet.'))

  return {
    getEmployees: (options) => read(() => emptyEmployees ? [] : employees, options),
    getEmployee: (id, options) => read(() => requireEmployee(id), options),
    getEmployeeHistory: (id, options) => read(() => { requireEmployee(id); return employeeHistories[id] }, options),
    getEvents: (options) => read(() => activities, options),
    getRecommendations: (id, options) => read(() => {
      requireEmployee(id)
      if (pendingOverviewFailure) {
        pendingOverviewFailure = false
        throw new ApiError('NETWORK', 'The career assessment could not be loaded.')
      }
      return { ...careerOverviews[id], ...overviewPatch }
    }, options, overviewLatencyMs),
    getHRAnalytics: (options) => read(() => hrAnalytics, options),
    // Mutation contracts are reserved for later checkpoints. Never report a fake success.
    completeActivity: unavailable,
    validateDataset: unavailable,
    uploadDataset: unavailable,
  }
}
