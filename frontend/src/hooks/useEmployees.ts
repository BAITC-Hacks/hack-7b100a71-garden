import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import { queryKeys } from '../services/queryClient'

export function useEmployees() {
  return useQuery({ queryKey: queryKeys.employees, queryFn: ({ signal }) => api.getEmployees({ signal }) })
}

export function useEmployee(id: string) {
  return useQuery({ queryKey: queryKeys.employee(id), queryFn: ({ signal }) => api.getEmployee(id, { signal }) })
}
