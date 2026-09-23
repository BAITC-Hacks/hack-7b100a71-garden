import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import { queryKeys } from '../services/queryClient'
import { useEmployee } from './useEmployees'

export function useEmployeeDashboard(id: string) {
  const employee = useEmployee(id)
  const career = useQuery({
    queryKey: queryKeys.recommendations(id),
    queryFn: ({ signal }) => api.getRecommendations(id, { signal }),
    enabled: employee.isSuccess,
  })
  return { employee, career }
}
