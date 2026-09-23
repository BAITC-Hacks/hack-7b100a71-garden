import { useId } from 'react'
import { copy } from '../i18n/en'
import type { CareerTarget, Recommendation } from '../types/domain'
import { ActivityImpact } from './ActivityImpact'
import { Icon } from './Icon'
import { ReadinessImpact } from './ReadinessImpact'
import { RecommendationExplanation } from './RecommendationExplanation'
import { Button } from './UI'
import { canRetryCompletion, isCompletionBusy, type CompletionState } from '../types/completion'

export type RecommendationStartHandler = (recommendation: Recommendation) => void

export function RecommendationCard({ recommendation, primary = false, target, onStart, completion }: {
  recommendation: Recommendation
  primary?: boolean
  target?: CareerTarget | null
  onStart?: RecommendationStartHandler
  completion?: CompletionState
}) {
  const labels = copy.dashboard
  const id = useId()
  const duration = recommendation.durationMinutes
  const active = completion?.eventId === recommendation.eventId
  const completed = completion?.completedEventIds.includes(recommendation.eventId)
  const submitting = active && completion?.phase === 'submitting'
  const blocked = !!completion && (isCompletionBusy(completion) || completion.phase === 'refresh-error' ||
    (completion.phase === 'error' && !canRetryCompletion(completion)))
  return (
    <article className={`recommendation-card ${primary ? 'recommendation-primary' : ''}`} aria-labelledby={`${id}-title`}>
      <div className="recommendation-meta">
        <span className="activity-type-icon"><Icon name="compass" /></span>
        {recommendation.type && <span>{recommendation.type}</span>}
        {typeof duration === 'number' && Number.isFinite(duration) && <span className="recommendation-duration">{duration} {labels.minutes}</span>}
      </div>
      <h3 id={`${id}-title`}>{recommendation.title}</h3>
      {recommendation.careerImpact && <p className="recommendation-impact"><Icon name="spark" /><span>{labels.careerImpact}: <strong>{recommendation.careerImpact}</strong></span></p>}
      <div className="recommendation-card-impact">
        <h4>{labels.skillImpact}</h4><ActivityImpact skills={recommendation.skillImpact} />
        <div className="recommendation-readiness"><h4>{labels.readiness}</h4>
          <ReadinessImpact before={recommendation.readinessBefore} after={recommendation.readinessAfter} />
        </div>
      </div>
      <RecommendationExplanation recommendation={recommendation} target={target} />
      <div className="recommendation-action">
        <Button disabled={!onStart || blocked || completed} onClick={onStart ? () => onStart(recommendation) : undefined} aria-busy={submitting || undefined}
          aria-describedby={!onStart ? `${id}-action-note` : undefined}>
          {submitting ? <><span className="completion-spinner" aria-hidden="true" />{copy.completion.submitting}</> : completed ? copy.completion.completed :
            active && completion && canRetryCompletion(completion) ? copy.completion.retry : <>{labels.startDevelopment}<Icon name="arrow" /></>}
        </Button>
        {!onStart && <p id={`${id}-action-note`}>{labels.activityActionUnavailable}</p>}
      </div>
    </article>
  )
}
