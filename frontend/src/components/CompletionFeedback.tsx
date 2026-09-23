import { useEffect, useRef } from 'react'
import { copy } from '../i18n/en'
import { isReadinessValue } from '../utils/formatReadiness'
import { canRetryCompletion, type CompletionState } from '../types/completion'
import { ReadinessImpact } from './ReadinessImpact'
import { Button } from './UI'

export function CompletionFeedback({ state, onRetry, onRefresh }: { state: CompletionState; onRetry: () => void; onRefresh: () => void }) {
  const labels = copy.completion
  const panel = useRef<HTMLDivElement>(null)
  const previousPhase = useRef(state.phase)
  useEffect(() => {
    if ((previousPhase.current === 'refreshing' || previousPhase.current === 'submitting') &&
      (state.phase === 'success' || state.phase === 'refresh-error' || state.phase === 'error')) panel.current?.focus({ preventScroll: true })
    previousPhase.current = state.phase
  }, [state.phase])
  if (state.phase === 'idle') return null
  const refreshError = state.phase === 'refresh-error'
  const error = state.phase === 'error'
  const unavailable = error && state.errorCode === 'RECOMMENDATION_UNAVAILABLE'
  const title = state.confirmed ? (state.alreadyCompleted ? labels.alreadyCompleted : labels.completed) :
    state.phase === 'submitting' ? labels.submitting : state.phase === 'refreshing' ? labels.refreshingTitle :
      refreshError ? labels.refreshFailedTitle : error ? labels.failed : labels.refreshed
  const description = state.phase === 'submitting' ? labels.submittingDescription :
    state.phase === 'refreshing' ? (state.confirmed ? labels.refreshing : labels.refreshingOnly) : refreshError ? labels.refreshFailed :
      unavailable ? labels.unavailable : error && state.errorCode === 'NOT_FOUND' ? labels.employeeMissing :
        error ? labels.failedDescription : labels.successDescription
  return <div ref={panel} tabIndex={-1} className={`completion-feedback ${error || refreshError ? 'completion-warning' : ''}`}
    role={error || refreshError ? 'alert' : 'status'} aria-live={error || refreshError ? 'assertive' : 'polite'}>
    <div className="completion-feedback-copy">
      <h3>{(state.phase === 'submitting' || state.phase === 'refreshing') && <span className="completion-spinner" aria-hidden="true" />}{title}</h3>
      {state.title && <p className="completed-activity-title">{state.title}</p>}
      <p>{description}</p>
      {state.phase === 'success' && state.confirmed && isReadinessValue(state.beforeReadiness) && isReadinessValue(state.afterReadiness) &&
        <div className="completion-readiness"><p>{copy.dashboard.readiness}</p><ReadinessImpact before={state.beforeReadiness} after={state.afterReadiness} afterLabel={labels.now} /></div>}
    </div>
    {canRetryCompletion(state) && <Button onClick={onRetry}>{labels.retry}</Button>}
    {(refreshError || unavailable) && <Button onClick={onRefresh}>{labels.retryRefresh}</Button>}
  </div>
}
