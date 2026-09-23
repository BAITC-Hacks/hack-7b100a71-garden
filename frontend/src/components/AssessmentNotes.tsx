import { apiCopy } from '../i18n/api'
import type { CareerOverview } from '../types/domain'

export function AssessmentNotes({ overview }: { overview: CareerOverview }) {
  if (!overview.skillsEstimated && !overview.summary && !overview.warnings?.length) return null
  return <aside className="assessment-caveats" aria-label={apiCopy.assessmentNotes}>
    <h2>{overview.skillsEstimated ? apiCopy.estimated : apiCopy.assessmentNotes}</h2>
    {overview.skillsEstimated && <p>{apiCopy.estimatedDescription}</p>}
    {overview.summary && <p>{overview.summary}</p>}
    {!!overview.warnings?.length && <ul>{overview.warnings.map((warning, index) => <li key={`${warning.code}-${index}`}>{warning.message}</li>)}</ul>}
  </aside>
}
