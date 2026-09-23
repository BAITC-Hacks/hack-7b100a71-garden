import type { QueryClient } from '@tanstack/react-query'
import { ApiError, type CareerApi } from '../types/api'
import { queryKeys } from './queryClient'

export const DATASET_REFRESH_TIMEOUT_MS = 10_000
const affected = new Set(['employees', 'employee', 'recommendations', 'history', 'events', 'hr-analytics'])

// Invalidate only dataset-backed resources. Local operation state and unrelated
// queries survive. The API owns every returned employee and aggregate value.
export async function refreshDatasetState(api: CareerApi, client: QueryClient) {
  const filter = { predicate: (query: { queryKey: readonly unknown[] }) => affected.has(String(query.queryKey[0])) }
  await client.cancelQueries(filter)
  await client.invalidateQueries({ ...filter, refetchType: 'none' })
  const controller = new AbortController()
  let timer: ReturnType<typeof setTimeout> | undefined
  try {
    const [employees, analytics] = await Promise.race([
      Promise.all([
        api.getEmployees({ signal: controller.signal }), api.getHRAnalytics({ signal: controller.signal }),
        client.refetchQueries({ type: 'active', predicate: (query) => filter.predicate(query) && query.queryKey[0] !== 'employees' && query.queryKey[0] !== 'hr-analytics' }, { throwOnError: true }),
      ]),
      new Promise<never>((_, reject) => { timer = setTimeout(() => {
        const error = new ApiError('TIMEOUT', 'The application data could not be refreshed in time.')
        controller.abort(error)
        void client.cancelQueries(filter)
        reject(error)
      }, DATASET_REFRESH_TIMEOUT_MS) }),
    ])
    if (!Array.isArray(employees) || !analytics || typeof analytics !== 'object') throw new ApiError('INVALID_RESPONSE', 'The refreshed application data is incomplete.')
    client.setQueryData(queryKeys.employees, employees)
    client.setQueryData(queryKeys.hr, analytics)
  } finally {
    clearTimeout(timer)
    controller.abort()
  }
}
