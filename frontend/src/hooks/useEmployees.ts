import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import { queryKeys } from '../services/queryClient'
import { canAccessEmployee } from '../services/session'
import { useSession } from './useSession'

export function useEmployees() {
  const session = useSession()
  return useQuery({ queryKey: queryKeys.employees, queryFn: ({ signal }) => api.getEmployees({ signal }), enabled: session?.role === 'hr' })
}

export function useEmployee(id: string) {
  const session = useSession()
  return useQuery({ queryKey: queryKeys.employee(id), queryFn: ({ signal }) => api.getEmployee(id, { signal }), enabled: !!id && canAccessEmployee(session, id) })
}
