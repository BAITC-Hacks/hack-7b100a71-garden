import type { QueryClient } from '@tanstack/react-query'
import { ApiError, type CareerApi } from '../types/api'
import type { CareerOverview, Employee } from '../types/domain'
import { queryKeys } from './queryClient'

export const REFRESH_TIMEOUT_MS = 10_000

function validateSnapshot(employee: Employee, overview: CareerOverview, id: string) {
  if (!employee || employee.id !== id || typeof employee.name !== 'string' || typeof employee.role !== 'string' ||
    typeof employee.grade !== 'string' || !Array.isArray(employee.skills) || employee.skills.some((skill) => !skill || typeof skill.name !== 'string') ||
    !overview || overview.employeeId !== id ||
    !Array.isArray(overview.skillGaps) || !Array.isArray(overview.recommendations) ||
    overview.skillGaps.some((skill) => !skill || typeof skill.id !== 'string' || typeof skill.name !== 'string' ||
      typeof skill.current !== 'number' || typeof skill.required !== 'number' || typeof skill.gap !== 'number' || typeof skill.critical !== 'boolean') ||
    overview.recommendations.some((item) => !item || typeof item.eventId !== 'string' || typeof item.title !== 'string') ||
    (overview.trajectory != null && !Array.isArray(overview.trajectory.positions))) {
    throw new ApiError('INVALID_RESPONSE', 'The refreshed employee state is incomplete.')
  }
}

// Refetch through the adapter, then publish one coherent snapshot. A failed read
// leaves the previous display intact; a late/aborted response never reaches cache.
export async function refreshEmployeeState(api: CareerApi, client: QueryClient, id: string) {
  const employeeKey = queryKeys.employee(id)
  const overviewKey = queryKeys.recommendations(id)
  const historyKey = queryKeys.history(id)
  const usesHistory = client.getQueryState(historyKey) !== undefined
  await Promise.all([client.cancelQueries({ queryKey: employeeKey, exact: true }), client.cancelQueries({ queryKey: overviewKey, exact: true }),
    client.cancelQueries({ queryKey: historyKey, exact: true })])
  const controller = new AbortController()
  let timer: ReturnType<typeof setTimeout> | undefined
  try {
    const snapshot = await Promise.race([
      Promise.all([api.getEmployee(id, { signal: controller.signal }), api.getRecommendations(id, { signal: controller.signal }),
        usesHistory ? api.getEmployeeHistory(id, { signal: controller.signal }) : Promise.resolve(undefined)]),
      new Promise<never>((_, reject) => { timer = setTimeout(() => {
        const error = new ApiError('TIMEOUT', 'The refresh timed out.')
        controller.abort(error)
        reject(error)
      }, REFRESH_TIMEOUT_MS) }),
    ])
    const [employee, overview, history] = snapshot
    validateSnapshot(employee, overview, id)
    if (usesHistory && !Array.isArray(history)) throw new ApiError('INVALID_RESPONSE', 'The refreshed history is incomplete.')
    client.setQueryData(employeeKey, employee)
    client.setQueryData(overviewKey, overview)
    if (usesHistory) client.setQueryData(historyKey, history)
    client.setQueryData<Employee[]>(queryKeys.employees, (current) => current?.map((item) => item.id === id ? employee : item))
    return overview
  } finally {
    clearTimeout(timer)
    controller.abort()
  }
}
