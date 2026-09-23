import { apiCopy } from '../i18n/api'
import type { Recommendation } from '../types/domain'

const label = (key: string) => key.replaceAll('_', ' ').replace(/^./, (letter) => letter.toUpperCase())

function EvidenceValue({ value }: { value: unknown }) {
  if (value == null) return <>{apiCopy.noValue}</>
  if (typeof value === 'boolean') return <>{value ? apiCopy.yes : apiCopy.no}</>
  if (Array.isArray(value)) return <ul>{value.map((item, index) => <li key={index}><EvidenceValue value={item} /></li>)}</ul>
  if (typeof value === 'object') return <EvidenceValues values={value as Record<string, unknown>} />
  return <>{String(value)}</>
}

function EvidenceValues({ values }: { values: Record<string, unknown> }) {
  return <dl className="supplied-evidence-values">{Object.entries(values).map(([key, value]) => <div key={key}>
    <dt>{label(key)}</dt><dd><EvidenceValue value={value} /></dd>
  </div>)}</dl>
}

export function SuppliedEvidence({ recommendation }: { recommendation: Recommendation }) {
  const entries = [
    ...(recommendation.supportingEvidence ?? []),
    ...(recommendation.explanation?.facts ?? []).map((fact) => ({ id: `fact-${fact.id}`, label: label(fact.code), values: fact.values })),
  ]
  if (!entries.length) return null
  return <section><h4>{apiCopy.evidence}</h4><div className="supplied-evidence-list">
    {entries.map((entry) => <details key={entry.id}><summary>{entry.label}</summary><EvidenceValues values={entry.values} /></details>)}
  </div></section>
}
