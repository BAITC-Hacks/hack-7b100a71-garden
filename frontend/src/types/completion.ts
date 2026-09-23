import type { ApiErrorCode } from './api'

export interface CompletionState {
  phase: 'idle' | 'submitting' | 'refreshing' | 'success' | 'error' | 'refresh-error'
  eventId?: string
  title?: string
  confirmed: boolean
  alreadyCompleted?: boolean
  errorCode?: ApiErrorCode
  completedEventIds: string[]
  beforeReadiness?: number
  afterReadiness?: number
}

export const idleCompletion: CompletionState = { phase: 'idle', confirmed: false, completedEventIds: [] }
export const isCompletionBusy = (state: CompletionState) => state.phase === 'submitting' || state.phase === 'refreshing'
export const canRetryCompletion = (state: CompletionState) => state.phase === 'error' &&
  (state.errorCode === 'NETWORK' || state.errorCode === 'TIMEOUT' || state.errorCode === 'UNAVAILABLE' || state.errorCode === 'INVALID_RESPONSE')
