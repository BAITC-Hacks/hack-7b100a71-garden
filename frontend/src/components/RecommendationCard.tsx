import { copy } from '../i18n/en'
import type { Recommendation } from '../types/domain'
import { Icon } from './Icon'

export function RecommendationCard({ recommendation, position }: { recommendation: Recommendation; position: number }) {
  const labels = copy.dashboard
  return (
    <article className="recommendation-preview">
      <div className="recommendation-meta">
        <span className="recommendation-number" aria-hidden="true">{String(position).padStart(2, '0')}</span>
        <span>{recommendation.type}</span><span className="recommendation-duration">{recommendation.durationMinutes} {labels.minutes}</span>
      </div>
      <h3>{recommendation.title}</h3>
      {recommendation.explanation.text && <p className="recommendation-summary">{recommendation.explanation.text}</p>}
      {recommendation.skillImpact.length > 0 && <ul className="skill-tags" aria-label={labels.skillFocus}>
        {recommendation.skillImpact.map((skill) => <li key={skill.skillId}>{skill.name}</li>)}
      </ul>}
      {recommendation.careerImpact && <p className="recommendation-impact"><Icon name="spark" />{recommendation.careerImpact} {labels.impact}</p>}
    </article>
  )
}
