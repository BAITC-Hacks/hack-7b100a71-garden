import { renderToStaticMarkup } from 'react-dom/server'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import type { Recommendation } from '../types/domain'
import { ActivityImpact } from './ActivityImpact'
import { ReadinessImpact } from './ReadinessImpact'
import { RecommendationCard } from './RecommendationCard'
import { RecommendationList } from './RecommendationList'

const recommendation: Recommendation = {
  eventId: 'supplied', title: 'Supplied activity', type: 'Workshop', durationMinutes: 120,
  careerImpact: 'High', score: 0.13,
  skillImpact: [{ skillId: 'system-design', name: 'System Design', current: 2, after: 3, required: 4, critical: true, gain: 17 }],
  readinessBefore: 0.675, readinessAfter: 0.7925,
  explanation: { text: 'The supplied explanation.', factors: [
    { id: 'first', label: 'Supplied factor first', value: 0 },
    { id: 'second', label: 'Supplied factor second', value: -1.25 },
  ] },
}
const text = (element: ReactNode) => renderToStaticMarkup(element).replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ')

describe('recommendation presentation', () => {
  it('renders supplied evidence unchanged, including gain that cannot be inferred from levels', () => {
    const original = structuredClone(recommendation)
    const output = text(<RecommendationCard recommendation={recommendation} target={{ role: 'Engineer', grade: 'Senior' }} />)
    expect(output).toContain('Current 2 Expected after 3 Target 4')
    expect(output).toContain('Activity gain 17')
    expect(output).toContain('Before activity 67.5% Projected after 79.25%')
    expect(output).toContain('Critical')
    expect(output).toContain('Engineer · Senior')
    expect(output).toContain('Supplied factor first 0 Supplied factor second -1.25')
    expect(output).not.toContain('-125%')
    expect(recommendation).toEqual(original)
  })

  it('uses a native disclosure that starts collapsed', () => {
    const html = renderToStaticMarkup(<RecommendationCard recommendation={recommendation} />)
    expect(html).toContain('<details class="recommendation-explanation"><summary>')
    expect(html).not.toContain('<details open')
    expect(html).toContain('Why this recommendation?')
  })

  it('keeps structured evidence when the entire explanation is absent', () => {
    const output = text(<RecommendationCard recommendation={{ ...recommendation, explanation: null }} />)
    expect(output).toContain('Current 2 Expected after 3 Target 4')
    expect(output).toContain('67.5%')
    expect(output).toContain('No written explanation was provided')
    expect(output).toContain('A factor breakdown has not been provided')
  })

  it('supports a recommendation with only identity and title', () => {
    const output = text(<RecommendationCard recommendation={{ eventId: 'minimal', title: 'Minimal activity' }} />)
    expect(output).toContain('Minimal activity')
    expect(output).toContain('Skill impact has not been provided')
    expect(output).toContain('Readiness impact has not been provided')
    expect(output).not.toContain('undefined')
    expect(output).not.toContain('NaN')
    expect(output).not.toContain('0%')
  })

  it('does not infer skill values, gain, or critical status for a partial skill', () => {
    const output = text(<ActivityImpact expanded skills={[{ skillId: 'partial', name: 'Partial skill', current: 0, required: 4 }]} />)
    expect(output).toContain('Current 0 Expected after Not provided Target 4')
    expect(output).not.toContain('Activity gain')
    expect(output).not.toContain('Critical')
    expect(output).not.toContain('Standard')
  })

  it.each([undefined, null, []])('handles missing skill arrays: %s', (skills) => {
    expect(text(<ActivityImpact skills={skills} />)).toContain('Skill impact has not been provided')
  })

  it.each([
    [0, undefined, 'Before activity 0% Projected after Not provided'],
    [null, 0.42, 'Before activity Not provided Projected after 42%'],
    [0.67, 0.3, 'Before activity 67% Projected after 30%'],
    [67, 0, 'Before activity Not provided Projected after 0%'],
  ] as const)('does not derive the missing readiness side or enforce improvement', (before, after, expected) => {
    expect(text(<ReadinessImpact before={before} after={after} />)).toContain(expected)
  })

  it('keeps long explanation text intact and safely escapes markup', () => {
    const explanation = `${'Long supplied evidence. '.repeat(120)}<script>not executable</script>`
    const html = renderToStaticMarkup(<RecommendationCard recommendation={{ ...recommendation, explanation: { text: explanation } }} />)
    expect(html).toContain('Long supplied evidence. '.repeat(120))
    expect(html).toContain('&lt;script&gt;not executable&lt;/script&gt;')
    expect(html).not.toContain('<script>')
  })

  it('keeps actions disabled without a handler and does not call a provided handler during rendering', () => {
    const disabled = renderToStaticMarkup(<RecommendationCard recommendation={recommendation} />)
    expect(disabled).toContain('disabled=""')
    expect(disabled).toContain('aria-describedby=')
    const onStart = vi.fn()
    const enabled = renderToStaticMarkup(<RecommendationList recommendations={[recommendation]} onStart={onStart} />)
    expect(enabled).not.toContain('disabled=""')
    expect(enabled).not.toContain('Starting an activity is not available yet')
    expect(onStart).not.toHaveBeenCalled()
  })

  it('preserves the first three entries and primary styling even when the first entry lacks optional fields', () => {
    const items: Recommendation[] = [
      { eventId: 'one', title: 'First supplied' },
      { ...recommendation, eventId: 'two', title: 'Second supplied', score: 1 },
      { ...recommendation, eventId: 'three', title: 'Third supplied', score: 0 },
      { ...recommendation, eventId: 'four', title: 'Fourth supplied', score: 0.5 },
    ]
    const original = structuredClone(items)
    const html = renderToStaticMarkup(<RecommendationList recommendations={items} />)
    expect(html.indexOf('First supplied')).toBeLessThan(html.indexOf('Second supplied'))
    expect(html.indexOf('Second supplied')).toBeLessThan(html.indexOf('Third supplied'))
    expect(html).not.toContain('Fourth supplied')
    expect(html.match(/recommendation-primary/g)).toHaveLength(1)
    expect(items).toEqual(original)
  })
})
