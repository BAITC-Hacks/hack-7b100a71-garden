import { copy } from '../i18n/en'
import type { ActivityHistory, CareerOverview, Recommendation } from '../types/domain'
import { Icon } from './Icon'
import { RecommendationCard } from './RecommendationCard'

const statusLabels: Record<string, string> = {
  no_next_grade: 'No next grade for this career direction',
  target_satisfied: 'Target requirements are already satisfied',
  no_eligible_recommendations: 'No eligible activities for the current target',
  invalid_target_requirements: 'Target requirements are unavailable',
}

export function RecommendationList({ recommendations, status, summary, raw, onComplete, completingEventId, disabled = false, history = [] }: {
  recommendations: Recommendation[]
  status?: CareerOverview['status']
  summary?: CareerOverview['explanationSummary']
  raw?: CareerOverview['raw']
  onComplete?: (eventId: string, recordId?: string) => void
  history?: ActivityHistory[]
  completingEventId?: string
  disabled?: boolean
}) {
  const labels = copy.dashboard
  // A presentation limit only. Preserve the server's order and explicit ranks.
  const preview = recommendations.slice(0, 3)
  return (
    <section className="recommendations-card surface" aria-labelledby="recommendations-heading" data-recommendation-status={status}>
      <div className="dashboard-section-heading">
        <p className="eyebrow">{labels.recommendationsEyebrow}</p><h2 id="recommendations-heading">{labels.recommendations}</h2>
        {summary?.text ? <p lang={summary.language}>{summary.text}</p> : <p>{labels.recommendationsDescription}</p>}
      </div>
      {preview.length ? <>
        <ol className="recommendation-list" aria-label={labels.recommendationList}>
          {preview.map((recommendation, index) => <li key={recommendation.eventId}><RecommendationCard recommendation={recommendation} position={index + 1}
            assignments={history.filter((record) => record.eventId === recommendation.eventId && (record.status === 'in_progress' || record.status === 'overdue'))} onComplete={onComplete} completing={completingEventId === recommendation.eventId} disabled={disabled} /></li>)}
        </ol>
        <p className="recommendations-footnote">{labels.recommendationsNote}</p>
      </> : <div className="dashboard-empty"><Icon name="compass" /><h3>{status && statusLabels[status] ? statusLabels[status] : labels.noRecommendations}</h3>
        <p>{status ? `Backend status: ${status}` : labels.noRecommendationsDescription}</p>
        {raw?.blocked_summary && <details className="recommendation-evidence"><summary>Availability and remaining gaps</summary><pre>{JSON.stringify(raw.blocked_summary, null, 2)}</pre></details>}
      </div>}
    </section>
  )
}
