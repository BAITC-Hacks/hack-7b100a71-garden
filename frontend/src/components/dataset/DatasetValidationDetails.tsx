import { useId, useState } from 'react'
import { copy } from '../../i18n/en'
import type { DatasetIssue, DatasetValidationResult } from '../../types/domain'
import { formatAggregate, isAggregateValue } from '../../utils/formatAnalytics'
import { Button } from '../UI'

function DatasetIssues({ title, issues }: { title: string; issues: DatasetIssue[] }) {
  const [visible, setVisible] = useState(10)
  const id = useId()
  return <section className="dataset-issue-section" aria-labelledby={id}>
    <h3 id={id}>{title} <span>{issues.length}</span></h3>
    <ol className="dataset-issues" aria-label={title}>
      {issues.slice(0, visible).map((issue, index) => <li key={index}>
        <dl>{([[copy.dataset.file, issue.file], [copy.dataset.row, issue.row], [copy.dataset.record, issue.record], [copy.dataset.field, issue.field]] as const)
          .filter(([, value]) => value != null && value !== '').map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
        <p>{issue.message || copy.dataset.noMessage}</p>
      </li>)}
    </ol>
    {issues.length > visible && <Button className="dataset-secondary" onClick={() => setVisible((count) => count + 10)}>{copy.dataset.more} <span className="sr-only">{title.toLowerCase()}</span></Button>}
  </section>
}

export function DatasetValidationDetails({ result }: { result: DatasetValidationResult }) {
  const entries = (['employees', 'skills', 'events', 'activityHistory', 'recordsProcessed'] as const)
    .filter((key) => result.summary?.[key] !== undefined)
  return <div className="dataset-validation-details">
    {result.valid === true && <section aria-label={copy.dataset.summary}>
      <h3>{copy.dataset.summary}</h3>
      {entries.length ? <dl className="dataset-summary">{entries.map((key) => {
        const value = result.summary?.[key]
        return <div key={key}><dt>{copy.dataset[key]}</dt><dd>{isAggregateValue(value) ? formatAggregate(value) : copy.dataset.noSummary}</dd></div>
      })}</dl> : <p className="dataset-muted">{copy.dataset.noSummary}</p>}
    </section>}
    {!!result.errors?.length && <DatasetIssues title={copy.dataset.errors} issues={result.errors} />}
    {result.valid === false && !result.errors?.length && <p className="dataset-muted">{copy.dataset.noErrorDetails}</p>}
    {!!result.warnings?.length && <DatasetIssues title={copy.dataset.warnings} issues={result.warnings} />}
  </div>
}
