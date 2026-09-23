import { skipToken, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import { queryKeys } from '../services/queryClient'
import { refreshEmployeeState } from '../services/refreshEmployeeState'
import { ApiError } from '../types/api'
import type { CareerOverview, Recommendation } from '../types/domain'
import { canRetryCompletion, idleCompletion, isCompletionBusy, type CompletionState } from '../types/completion'

export function useActivityCompletion(employeeId: string) {
  const client = useQueryClient()
  const key = queryKeys.completion(employeeId)
  // Employee-scoped operation metadata survives selection changes. Business data
  // is only published by refreshEmployeeState after both reads succeed.
  const { data: state = idleCompletion } = useQuery<CompletionState>({ queryKey: key, queryFn: skipToken, initialData: idleCompletion, staleTime: Infinity, gcTime: Infinity })
  const current = () => client.getQueryData<CompletionState>(key) ?? idleCompletion
  const update = (patch: Partial<CompletionState>) => client.setQueryData<CompletionState>(key, { ...current(), ...patch })

  async function refresh() {
    update({ phase: 'refreshing', errorCode: undefined })
    try {
      const overview = await refreshEmployeeState(api, client, employeeId)
      update({ phase: 'success', afterReadiness: overview.readiness?.current })
    } catch (error) {
      update({ phase: 'refresh-error', errorCode: error instanceof ApiError ? error.code : 'NETWORK' })
    }
  }

  async function complete(recommendation: Recommendation) {
    const previous = current()
    if (isCompletionBusy(previous) || previous.phase === 'refresh-error' || previous.completedEventIds.includes(recommendation.eventId) ||
      (previous.phase === 'error' && !canRetryCompletion(previous))) return
    // Synchronous cache update also guards two clicks before React re-renders.
    update({ phase: 'submitting', eventId: recommendation.eventId, title: recommendation.title, confirmed: false,
      alreadyCompleted: false, errorCode: undefined, afterReadiness: undefined,
      beforeReadiness: client.getQueryData<CareerOverview>(queryKeys.recommendations(employeeId))?.readiness?.current })
    try {
      await api.completeActivity(employeeId, recommendation.eventId)
    } catch (error) {
      if (!(error instanceof ApiError) || error.code !== 'ALREADY_COMPLETED') {
        update({ phase: 'error', errorCode: error instanceof ApiError ? error.code : 'NETWORK' })
        return
      }
      update({ alreadyCompleted: true })
    }
    update({ confirmed: true, completedEventIds: [...current().completedEventIds, recommendation.eventId] })
    await refresh()
  }

  async function retryRefresh() {
    const latest = current()
    if (latest.phase !== 'refresh-error' && !(latest.phase === 'error' && latest.errorCode === 'RECOMMENDATION_UNAVAILABLE')) return
    await refresh()
  }

  async function retryCompletion() {
    const latest = current()
    if (canRetryCompletion(latest) && latest.eventId && latest.title) await complete({ eventId: latest.eventId, title: latest.title })
  }

  return { state, complete, retryRefresh, retryCompletion }
}
