import { useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import { queryKeys } from '../services/queryClient'
import { createCompletionAction, runCompletionAction } from '../services/completionAction'
import type { CompletionAction } from '../services/completionAction'
import { useEmployee } from './useEmployees'
import { useSession } from './useSession'
import { canAccessEmployee } from '../services/session'

export function useEmployeeDashboard(id: string) {
  const employee = useEmployee(id)
  const session = useSession()
  const allowed = canAccessEmployee(session, id)
  const client = useQueryClient()
  const actions = useRef(new Map<string, CompletionAction>())
  const inFlight = useRef(false)
  const career = useQuery({
    queryKey: queryKeys.recommendations(id),
    queryFn: ({ signal }) => api.getRecommendations(id, { signal }),
    enabled: allowed && employee.isSuccess,
  })
  const history = useQuery({
    queryKey: queryKeys.history(id),
    queryFn: ({ signal }) => api.getEmployeeHistory(id, { signal }),
    enabled: allowed && employee.isSuccess,
  })
  const completion = useMutation({
    onSettled: () => { inFlight.current = false },
    mutationFn: async ({ employeeId, eventId, recordId }: { employeeId: string; eventId: string; recordId?: string }) => {
      const actionId = JSON.stringify([employeeId, eventId, recordId ?? null])
      let action = actions.current.get(actionId)
      if (!action) {
        action = createCompletionAction(employeeId, eventId, undefined, recordId)
        actions.current.set(actionId, action)
      }
      const receipt = await runCompletionAction(action, {
        submit: (employeeId, eventId, options) => api.completeActivity(employeeId, eventId, options),
        refresh: async (employeeId) => {
          // No local arithmetic: every displayed level and recommendation is read
          // again from the backend after its durable completion receipt.
          await Promise.all([
            client.invalidateQueries({ queryKey: queryKeys.employee(employeeId) }),
            client.invalidateQueries({ queryKey: queryKeys.history(employeeId) }),
            client.invalidateQueries({ queryKey: queryKeys.recommendations(employeeId) }),
            client.invalidateQueries({ queryKey: queryKeys.hr }),
          ])
        },
      })
      // A confirmed action is finished. Any later deliberate completion gets a new key.
      actions.current.delete(actionId)
      return { employeeId, eventId, receipt }
    },
  })
  const complete = (eventId: string, recordId?: string) => {
    if (!allowed || inFlight.current) return
    inFlight.current = true
    completion.mutate({ employeeId: id, eventId, ...(recordId ? { recordId } : {}) })
  }
  const refresh = async () => {
    await Promise.all([employee.refetch(), career.refetch(), history.refetch()])
  }
  return { employee, career, history, completion, complete, refresh }
}
