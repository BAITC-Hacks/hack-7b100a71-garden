import { copy } from '../i18n/en'
import { formatReadiness, isReadinessValue } from '../utils/formatReadiness'

export function ReadinessImpact({ before, after, afterLabel }: { before?: number | null; after?: number | null; afterLabel?: string }) {
  const labels = copy.dashboard
  const hasBefore = isReadinessValue(before)
  const hasAfter = isReadinessValue(after)
  if (!hasBefore && !hasAfter) return <p className="impact-unavailable">{labels.noReadinessImpact}</p>
  return <dl className="readiness-impact-values">
    <div><dt>{labels.readinessBefore}</dt><dd>{hasBefore ? formatReadiness(before) : <span className="impact-missing">{labels.notProvided}</span>}</dd></div>
    <div><dt>{afterLabel ?? labels.readinessAfter}</dt><dd>{hasAfter ? formatReadiness(after) : <span className="impact-missing">{labels.notProvided}</span>}</dd></div>
  </dl>
}
