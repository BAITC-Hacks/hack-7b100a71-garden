import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'
import { queryKeys } from '../services/queryClient'

export function useHRAnalytics() {
  return useQuery({ queryKey: queryKeys.hr, queryFn: ({ signal }) => api.getHRAnalytics({ signal }) })
}
