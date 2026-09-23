import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import type { ReactNode } from 'react'
import type { CareerTrajectory as Trajectory, Employee, Recommendation, SkillGap } from '../types/domain'
import { CareerReadiness } from './CareerReadiness'
import { CareerTrajectory } from './CareerTrajectory'
import { EmployeeProfile } from './EmployeeProfile'
import { RecommendationList } from './RecommendationList'
import { SkillGapList } from './SkillGapList'
import { formatReadiness } from '../utils/formatReadiness'

const employee: Employee = {
  id: 'test-profile', name: 'Test Employee', role: 'Data Analyst', grade: 'Middle',
  department: 'Analytics', preferredLanguage: 'en', skills: [],
}
const target = { role: 'Product Manager', grade: 'Middle' }
const text = (element: ReactNode) => renderToStaticMarkup(element).replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ')

describe('dashboard presentation boundaries', () => {
  it.each([0, 0.67, 1])('displays supplied readiness %s, including zero', (current) => {
    const html = renderToStaticMarkup(<CareerReadiness readiness={{ current }} target={target} />)
    expect(html).toContain(`aria-valuenow="${current}"`)
    expect(html).toContain('aria-valuemax="1"')
    expect(html).not.toContain('Readiness not available')
  })

  it.each([null, { current: 67 }, { current: -1 }])('does not invent or repair unavailable readiness %s', (readiness) => {
    const html = renderToStaticMarkup(<CareerReadiness readiness={readiness} target={null} />)
    expect(html).toContain('Readiness not available')
    expect(html).not.toContain('role="meter"')
  })

  it('shows the exact gap and critical flag instead of deriving them from levels', () => {
    const skill: SkillGap = { id: 'test', name: 'Provided gap', current: 2, required: 4, gap: 17, scaleMax: 5, critical: false }
    const output = text(<SkillGapList skills={[skill]} />)
    expect(output).toContain('Current 2 Required 4 Gap 17')
    expect(output).toContain('Standard')
    expect(output).not.toContain('Critical')
  })

  it('does not assume a five-point skill scale', () => {
    const skill: SkillGap = { id: 'test', name: 'Custom scale', current: 20, required: 80, gap: 60, scaleMax: 100, critical: true }
    const html = renderToStaticMarkup(<SkillGapList skills={[skill]} />)
    expect(html).toContain('width:20%')
    expect(html).toContain('width:80%')
    expect(html).toContain('Critical')
  })

  it('preserves recommendation ordering even when scores disagree, and limits the preview to three', () => {
    const recommendations: Recommendation[] = ['First from API', 'Second from API', 'Third from API', 'Fourth from API'].map((title, index) => ({
      eventId: String(index), title, type: 'Course', durationMinutes: 60, score: index / 4,
      careerImpact: null, skillImpact: [], readinessBefore: null, readinessAfter: null,
      explanation: { text: null, factors: [] },
    }))
    const originalOrder = recommendations.map((item) => item.eventId)
    const output = text(<RecommendationList recommendations={recommendations} />)
    expect(output.indexOf('First from API')).toBeLessThan(output.indexOf('Second from API'))
    expect(output.indexOf('Second from API')).toBeLessThan(output.indexOf('Third from API'))
    expect(output).not.toContain('Fourth from API')
    expect(recommendations.map((item) => item.eventId)).toEqual(originalOrder)
  })

  it('uses the supplied same-grade transition target', () => {
    const output = text(<CareerTrajectory employee={employee} target={target} trajectory={{ kind: 'transition', positions: [] }} />)
    expect(output).toContain('Career transition')
    expect(output).toContain('Data Analyst')
    expect(output).toContain('Product Manager')
    expect(output).not.toContain('Senior')
  })

  it('does not manufacture a next grade for a Lead without a target', () => {
    const output = text(<CareerTrajectory employee={{ ...employee, grade: 'Lead' }} target={null} trajectory={null} />)
    expect(output).toContain('Lead')
    expect(output).toContain('Your next direction is open')
    expect(output).not.toContain('Your target')
  })

  it('distinguishes failed or loading target data from an explicitly absent target', () => {
    expect(text(<EmployeeProfile employee={employee} target={undefined} isTargetPending />)).toContain('Loading your target')
    expect(text(<EmployeeProfile employee={employee} target={undefined} isTargetPending={false} />)).toContain('Target unavailable')
    expect(text(<EmployeeProfile employee={employee} target={null} isTargetPending={false} />)).toContain('No target set')
  })

  it('only displays tenure when supplied and renders independent empty sections', () => {
    expect(text(<EmployeeProfile employee={employee} target={null} isTargetPending={false} />)).not.toContain('With the team')
    expect(text(<EmployeeProfile employee={{ ...employee, tenureLabel: '18 months' }} target={null} isTargetPending={false} />)).toContain('18 months')
    expect(text(<SkillGapList skills={[]} />)).toContain('No skill gaps to show')
    expect(text(<RecommendationList recommendations={[]} />)).toContain('No recommendations yet')
  })

  it.each([[0.675, '67.5%'], [0.9999, '99.99%'], [0.12345678912345678, '12.345678912345678%']])(
    'preserves supplied fractional readiness %s in the visible percentage', (current, expected) => {
      const readiness = { current: Number(current) }
      const html = renderToStaticMarkup(<CareerReadiness readiness={readiness} target={target} />)
      expect(html).toContain(`aria-valuetext="${expected}"`)
      expect(html).toContain(`aria-valuenow="${current}"`)
      expect(readiness.current).toBe(current)
    },
  )

  it('formats tiny supplied values without silently rounding them to zero', () => {
    expect(formatReadiness(1e-30)).toBe('1E-28%')
    expect(formatReadiness(0)).toBe('0%')
  })

  it('does not imply a target when an assessment exists without one', () => {
    const output = text(<CareerReadiness readiness={{ current: 0.42 }} target={null} />)
    expect(output).toContain('42%')
    expect(output).toContain('Current assessment')
    expect(output).not.toContain('toward your target')
  })

  it('shows a supplied activity projection independently of the current assessment', () => {
    const projection = { title: 'Activity from API', readinessBefore: 0.675, readinessAfter: 0.7925 }
    const original = { ...projection }
    const element = <CareerReadiness readiness={{ current: 0.42 }} target={target} projection={projection} />
    const output = text(element)
    expect(output).toContain('42%')
    expect(output).toContain('Activity readiness projection Activity from API Before activity 67.5% Projected after 79.25%')
    expect(renderToStaticMarkup(element)).toContain('aria-valuenow="0.42"')
    expect(projection).toEqual(original)
  })

  it.each([
    null,
    undefined,
    { title: 'Incomplete', readinessBefore: null, readinessAfter: 0.79 },
    { title: 'Incomplete', readinessBefore: 0.67, readinessAfter: null },
    { title: 'Invalid', readinessBefore: 67, readinessAfter: 0.79 },
    { title: 'Invalid', readinessBefore: 0.67, readinessAfter: -1 },
    { title: 'Invalid', readinessBefore: 0.67, readinessAfter: NaN },
  ])('omits missing or invalid before/after pairs without inventing a value: %s', (projection) => {
    const output = text(<CareerReadiness readiness={{ current: 0.67 }} target={target} projection={projection} />)
    expect(output).toContain('67%')
    expect(output).not.toContain('Activity readiness projection')
    expect(output).not.toContain('Projected after')
  })

  it('preserves zero and a lower supplied projection without assuming improvement', () => {
    const output = text(<CareerReadiness readiness={{ current: 0.67 }} target={target}
      projection={{ title: 'Unmodified projection', readinessBefore: 0.67, readinessAfter: 0 }} />)
    expect(output).toContain('Before activity 67% Projected after 0%')
  })

  it('does not substitute an activity projection for missing current readiness', () => {
    const element = <CareerReadiness readiness={null} target={target}
      projection={{ title: 'Provided activity', readinessBefore: 0, readinessAfter: 0.42 }} />
    expect(text(element)).toContain('Readiness not available')
    expect(text(element)).toContain('Before activity 0% Projected after 42%')
    expect(renderToStaticMarkup(element)).not.toContain('role="meter"')
  })

  it('renders every supplied trajectory position and state in order without changing them', () => {
    const trajectory: Trajectory = { kind: 'transition', positions: [
      { role: 'Research Assistant', grade: 'Junior', state: 'past' },
      { ...employee, state: 'current' },
      { role: 'Product Analyst', grade: 'Middle', state: 'intermediate' },
      { ...target, state: 'target' },
      { role: 'Product Director', grade: 'Lead', state: 'future' },
    ] }
    const before = JSON.stringify(trajectory)
    const element = <CareerTrajectory employee={employee} target={target} trajectory={trajectory} />
    const output = text(element)
    const roles = trajectory.positions.map((position) => position.role)
    roles.forEach((role, index) => {
      expect(output).toContain(role)
      if (index > 0) expect(output.indexOf(roles[index - 1])).toBeLessThan(output.indexOf(role))
    })
    expect(output).toContain('Intermediate position')
    expect(output).toContain('You are here')
    expect(output).toContain('Your target')
    expect(output).toContain('Further along')
    expect(renderToStaticMarkup(element).match(/aria-current="step"/g)).toHaveLength(1)
    expect(JSON.stringify(trajectory)).toBe(before)
  })

  it.each([null, { kind: 'transition' as const, positions: [] }])('shows missing trajectory %s without drawing an invented path', (trajectory) => {
    const element = <CareerTrajectory employee={employee} target={target} trajectory={trajectory} />
    const output = text(element)
    expect(output).toContain('Trajectory not available')
    expect(output).toContain('Data Analyst')
    expect(output).toContain('Product Manager')
    expect(renderToStaticMarkup(element)).not.toContain('aria-label="Career trajectory positions"')
  })

  it('keeps a partial supplied path intact and shows missing anchors as separate facts', () => {
    const element = <CareerTrajectory employee={employee} target={target} trajectory={{ kind: 'transition', positions: [
      { role: 'Product Analyst', grade: 'Middle', state: 'intermediate' },
    ] }} />
    const html = renderToStaticMarkup(element)
    expect(html).toContain('Available position details')
    expect(text(element)).toContain('Data Analyst')
    expect(text(element)).toContain('Product Manager')
    expect(html.match(/<li /g)).toHaveLength(1)
    expect(html).not.toContain('aria-current="step"')
  })

  it('shows scaleMax and fractional levels as supplied', () => {
    const output = text(<SkillGapList skills={[{ id: 'custom', name: 'Custom scale', current: 6.5, required: 8, gap: 1.5, critical: true, scaleMax: 10 }]} />)
    expect(output).toContain('Current 6.5 Required 8 Gap 1.5')
    expect(output).toContain('Scale maximum 10')
  })

  it.each([undefined, null])('keeps numbers visible without assuming a missing scale %s', (scaleMax) => {
    const element = <SkillGapList skills={[{ id: 'unscaled', name: 'Unscaled skill', current: 2, required: 4, gap: 7, critical: false, scaleMax }]} />
    expect(text(element)).toContain('Current 2 Required 4 Gap 7')
    expect(text(element)).toContain('Scale not provided')
    expect(text(element)).not.toContain('Scale maximum')
    expect(renderToStaticMarkup(element)).not.toContain('skill-comparison')
  })

  it('does not clamp out-of-scale values or rewrite supplied gaps', () => {
    const element = <SkillGapList skills={[{ id: 'invalid', name: 'Outside scale', current: 12, required: 8, gap: 3, critical: true, scaleMax: 10 }]} />
    expect(text(element)).toContain('Current 12 Required 8 Gap 3')
    expect(text(element)).toContain('Scale maximum 10')
    expect(text(element)).toContain('Level comparison unavailable')
    expect(renderToStaticMarkup(element)).not.toContain('skill-comparison')
  })
})
