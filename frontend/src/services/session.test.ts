import { afterEach, describe, expect, it, vi } from 'vitest'
import { queryClient } from './queryClient'
import { canAccessEmployee, getSession, sessionHome, setSession, subscribeSession } from './session'

afterEach(() => setSession(null))

describe('memory-only identity boundary', () => {
  it('keeps a token opaque and only allows an employee their own profile', () => {
    const employee = { role: 'employee' as const, employeeId: 'jury/id ?42', token: 'opaque.test-token' }
    setSession(employee)
    expect(getSession()).toEqual(employee)
    expect(Object.isFrozen(getSession())).toBe(true)
    expect(sessionHome(employee)).toBe('/employees/jury%2Fid%20%3F42')
    expect(canAccessEmployee(employee, employee.employeeId)).toBe(true)
    expect(canAccessEmployee(employee, 'other')).toBe(false)
    expect(canAccessEmployee(null, employee.employeeId)).toBe(false)
    expect(canAccessEmployee({ role: 'hr', token: 'test-hr' }, 'other')).toBe(true)
  })

  it('notifies subscribers and clears all cached data on identity changes', () => {
    const listener = vi.fn()
    const unsubscribe = subscribeSession(listener)
    queryClient.setQueryData(['hr-analytics'], { sensitive: true })
    setSession({ role: 'employee', employeeId: 'jury-profile', token: 'test-token' })
    expect(queryClient.getQueryData(['hr-analytics'])).toBeUndefined()
    expect(listener).toHaveBeenCalledTimes(1)
    unsubscribe()
    setSession(null)
    expect(listener).toHaveBeenCalledTimes(1)
    expect(getSession()).toBeNull()
  })

  it('cancels pending queries before another identity can inherit their results', async () => {
    let cancelled = false
    const pending = queryClient.fetchQuery({ queryKey: ['sensitive-pending'], queryFn: ({ signal }) => new Promise((_, reject) => {
      signal.addEventListener('abort', () => { cancelled = true; reject(new Error('cancelled')) })
    }) }).catch(() => undefined)
    setSession({ role: 'hr', token: 'test-new-token' })
    await pending
    expect(cancelled).toBe(true)
    expect(queryClient.getQueryData(['sensitive-pending'])).toBeUndefined()
  })

  it.each(['', 'token with spaces', '\ntoken'])('rejects invalid token %j without changing identity', (token) => {
    setSession({ role: 'hr', token: 'previous-test-token' })
    expect(() => setSession({ role: 'hr', token })).toThrow('token')
    expect(getSession()?.token).toBe('previous-test-token')
  })

  it('rejects an empty employee ID', () => {
    expect(() => setSession({ role: 'employee', token: 'test-token', employeeId: '  ' })).toThrow('employee ID')
  })
})
