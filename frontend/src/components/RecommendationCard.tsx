import { useState } from 'react'
import { copy } from '../i18n/en'
import type { ActivityHistory, Recommendation } from '../types/domain'
import { Button } from './UI'

function percent(value: number) {
  return new Intl.NumberFormat('en', { style: 'percent', maximumFractionDigits: 2 }).format(value)
}

export function RecommendationCard({ recommendation, position, onComplete, completing = false, disabled = false, assignments = [] }: {
  recommendation: Recommendation
  position: number
  onComplete?: (eventId: string, recordId?: string) => void
  assignments?: ActivityHistory[]
  completing?: boolean
  disabled?: boolean
}) {
  const labels = copy.dashboard
  const [recordId, setRecordId] = useState('')
  const needsAssignment = assignments.length > 1
  const selectedAssignment = assignments.some((record) => record.id === recordId) ? recordId : undefined
  const evidence = recommendation.raw?.evidence
  return (
    <article className="recommendation-preview" data-event-id={recommendation.eventId}>
      <div className="recommendation-meta">
        <span className="recommendation-number" aria-label={`Rank ${recommendation.rank ?? position}`}>{String(recommendation.rank ?? position).padStart(2, '0')}</span>
        <span>{recommendation.type}{recommendation.format ? ` · ${recommendation.format}` : ''}</span><span className="recommendation-duration">{recommendation.durationMinutes} {labels.minutes}</span>
      </div>
      <h3>{recommendation.title}</h3>
      <p className="recommendation-event-id">{recommendation.eventId}</p>
      {recommendation.skillImpact.length > 0 && <ul className="skill-impact-list" aria-label={labels.skillFocus}>
        {recommendation.skillImpact.map((skill) => <li key={skill.skillId}>
          <span>{skill.name}{skill.critical && <small>Critical</small>}</span>
          <strong>{skill.current} → {skill.after}<small> required {skill.required}</small></strong>
        </li>)}
      </ul>}
      {recommendation.readinessBefore !== null && recommendation.readinessAfter !== null &&
        <p className="recommendation-readiness">Target coverage: <strong>{percent(recommendation.readinessBefore)} → {percent(recommendation.readinessAfter)}</strong><span>Simulated after completion</span></p>}
      {evidence?.audience_match && <p className="recommendation-audience">
        Admission: <strong>{evidence.audience_match}</strong> · attained grade <strong>{evidence.attained_grade}</strong>
      </p>}
      {recommendation.explanation.text && <details className="recommendation-explanation" open={position === 1}>
        <summary>Why this?</summary>
        <p className="recommendation-summary" lang={recommendation.explanation.language}>{recommendation.explanation.text}</p>
        <p className="explanation-source">{recommendation.explanation.language?.toUpperCase()}{recommendation.explanation.source ? ` · ${recommendation.explanation.source}` : ''}</p>
      </details>}
      {(recommendation.raw || recommendation.explanation.factors.length > 0) && <details className="recommendation-evidence">
        <summary>Score, factors and evidence</summary>
        {recommendation.score !== null && <p>Backend score: <strong>{recommendation.score}</strong></p>}
        {recommendation.explanation.factors.length > 0 && <dl className="factor-list">{recommendation.explanation.factors.map((factor) =>
          <div key={factor.id}><dt>{factor.label}</dt><dd>{factor.value}</dd></div>,
        )}</dl>}
        {recommendation.raw && <details><summary>Full structured evidence</summary><pre>{JSON.stringify(recommendation.raw, null, 2)}</pre></details>}
      </details>}
      {onComplete && <div className="recommendation-actions">
        {needsAssignment && <label className="completion-assignment">Assignment to complete
          <select value={selectedAssignment ?? ''} disabled={disabled || completing} onChange={(event) => setRecordId(event.target.value)}>
            <option value="">Choose an assignment</option>
            {assignments.map((record) => <option key={record.id} value={record.id}>{record.id} · {record.status}{record.date ? ` · ${record.date}` : ''}</option>)}
          </select>
        </label>}
        <Button disabled={disabled || completing || (needsAssignment && !selectedAssignment)} onClick={() => onComplete(recommendation.eventId, needsAssignment ? selectedAssignment : undefined)}>
          {completing ? 'Saving completion…' : 'Complete activity'}
        </Button>
        <span>Progress is updated after backend confirmation.</span>
      </div>}
    </article>
  )
}
