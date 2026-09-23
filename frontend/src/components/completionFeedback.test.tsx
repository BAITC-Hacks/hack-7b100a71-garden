import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { CompletionFeedback } from './CompletionFeedback'
import { canRetryCompletion, idleCompletion, type CompletionState } from '../types/completion'
import type { ApiErrorCode } from '../types/api'

function feedback(errorCode: ApiErrorCode) {
  const state: CompletionState = { ...idleCompletion, phase: 'error', eventId: 'activity', title: 'Development activity', errorCode }
  return { state, html: renderToStaticMarkup(<CompletionFeedback state={state} onRetry={() => {}} onRefresh={() => {}} />) }
}

describe('completion failure recovery guidance', () => {
  it.each(['NETWORK', 'TIMEOUT', 'INVALID_RESPONSE', 'UNAVAILABLE'] as const)('allows a stable-key retry for %s', (code) => {
    const { state, html } = feedback(code)
    expect(canRetryCompletion(state)).toBe(true)
    expect(html).toContain('Retry completion')
    if (code !== 'UNAVAILABLE') {
      expect(html).toContain('Completion could not be confirmed')
      expect(html).toContain('without recording it twice')
    }
  })

  it.each([
    ['AUTHENTICATION', 'Change access token'], ['FORBIDDEN', 'appropriate access token'],
    ['CONFLICT', 'activity records'], ['VALIDATION', 'activity and employee details'],
    ['CONFIGURATION', 'API connection settings'], ['NOT_FOUND', 'Choose another profile'],
  ] as const)('gives specific guidance for %s without offering an unsupported retry', (code, guidance) => {
    const { state, html } = feedback(code)
    expect(canRetryCompletion(state)).toBe(false)
    expect(html).toContain(guidance)
    expect(html).not.toContain('Retry completion')
    expect(html).not.toContain('You can retry this activity')
  })

  it('offers only a read-only refresh when a recommendation is no longer available', () => {
    const { state, html } = feedback('RECOMMENDATION_UNAVAILABLE')
    expect(canRetryCompletion(state)).toBe(false)
    expect(html).toContain('Retry refresh')
    expect(html).not.toContain('Retry completion')
  })
})
