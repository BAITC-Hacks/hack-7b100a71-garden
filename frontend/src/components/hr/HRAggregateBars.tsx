import { copy } from '../../i18n/en'
import { formatAggregate, isAggregateValue } from '../../utils/formatAnalytics'

interface AggregateRow { id: string; label: string; value?: number | null; tone?: string }

// Relative widths are chart geometry only. No totals, rates, or ranking are derived.
export function HRAggregateBars({ rows, label, unit, singularUnit }: { rows: AggregateRow[]; label: string; unit: string; singularUnit: string }) {
  const scale = Math.max(1, ...rows.map(({ value }) => isAggregateValue(value) ? value : 0))
  return <ul className="hr-bars" aria-label={label}>
    {rows.map((row) => <li key={row.id} className={`hr-bar-row ${row.tone ? `hr-tone-${row.tone}` : ''}`}>
      <div className="hr-bar-label"><span>{row.label}</span>
        <span className="hr-bar-value">{isAggregateValue(row.value)
          ? <><strong>{formatAggregate(row.value)}</strong> <span>{row.value === 1 ? singularUnit : unit}</span></>
          : <span>{copy.hr.unavailable}</span>}
        </span>
      </div>
      {isAggregateValue(row.value) && <div className="hr-bar-track" aria-hidden="true">
        <span className="hr-bar-fill" style={{ width: `${row.value / scale * 100}%` }} />
      </div>}
    </li>)}
  </ul>
}
