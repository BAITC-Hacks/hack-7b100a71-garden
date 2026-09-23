import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { AssessmentNotes } from './AssessmentNotes'
import { RecommendationExplanation } from './RecommendationExplanation'
import { HRNextStep, HRParticipation } from './hr/HRInsights'
import type { CareerOverview } from '../types/domain'

describe('real contract presentation', () => {
  it('retains structured evidence and distinct factor values without generated prose', () => {
    const html = renderToStaticMarkup(<RecommendationExplanation recommendation={{ eventId: 'contract-event', title: 'Supplied event',
      explanation: { factors: [{ id: 'coverage', label: 'Coverage', raw: 3, normalized: 0.5, weight: 0.4, contribution: 0.2 }],
        facts: [{ id: 'f1', code: 'skill_improvement', values: { current: 0, critical: false }, evidencePaths: [] }] },
      supportingEvidence: [{ id: 'history', label: 'History signals', values: { records: ['supplied-record'], nested: { count: 0 } } }],
    }} />)
    for (const label of ['Raw value', 'Normalized', 'Weight', 'Contribution', 'Supplied evidence', 'Skill improvement', 'supplied-record']) expect(html).toContain(label)
    expect(html).toContain('0.5'); expect(html).toContain('0.4'); expect(html).toContain('0.2')
    expect(html).toContain('No'); expect(html).not.toContain('[object Object]')
  })
  it('presents estimated-skill caveats verbatim when supplied', () => {
    const overview: CareerOverview = { employeeId: 'e', readiness: null, target: null, trajectory: null, skillGaps: [], recommendations: [],
      skillsEstimated: true, summary: 'Supplied summary', warnings: [{ code: 'history', message: 'Supplied caveat.' }] }
    const html = renderToStaticMarkup(<AssessmentNotes overview={overview} />)
    expect(html).toContain('Skills are estimated'); expect(html).toContain('Supplied caveat.'); expect(html).toContain('Supplied summary')
    expect(renderToStaticMarkup(<AssessmentNotes overview={{ ...overview, skillsEstimated: false, summary: undefined, warnings: [] }} />)).toBe('')
  })
  it('labels partial next-step coverage without treating it as an organization-wide count', () => {
    const html = renderToStaticMarkup(<HRNextStep count={0} coverage={{ available: true, complete: false, evaluatedCount: 2, pendingCount: 8 }} />)
    expect(html).toContain('Coverage assessment is incomplete'); expect(html).toContain('Employees evaluated'); expect(html).toContain('Employees pending evaluation')
    expect(html).toContain('>0<'); expect(html).toContain('>2<'); expect(html).toContain('>8<')
  })
  it('shows supplied participation counts without deriving a rate', () => {
    const html = renderToStaticMarkup(<HRParticipation activities={undefined} rate={undefined} participatingEmployees={7} recordCount={12} />)
    expect(html).toContain('Participating employees'); expect(html).toContain('Participation records')
    expect(html).toContain('>7<'); expect(html).toContain('>12<'); expect(html).not.toContain('role="meter"')
  })
})
