import { copy } from '../../i18n/en'
import type { HRAnalytics } from '../../types/domain'
import { formatAggregate, formatParticipation, isAggregateValue, isParticipationRate } from '../../utils/formatAnalytics'
import { Icon } from '../Icon'

export function HRMetricCards({ analytics }: { analytics: HRAnalytics }) {
  const metrics = [
    { label: copy.hr.total, note: copy.hr.totalNote, value: analytics.totalEmployees, icon: 'people' as const },
    { label: copy.hr.developing, note: copy.hr.developingNote, value: analytics.employeesInDevelopment, icon: 'compass' as const },
    { label: copy.hr.withoutNext, note: copy.hr.withoutNextNote, value: analytics.withoutNextStep, icon: 'arrow' as const },
    { label: copy.hr.rate, note: copy.hr.rateNote, value: analytics.participationRate, icon: 'chart' as const, rate: true },
  ]
  return <dl className="hr-metrics" aria-label={copy.hr.overview}>
    {metrics.map(({ label, note, value, icon, rate }) => {
      const available = rate ? isParticipationRate(value) : isAggregateValue(value)
      return <div className="surface hr-metric" key={label}>
        <dt><span>{label}</span><Icon name={icon} /></dt>
        <dd className={available ? 'hr-metric-value' : 'hr-metric-unavailable'}>
          {available && typeof value === 'number' ? (rate ? formatParticipation(value) : formatAggregate(value)) : copy.hr.unavailable}
        </dd>
        <dd className="hr-metric-note">{note}</dd>
      </div>
    })}
  </dl>
}
