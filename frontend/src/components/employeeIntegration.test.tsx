import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { ReactNode } from 'react'
import type { Employee, Recommendation } from '../types/domain'
import type { ExplanationDTO, RankedRecommendationDTO } from '../types/transport'
import { EmployeeProfile } from './EmployeeProfile'
import { RecommendationCard } from './RecommendationCard'
import { RecommendationList } from './RecommendationList'
import { ActivityHistory } from './ActivityHistory'
import { SkillGapList } from './SkillGapList'

const text = (element: ReactNode) => renderToStaticMarkup(element).replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ')
const employee: Employee = { id: 'jury-profile', name: 'New Profile', role: 'Backend Engineer', grade: 'Junior', department: 'Engineering', preferredLanguage: 'kk', skills: [{ id: 'api', name: 'API Design', current: 3, scaleMax: 5 }], assessmentSkills: { api: 2 }, workFormat: 'hybrid' }
const recommendation: Recommendation = { eventId: 'ev-1', title: 'Backend supplied title', type: 'course', durationMinutes: 90, format: 'online', careerImpact: 'Do not render a mock label', score: .2, skillImpact: [{ skillId: 'api', name: 'API Design', current: 2, after: 3, required: 3, critical: true }], readinessBefore: .42105263157894735, readinessAfter: .5263157894736842, rank: 3, explanation: { text: 'From the backend', factors: [{ id: 'impact', label: 'impact', value: .7 }], language: 'en', source: 'deterministic' } }

describe('real employee UI presentation', () => {
  it('renders effective skills, work format and language without substituting assessment skills', () => {
    const html = renderToStaticMarkup(<EmployeeProfile employee={employee} target={null} isTargetPending={false} />)
    expect(text(<EmployeeProfile employee={employee} target={null} isTargetPending={false} />)).toContain('API Design 3 / 5')
    expect(html).toContain('hybrid')
    expect(html).toContain('KK')
    expect(html).not.toContain('API Design 2')
  })

  it.each(['kk', 'ru', 'en'] as const)('renders unchanged backend explanation in %s', (language) => {
    const original = { ...recommendation, explanation: { ...recommendation.explanation, language, text: `Backend ${language} explanation: 2 → 3.` } }
    const html = renderToStaticMarkup(<RecommendationCard recommendation={original} position={1} onComplete={() => {}} />)
    expect(html).toContain(`lang="${language}"`)
    expect(html).toContain(original.explanation.text)
    expect(html).toContain('aria-label="Rank 3"')
    expect(html).toContain('42.11%')
    expect(html).toContain('52.63%')
    expect(html).not.toContain(original.careerImpact)
  })

  it.each(['no_next_grade', 'target_satisfied', 'no_eligible_recommendations'] as const)('renders normal HTTP 200 state %s as a non-error result', (status) => {
    const summary: ExplanationDTO = { language: 'ru', source: 'deterministic', text: `Состояние ${status}`, facts: [], segments: [] }
    const html = renderToStaticMarkup(<RecommendationList recommendations={[]} status={status} summary={summary} />)
    expect(html).toContain(status)
    expect(html).toContain(summary.text)
    expect(html).not.toContain('role="alert"')
    expect(html).not.toContain('Complete activity')
  })

  it('renders explicit destination-role admission and raw evidence intact', () => {
    const raw = { evidence: { audience_match: 'target_role', attained_grade: 'Middle', target_role: 'Product Manager', useful_marker: 'jury-evidence' } } as unknown as RankedRecommendationDTO
    const html = renderToStaticMarkup(<RecommendationCard recommendation={{ ...recommendation, raw }} position={1} />)
    expect(html).toContain('target_role')
    expect(html).toContain('Middle')
    expect(html).toContain('jury-evidence')
    expect(html).not.toContain('High career impact')
  })

  it('shows supplied satisfied requirements and positive gaps separately', () => {
    const html = text(<SkillGapList skills={[
      { id: 'api', name: 'API Design', current: 3, required: 3, gap: 0, critical: true, scaleMax: 5 },
      { id: 'sql', name: 'SQL', current: 1, required: 3, gap: 2, critical: false, scaleMax: 5 },
    ]} />)
    expect(html).toContain('1 satisfied requirements · 1 remaining gaps')
    expect(html).toContain('Critical · Satisfied')
    expect(html).toContain('Current 1 Required 3 Gap 2')
  })

  it('keeps repeated activities as separate records and labels actual versus logical completion', () => {
    const html = renderToStaticMarkup(<ActivityHistory records={[
      { id: 'attempt-1', eventId: 'event-a', status: 'dropped', updatedAt: '2026-01-02', date: '2026-01-02', completionPct: 40 },
      { id: 'attempt-2', eventId: 'event-a', status: 'completed', updatedAt: '2026-09-23T08:00:00Z', date: '2026-10-01', completedAt: '2026-09-23T08:00:00Z', completedOn: '2026-10-01', completionPct: 100 },
    ]} />)
    expect(html).toContain('attempt-1')
    expect(html).toContain('attempt-2')
    expect(html).toContain('Logical day: 2026-10-01')
    expect(html).toContain('2026-09-23T08:00:00Z')
  })
})
