import { describe, expect, it, vi } from 'vitest'
import type { CompletionReceipt } from '../types/domain'
import { createCompletionAction, runCompletionAction } from './completionAction'

const receipt: CompletionReceipt = {
  activity: { record_id: 'runtime-1', employee_id: 'jury-profile', event_id: 'event-a', date: '2026-10-01', due_date: null,
    status: 'completed', completion_pct: 100, score: null, feedback_rating: null, assigned_by: 'self' },
  effective_skills: { api: 3 }, skill_changes: [{ skill_id: 'api', before: 2, after: 3, gain: 1, event_gain: 1, max_level: 3 }], version: 2, replayed: false,
}

describe('completion action boundary', () => {
  it('reuses one idempotency key after an uncertain failure and refreshes only on confirmation', async () => {
    const createKey = vi.fn(() => 'action-key')
    const action = createCompletionAction('jury-profile', 'event-a', createKey)
    const submit = vi.fn().mockRejectedValueOnce(new Error('Connection lost')).mockResolvedValueOnce({ ...receipt, replayed: true })
    const refresh = vi.fn().mockResolvedValue(undefined)
    await expect(runCompletionAction(action, { submit, refresh })).rejects.toThrow('Connection lost')
    expect(refresh).not.toHaveBeenCalled()
    const actual = await runCompletionAction(action, { submit, refresh })
    expect(createKey).toHaveBeenCalledTimes(1)
    expect(submit.mock.calls).toEqual([
      ['jury-profile', 'event-a', { idempotencyKey: 'action-key' }],
      ['jury-profile', 'event-a', { idempotencyKey: 'action-key' }],
    ])
    expect(actual).toEqual({ ...receipt, replayed: true })
    expect(refresh).toHaveBeenCalledExactlyOnceWith('jury-profile')
  })

  it('does not derive a gain or rewrite the supplied receipt', async () => {
    const submit = vi.fn().mockResolvedValue(receipt)
    const refresh = vi.fn().mockImplementation(async () => { expect(submit).toHaveBeenCalledTimes(1) })
    const actual = await runCompletionAction(createCompletionAction('jury-profile', 'event-a', () => 'unique'), { submit, refresh })
    expect(actual).toBe(receipt)
    expect(actual.effective_skills.api).toBe(3)
  })
})
