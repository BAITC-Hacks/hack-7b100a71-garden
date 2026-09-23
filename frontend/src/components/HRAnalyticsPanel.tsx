import type { ActivityStatus, HRAnalytics } from '../types/domain'

const statuses: Array<{ value: ActivityStatus; label: string }> = [
  { value: 'completed', label: 'Completed' }, { value: 'in_progress', label: 'In progress' },
  { value: 'dropped', label: 'Dropped' }, { value: 'no_show', label: 'No show' },
  { value: 'declined', label: 'Declined' }, { value: 'overdue', label: 'Overdue' },
]

export function HRAnalyticsPanel({ analytics }: { analytics: HRAnalytics }) {
  const coverage = analytics.employees_without_next_step
  return <div className="hr-analytics">
    <div className="hr-summary-grid">
      <section className="surface hr-metric"><h2>Employees</h2><strong>{analytics.employee_count}</strong><p>Active dataset</p></section>
      <section className="surface hr-metric"><h2>Participating employees</h2><strong>{analytics.participation_summary.participating_employees}</strong><p>At least one activity record</p></section>
      <section className="surface hr-metric"><h2>Activity records</h2><strong>{analytics.participation_summary.total_records}</strong><p>Includes repeated attempts</p></section>
    </div>
    <section className="surface hr-section" aria-labelledby="hr-coverage-title">
      <h2 id="hr-coverage-title">Employees without a recommended next step</h2>
      <div className="hr-coverage-value">{coverage.count === null ? 'Not evaluated' : coverage.count}</div>
      <p>{coverage.complete ? 'Complete coverage' : 'Partial coverage'} · {coverage.evaluated_count} evaluated · {coverage.pending_count} pending</p>
      <p className="hr-help">{coverage.available
        ? 'Based on recommendation results already calculated for this dataset version. Pending employees are not counted as having no next step.'
        : 'Recommendation coverage is unavailable. Pending employees have not been evaluated.'}</p>
    </section>
    <section className="surface hr-section" aria-labelledby="hr-gaps-title">
      <h2 id="hr-gaps-title">Common skill gaps</h2>
      <p className="hr-help">Effective skills compared with each employee’s current role and grade. These are not career-target gaps.</p>
      {analytics.gap_basis !== 'effective_skills_against_current_role_and_grade' && <p>Reported gap basis: {analytics.gap_basis}</p>}
      {analytics.common_skill_gaps.length === 0 ? <p className="hr-empty">No current-role skill gaps reported.</p> : <div className="hr-table-scroll">
        <table><caption className="sr-only">Current-role skill gaps</caption><thead><tr>
          <th scope="col">Skill</th><th scope="col">Employees</th><th scope="col">Levels missing</th><th scope="col">Critical for employees</th>
        </tr></thead><tbody>{analytics.common_skill_gaps.map((gap) => <tr key={gap.skill_id}>
          <th scope="row">{gap.skill_name}<small>{gap.category} · {gap.skill_id}</small></th>
          <td>{gap.employee_count}</td><td>{gap.total_levels_missing}</td><td>{gap.critical_employee_count}</td>
        </tr>)}</tbody></table>
      </div>}
    </section>
    <section className="surface hr-section" aria-labelledby="hr-participation-title">
      <h2 id="hr-participation-title">Activity participation</h2>
      <p className="hr-help">History record counts by status, including repeated activities.</p>
      <div className="hr-table-scroll"><table><caption className="sr-only">Activity status totals</caption><thead><tr>
        <th scope="col">Status</th><th scope="col">All</th><th scope="col">Voluntary</th><th scope="col">Mandatory</th>
      </tr></thead><tbody>{statuses.map(({ value, label }) => <tr key={value}>
        <th scope="row">{label}</th><td>{analytics.activity_participation[value]}</td>
        <td>{analytics.participation_summary.voluntary[value]}</td><td>{analytics.participation_summary.mandatory[value]}</td>
      </tr>)}</tbody></table></div>
      {(analytics.version !== undefined || analytics.asOf) && <p className="hr-help">Dataset version {analytics.version ?? 'not provided'}{analytics.asOf ? ` · Snapshot date ${analytics.asOf}` : ''}</p>}
    </section>
  </div>
}
