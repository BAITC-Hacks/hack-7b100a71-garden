import { copy } from '../i18n/en'
import type { CareerTarget, Recommendation } from '../types/domain'
import { Icon } from './Icon'
import { RecommendationCard, type RecommendationStartHandler } from './RecommendationCard'
import type { CompletionState } from '../types/completion'
import { CompletionFeedback } from './CompletionFeedback'

export function RecommendationList({ recommendations, target, onStart, completion, onRetry, onRefresh, blockedReason }: {
  recommendations: Recommendation[]
  target?: CareerTarget | null
  onStart?: RecommendationStartHandler
  completion?: CompletionState
  onRetry?: () => void
  onRefresh?: () => void
  blockedReason?: string
}) {
  const labels = copy.dashboard
  // A presentation limit only. The adapter's ordering is authoritative.
  const preview = recommendations.slice(0, 3)
  return (
    <section className="recommendations-card surface" aria-labelledby="recommendations-heading">
      <div className="dashboard-section-heading">
        <p className="eyebrow">{labels.recommendationsEyebrow}</p><h2 id="recommendations-heading">{labels.recommendations}</h2><p>{labels.recommendationsDescription}</p>
      </div>
      {blockedReason && <p role="status">{blockedReason}</p>}
      <fieldset disabled={Boolean(blockedReason)} aria-label={labels.recommendationList} style={{ border: 0, margin: 0, padding: 0, minWidth: 0 }}>
      {completion && onRetry && onRefresh && <CompletionFeedback state={completion} onRetry={onRetry} onRefresh={onRefresh} />}
      {preview.length ? <>
        <ol className={`recommendation-list ${preview.length === 2 ? 'recommendation-list-pair' : ''}`} aria-label={labels.recommendationList}>
          {preview.map((recommendation, index) => <li key={recommendation.eventId}><RecommendationCard recommendation={recommendation} primary={index === 0} target={target} onStart={onStart} completion={completion} /></li>)}
        </ol>
        <p className="recommendations-footnote">{labels.recommendationsNote}</p>
      </> : <div className="dashboard-empty"><Icon name="compass" /><h3>{labels.noRecommendations}</h3><p>{labels.noRecommendationsDescription}</p></div>}
      </fieldset>
    </section>
  )
}
