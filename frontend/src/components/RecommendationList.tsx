import { copy } from '../i18n/en'
import type { Recommendation } from '../types/domain'
import { Icon } from './Icon'
import { RecommendationCard } from './RecommendationCard'

export function RecommendationList({ recommendations }: { recommendations: Recommendation[] }) {
  const labels = copy.dashboard
  // A presentation limit only. The adapter's ordering is authoritative.
  const preview = recommendations.slice(0, 3)
  return (
    <section className="recommendations-card surface" aria-labelledby="recommendations-heading">
      <div className="dashboard-section-heading">
        <p className="eyebrow">{labels.recommendationsEyebrow}</p><h2 id="recommendations-heading">{labels.recommendations}</h2><p>{labels.recommendationsDescription}</p>
      </div>
      {preview.length ? <>
        <ol className="recommendation-list" aria-label={labels.recommendationList}>
          {preview.map((recommendation, index) => <li key={recommendation.eventId}><RecommendationCard recommendation={recommendation} position={index + 1} /></li>)}
        </ol>
        <p className="recommendations-footnote">{labels.recommendationsNote}</p>
      </> : <div className="dashboard-empty"><Icon name="compass" /><h3>{labels.noRecommendations}</h3><p>{labels.noRecommendationsDescription}</p></div>}
    </section>
  )
}
