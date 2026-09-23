import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { HRAnalytics } from '../types/domain'
import { HRAnalyticsPanel } from './HRAnalyticsPanel'

const counts = { completed: 21, in_progress: 4, dropped: 2, no_show: 3, declined: 1, overdue: 8 }
const analytics: HRAnalytics = {
  employee_count: 250,
  gap_basis: 'effective_skills_against_current_role_and_grade',
  common_skill_gaps: [{ skill_id: 'skill-new', skill_name: 'Imported skill', category: 'Engineering', employee_count: 14, total_levels_missing: 19, critical_employee_count: 11 }],
  employees_without_next_step: { available: true, count: null, evaluated_count: 0, pending_count: 250, complete: false },
  activity_participation: counts,
  participation_summary: { total_records: 39, participating_employees: 17, voluntary: counts, mandatory: { completed: 0, in_progress: 0, dropped: 0, no_show: 0, declined: 0, overdue: 0 } },
  version: 5, asOf: '2026-10-01',
}
const text = (value: HRAnalytics) => renderToStaticMarkup(<HRAnalyticsPanel analytics={value} />).replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ')

describe('HR aggregate presentation', () => {
  it('preserves unknown coverage and pending employees without inventing a zero total', () => {
    const output = text(analytics)
    expect(output).toContain('Not evaluated')
    expect(output).toContain('Partial coverage · 0 evaluated · 250 pending')
    expect(output).toContain('Pending employees are not counted')
    expect(output).not.toContain('participation rate')
    expect(output).not.toContain('employees in development')
  })
  it('shows a known zero separately from pending coverage', () => {
    const output = text({ ...analytics, employees_without_next_step: { available: true, count: 0, evaluated_count: 3, pending_count: 247, complete: false } })
    expect(output).toContain('next step 0 Partial coverage · 3 evaluated · 247 pending')
    expect(output).not.toContain('Not evaluated')
  })
  it('marks complete and unavailable coverage explicitly', () => {
    expect(text({ ...analytics, employees_without_next_step: { available: true, count: 8, evaluated_count: 250, pending_count: 0, complete: true } })).toContain('8 Complete coverage · 250 evaluated · 0 pending')
    expect(text({ ...analytics, employees_without_next_step: { ...analytics.employees_without_next_step, available: false } })).toContain('Recommendation coverage is unavailable')
  })
  it('renders exact current-role gaps and participation counts, including imported IDs', () => {
    const before = JSON.stringify(analytics)
    const output = text(analytics)
    expect(output).toContain('current role and grade')
    expect(output).toContain('not career-target gaps')
    expect(output).toContain('Imported skill Engineering · skill-new 14 19 11')
    expect(output).toContain('Completed 21 21 0')
    expect(output).toContain('In progress 4 4 0')
    expect(output).toContain('Overdue 8 8 0')
    expect(output).toContain('Dataset version 5 · Snapshot date 2026-10-01')
    expect(JSON.stringify(analytics)).toBe(before)
  })
})
