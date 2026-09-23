import { copy } from '../i18n/en'
import type { CareerTarget, Recommendation } from '../types/domain'
import { ActivityImpact } from './ActivityImpact'
import { Icon } from './Icon'
import { ReadinessImpact } from './ReadinessImpact'

export function RecommendationExplanation({ recommendation, target }: { recommendation: Recommendation; target?: CareerTarget | null }) {
  const labels = copy.dashboard
  const factors = recommendation.explanation?.factors
  return <details className="recommendation-explanation">
    <summary><Icon name="spark" /><span>{labels.whyRecommendation}</span><Icon name="chevron" /></summary>
    <div className="recommendation-evidence">
      <p className="evidence-intro">{labels.evidenceIntro}</p>
      <section><h4>{labels.skillImpact}</h4><ActivityImpact skills={recommendation.skillImpact} expanded /></section>
      <section>
        <h4>{labels.careerImpact}</h4>
        <dl className="career-evidence">
          {target && <div><dt>{labels.target}</dt><dd>{target.role} · {target.grade}</dd></div>}
          <div><dt>{labels.suppliedImpact}</dt><dd>{recommendation.careerImpact || labels.notProvided}</dd></div>
        </dl>
        <h5>{labels.readiness}</h5>
        <ReadinessImpact before={recommendation.readinessBefore} after={recommendation.readinessAfter} />
      </section>
      <section>
        <h4>{labels.recommendationFactors}</h4>
        {factors?.length ? <dl className="recommendation-factors">{factors.map((factor) =>
          <div key={factor.id}><dt>{factor.label}</dt><dd>{typeof factor.value === 'number' && Number.isFinite(factor.value) ? factor.value : labels.notProvided}</dd></div>,
        )}</dl> : <p className="impact-unavailable">{labels.noFactors}</p>}
      </section>
      <section className="written-explanation">
        <h4><Icon name="spark" />{labels.writtenExplanation}</h4>
        <p>{recommendation.explanation?.text?.trim() ? recommendation.explanation.text : labels.noExplanation}</p>
      </section>
    </div>
  </details>
}
