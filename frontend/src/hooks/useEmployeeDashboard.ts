import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import { queryKeys } from '../services/queryClient'
import { useEmployee } from './useEmployees'
import { refreshEmployeeState } from '../services/refreshEmployeeState'

export function useEmployeeDashboard(id: string) {
  const client = useQueryClient()
  const employee = useEmployee(id)
  const career = useQuery({
    queryKey: queryKeys.recommendations(id),
    queryFn: ({ signal }) => api.getRecommendations(id, { signal }),
    enabled: employee.isSuccess,
  })
  const employeeVersion = employee.data?.snapshotVersion
  const careerVersion = career.data?.snapshotVersion
  const snapshotMismatch = employeeVersion !== undefined && careerVersion !== undefined && employeeVersion !== careerVersion
  const snapshotRefresh = useQuery({
    queryKey: ['employee-snapshot-refresh', id],
    queryFn: ({ signal }) => refreshEmployeeState(api, client, id, signal),
    enabled: false,
    retry: false,
  })
  return { employee, career, snapshotMismatch, snapshotRefresh,
    refreshSnapshot: () => snapshotRefresh.refetch({ cancelRefetch: false }) }
}
