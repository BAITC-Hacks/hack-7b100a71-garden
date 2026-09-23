import { useId, type ReactNode } from 'react'
import { copy } from '../../i18n/en'
import type { HRAnalytics } from '../../types/domain'
import { formatAggregate, formatParticipation, isAggregateValue, isParticipationRate } from '../../utils/formatAnalytics'
import { HRAggregateBars } from './HRAggregateBars'
import { Icon } from '../Icon'
import { apiCopy } from '../../i18n/api'

function InsightCard({ eyebrow, title, description, children, className = '' }: { eyebrow: string; title: string; description: string; children: ReactNode; className?: string }) {
  const id = useId()
  return <section className={`surface hr-insight ${className}`} aria-labelledby={id}>
    <header className="hr-card-heading"><p className="eyebrow">{eyebrow}</p><h2 id={id}>{title}</h2><p>{description}</p></header>
    {children}
  </section>
}

function InsightEmpty({ title, description }: { title: string; description: string }) {
  return <div className="hr-section-empty"><Icon name="chart" /><p>{title}</p><span>{description}</span></div>
}

export function HRSkillGaps({ gaps, basis }: { gaps: HRAnalytics['commonSkillGaps']; basis?: string }) {
  return <InsightCard eyebrow={copy.hr.gapsEyebrow} title={copy.hr.gaps} description={copy.hr.gapsDescription}>
    {basis && <p className="hr-chart-note">{apiCopy.gapBasis}: {basis.replaceAll('_', ' ')}</p>}
    {gaps?.length ? <HRAggregateBars label={copy.hr.gaps} unit={copy.hr.employees} singularUnit={copy.hr.employee}
      rows={gaps.map((gap) => ({ id: gap.skillId, label: gap.name, value: gap.employeeCount }))} />
      : <InsightEmpty title={copy.hr.gapsEmpty} description={copy.hr.gapsEmptyDescription} />}
  </InsightCard>
}

export function HRNextStep({ count, coverage }: { count: HRAnalytics['withoutNextStep']; coverage?: HRAnalytics['nextStepCoverage'] }) {
  const id = useId()
  return <section className="hr-next-step" aria-labelledby={id}>
    <div className="hr-next-icon" aria-hidden="true"><Icon name="compass" /></div>
    <p className="eyebrow">{copy.hr.nextEyebrow}</p><h2 id={id}>{copy.hr.next}</h2>
    {isAggregateValue(count) ? <p className="hr-next-stat"><strong>{formatAggregate(count)}</strong><span>{copy.hr.nextLabel}</span></p>
      : <p className="hr-next-unavailable">{copy.hr.nextUnavailable}</p>}
    <p className="hr-next-description">{coverage?.complete === false ? apiCopy.coveragePartialDescription : copy.hr.nextDescription}</p>
    {coverage && <div className="hr-coverage">
      <p>{coverage.available === false ? apiCopy.coverageUnavailable : coverage.complete === false ? apiCopy.coveragePartial : coverage.complete === true ? apiCopy.coverageComplete : apiCopy.coverage}</p>
      <dl>{isAggregateValue(coverage.evaluatedCount) && <div><dt>{apiCopy.evaluated}</dt><dd>{formatAggregate(coverage.evaluatedCount)}</dd></div>}
        {isAggregateValue(coverage.pendingCount) && <div><dt>{apiCopy.pending}</dt><dd>{formatAggregate(coverage.pendingCount)}</dd></div>}</dl>
    </div>}
  </section>
}

export function HRParticipation({ activities, rate, participatingEmployees, recordCount }: { activities: HRAnalytics['activityParticipation']; rate: HRAnalytics['participationRate']; participatingEmployees?: number; recordCount?: number }) {
  return <InsightCard eyebrow={copy.hr.participationEyebrow} title={copy.hr.participation} description={copy.hr.participationDescription}>
    {(isAggregateValue(participatingEmployees) || isAggregateValue(recordCount)) && <dl className="hr-participation-counts">
      {isAggregateValue(participatingEmployees) && <div><dt>{apiCopy.participating}</dt><dd>{formatAggregate(participatingEmployees)}</dd></div>}
      {isAggregateValue(recordCount) && <div><dt>{apiCopy.participationRecords}</dt><dd>{formatAggregate(recordCount)}</dd></div>}
    </dl>}
    {isParticipationRate(rate) && <div className="hr-participation-rate">
      <div><strong>{formatParticipation(rate)}</strong><span>{copy.hr.rateNote}</span></div>
      <div className="hr-rate-track" role="meter" aria-label={copy.hr.rate} aria-valuemin={0} aria-valuemax={1} aria-valuenow={rate} aria-valuetext={formatParticipation(rate)}>
        <span style={{ width: `${rate * 100}%` }} />
      </div>
    </div>}
    {activities?.length ? <HRAggregateBars label={copy.hr.participation} unit={copy.hr.participants} singularUnit={copy.hr.participant}
      rows={activities.map((activity) => ({ id: activity.activityId, label: activity.title, value: activity.participantCount }))} />
      : <InsightEmpty title={copy.hr.participationEmpty} description={copy.hr.participationEmptyDescription} />}
  </InsightCard>
}

export function HRStatusDistribution({ statuses }: { statuses: HRAnalytics['activityStatuses'] }) {
  return <InsightCard eyebrow={copy.hr.statusEyebrow} title={copy.hr.status} description={copy.hr.statusDescription} className="hr-status-insight">
    {statuses?.length ? <HRAggregateBars label={copy.hr.status} unit={copy.hr.records} singularUnit={copy.hr.record}
      rows={statuses.map(({ status, count }) => ({ id: status, label: copy.hr.statuses[status], value: count, tone: status }))} />
      : <InsightEmpty title={copy.hr.statusEmpty} description={copy.hr.statusEmptyDescription} />}
  </InsightCard>
}
