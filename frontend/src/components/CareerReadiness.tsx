import { copy } from '../i18n/en'
import type { CareerReadiness as Readiness, CareerTarget, Recommendation } from '../types/domain'
import { Icon } from './Icon'
import { formatReadiness, isReadinessValue } from '../utils/formatReadiness'
import { ReadinessImpact } from './ReadinessImpact'

export function CareerReadiness({ readiness, target, projection }: {
  readiness: Readiness | null
  target: CareerTarget | null
  projection?: Pick<Recommendation, 'title' | 'readinessBefore' | 'readinessAfter'> | null
}) {
  const labels = copy.dashboard
  const value = readiness?.current
  // Display validity only. Never calculate or repair an assessment.
  const available = isReadinessValue(value)
  const formatted = available ? formatReadiness(value) : null
  const extended = (formatted?.length ?? 0) > 10
  const before = isReadinessValue(projection?.readinessBefore) ? formatReadiness(projection.readinessBefore) : null
  const after = isReadinessValue(projection?.readinessAfter) ? formatReadiness(projection.readinessAfter) : null
  return (
    <section className="readiness-card" aria-labelledby="readiness-heading">
      <div className="dashboard-card-heading">
        <div><p className="eyebrow">{labels.readinessEyebrow}</p><h2 id="readiness-heading">{labels.readiness}</h2></div>
        <Icon name="spark" />
      </div>
      {available ? <>
        <div className="readiness-content">
          <div className="readiness-ring" role="meter" aria-label={labels.readiness}
            aria-valuemin={0} aria-valuemax={1} aria-valuenow={value} aria-valuetext={formatted ?? undefined}>
            <svg viewBox="0 0 160 160" aria-hidden="true">
              <circle className="ring-track" cx="80" cy="80" r="68" />
              <circle className="ring-value" cx="80" cy="80" r="68" pathLength="100" strokeDasharray={`${value * 100} 100`} />
            </svg>
            <span className={`readiness-number ${extended ? 'readiness-number-caption' : (formatted?.length ?? 0) > 5 ? 'readiness-number-precise' : ''}`}>{extended ? labels.currentAssessment : formatted}</span>
          </div>
          <div className="readiness-context">
            <p>{target ? labels.readinessLabel : labels.currentAssessment}</p>
            {target && <strong>{target.grade}<span>{target.role}</span></strong>}
          </div>
        </div>
        {extended && <p className="readiness-exact-value">{formatted}</p>}
        <p className="readiness-note">{target ? labels.readinessNote : labels.readinessUntargetedNote}</p>
      </> : <div className="readiness-empty">
        <span aria-hidden="true">—</span><h3>{labels.readinessUnavailable}</h3>
        <p>{target ? labels.readinessMissingNote : labels.noTargetReadiness}</p>
      </div>}
      {projection && before !== null && after !== null && <div className="readiness-projection" role="group" aria-label={labels.readinessProjection}>
        <h3>{labels.readinessProjection}</h3>
        <p>{projection.title}</p>
        <ReadinessImpact before={projection.readinessBefore} after={projection.readinessAfter} />
      </div>}
    </section>
  )
}
