// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { CareerOverview, CompletionReceipt, Employee, Recommendation } from '../types/domain'
import { ApiError } from '../types/api'
import { EmployeeWorkspace } from './EmployeeWorkspace'

const mocks = vi.hoisted(() => ({ getEmployee: vi.fn(), getRecommendations: vi.fn(), getEmployeeHistory: vi.fn(), completeActivity: vi.fn(), getEmployees: vi.fn() }))
vi.mock('../services/api', () => ({ api: mocks }))
vi.mock('../hooks/useSession', () => ({ useSession: () => ({ role: 'employee', employeeId: 'jury-profile', token: 'test-opaque-token' }) }))

let completed = false
const employee = (): Employee => ({ id: 'jury-profile', name: 'New Employee', role: 'Backend Engineer', grade: 'Junior', department: 'Engineering', preferredLanguage: 'kk', skills: [
  { id: 'api', name: 'API Design', current: completed ? 3 : 2, scaleMax: 5 }, { id: 'system', name: 'System Design', current: completed ? 2 : 1, scaleMax: 5 },
], version: completed ? 2 : 1 })
const recommendation = (eventId: string, title: string, rank: number): Recommendation => ({ eventId, title, rank, type: 'course', format: 'online', durationMinutes: 60, careerImpact: null, score: .8, skillImpact: [], readinessBefore: .5897435897435898, readinessAfter: .6666666666666666, explanation: { text: 'Мақсат талаптарына қатысты ұсыныс.', factors: [], language: 'kk', source: 'deterministic' } })
const career = (): CareerOverview => ({ employeeId: 'jury-profile', target: { role: 'Backend Engineer', grade: 'Middle' }, trajectory: null, readiness: { current: completed ? .6666666666666666 : .5897435897435898 }, skillGaps: [], targetRequirements: [], recommendations: completed ? [recommendation('EV_036', 'Feedback Practice', 1)] : [recommendation('EV_005', 'System Design Fundamentals', 1), recommendation('EV_036', 'Feedback Practice', 2)], version: completed ? 2 : 1, status: 'ok' })
const receipt: CompletionReceipt = { activity: { record_id: 'runtime-1', employee_id: 'jury-profile', event_id: 'EV_005', date: '2026-10-01', due_date: null, status: 'completed', completion_pct: 100, score: null, feedback_rating: null, assigned_by: 'self', completed_at: '2026-09-23T08:00:00Z', completed_on: '2026-10-01', runtime_sequence: 1 }, effective_skills: { api: 3, system: 2 }, skill_changes: [{ skill_id: 'api', before: 2, after: 3, gain: 1, event_gain: 1, max_level: 3 }, { skill_id: 'system', before: 1, after: 2, gain: 1, event_gain: 1, max_level: 3 }], version: 2, replayed: false }

function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity }, mutations: { retry: false } } })
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/employees/jury-profile']}><Routes><Route path="/employees/:employeeId" element={<EmployeeWorkspace />} /></Routes></MemoryRouter></QueryClientProvider>)
  return client
}
function completeButton() {
  const article = screen.getByRole('heading', { name: 'System Design Fundamentals' }).closest('article')!
  return within(article).getByRole('button', { name: 'Complete activity' })
}

beforeEach(() => {
  vi.clearAllMocks()
  completed = false
  mocks.getEmployee.mockImplementation(async () => employee())
  mocks.getRecommendations.mockImplementation(async () => career())
  mocks.getEmployeeHistory.mockResolvedValue([])
})
afterEach(cleanup)

describe('employee dashboard completion integration', () => {
  it('waits for backend confirmation, then refetches profile/history/recommendations/HR and renders returned progress', async () => {
    let confirm!: (value: CompletionReceipt) => void
    mocks.completeActivity.mockImplementation(() => new Promise<CompletionReceipt>((resolve) => { confirm = resolve }))
    const client = show()
    const invalidate = vi.spyOn(client, 'invalidateQueries')
    await screen.findByRole('heading', { name: 'System Design Fundamentals' })
    expect(screen.getByRole('meter').getAttribute('aria-valuenow')).toBe('0.5897435897435898')
    const button = completeButton()
    fireEvent.click(button)
    fireEvent.click(button)
    await waitFor(() => expect(mocks.completeActivity).toHaveBeenCalledTimes(1))
    expect(mocks.getEmployee).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('meter').getAttribute('aria-valuenow')).toBe('0.5897435897435898')
    expect(screen.getByRole('button', { name: 'Saving completion…' }).hasAttribute('disabled')).toBe(true)
    expect(screen.queryByRole('heading', { name: 'Completion recorded' })).toBeNull()
    completed = true
    await act(async () => { confirm(receipt) })
    await screen.findByRole('heading', { name: 'Completion recorded' })
    await waitFor(() => expect(screen.getByRole('meter').getAttribute('aria-valuenow')).toBe('0.6666666666666666'))
    expect(screen.queryByRole('heading', { name: 'System Design Fundamentals' })).toBeNull()
    expect(screen.getByRole('heading', { name: 'Feedback Practice' })).toBeTruthy()
    const profile = screen.getByRole('region', { name: 'Your profile' })
    expect(within(profile).getByText('API Design').closest('li')?.textContent).toBe('API Design3 / 5')
    expect(within(profile).getByText('System Design').closest('li')?.textContent).toBe('System Design2 / 5')
    expect(mocks.getEmployee).toHaveBeenCalledTimes(2)
    expect(mocks.getEmployeeHistory).toHaveBeenCalledTimes(2)
    expect(mocks.getRecommendations).toHaveBeenCalledTimes(2)
    expect(invalidate.mock.calls.map(([options]) => options?.queryKey)).toEqual([
      ['employee', 'jury-profile'], ['history', 'jury-profile'], ['recommendations', 'jury-profile'], ['hr-analytics'],
    ])
    expect(mocks.getEmployees).not.toHaveBeenCalled()
    expect(mocks.completeActivity.mock.calls[0][2].idempotencyKey).toEqual(expect.any(String))
  })

  it('retries uncertain completion using the exact same action key and does not show a gain on failure', async () => {
    mocks.completeActivity.mockRejectedValueOnce(new ApiError('NETWORK', 'Connection interrupted')).mockImplementationOnce(async () => { completed = true; return { ...receipt, replayed: true } })
    show()
    await screen.findByRole('heading', { name: 'System Design Fundamentals' })
    fireEvent.click(completeButton())
    await screen.findByRole('heading', { name: 'Completion could not be confirmed' })
    expect(screen.getByRole('meter').getAttribute('aria-valuenow')).toBe('0.5897435897435898')
    expect(mocks.getEmployee).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole('button', { name: 'Retry completion' }))
    await screen.findByRole('heading', { name: 'Completion already recorded' })
    expect(mocks.completeActivity).toHaveBeenCalledTimes(2)
    expect(mocks.completeActivity.mock.calls[1]).toEqual(mocks.completeActivity.mock.calls[0])
  })

  it('requires an ambiguous assignment choice and retries the exact chosen record with the same key', async () => {
    mocks.getEmployeeHistory.mockResolvedValue([
      { id: 'assignment-a', eventId: 'EV_005', status: 'overdue', date: '2026-01-01', updatedAt: '2026-01-01' },
      { id: 'assignment-b', eventId: 'EV_005', status: 'overdue', date: '2026-02-01', updatedAt: '2026-02-01' },
    ])
    mocks.completeActivity.mockRejectedValueOnce(new ApiError('NETWORK', 'Uncertain result')).mockImplementationOnce(async () => { completed = true; return { ...receipt, replayed: true } })
    show()
    await screen.findByRole('heading', { name: 'System Design Fundamentals' })
    expect(completeButton().hasAttribute('disabled')).toBe(true)
    fireEvent.change(screen.getByRole('combobox', { name: 'Assignment to complete' }), { target: { value: 'assignment-b' } })
    expect(completeButton().hasAttribute('disabled')).toBe(false)
    fireEvent.click(completeButton())
    await screen.findByRole('heading', { name: 'Completion could not be confirmed' })
    expect(mocks.completeActivity.mock.calls[0][2].recordId).toBe('assignment-b')
    fireEvent.change(screen.getByRole('combobox', { name: 'Assignment to complete' }), { target: { value: 'assignment-a' } })
    fireEvent.click(screen.getByRole('button', { name: 'Retry completion' }))
    await screen.findByRole('heading', { name: 'Completion already recorded' })
    expect(mocks.completeActivity.mock.calls[1]).toEqual(mocks.completeActivity.mock.calls[0])
  })

  it('shows loading and then a genuine empty result without treating it as an error', async () => {
    let resolveProfile!: (value: Employee) => void
    mocks.getEmployee.mockImplementationOnce(() => new Promise<Employee>((resolve) => { resolveProfile = resolve }))
    mocks.getRecommendations.mockResolvedValue({ ...career(), status: 'no_next_grade', recommendations: [], target: null, readiness: null })
    show()
    expect(screen.getByRole('status').getAttribute('aria-busy')).toBe('true')
    await act(async () => { resolveProfile(employee()) })
    await screen.findByRole('heading', { name: 'No next grade for this career direction' })
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Complete activity' })).toBeNull()
  })

  it.each([
    [new ApiError('UNAUTHENTICATED', 'Missing bearer', { status: 401, backendCode: 'unauthenticated' }), 'Authentication required'],
    [new ApiError('FORBIDDEN', 'Wrong employee', { status: 403, backendCode: 'forbidden' }), 'Access denied'],
    [new ApiError('UNAVAILABLE', 'Backend offline', { status: 503 }), 'Backend unavailable'],
  ])('renders authentication and availability errors clearly: %s', async (error, title) => {
    mocks.getEmployee.mockRejectedValueOnce(error)
    show()
    await screen.findByRole('heading', { name: String(title) })
    expect(mocks.getRecommendations).not.toHaveBeenCalled()
    expect(mocks.getEmployeeHistory).not.toHaveBeenCalled()
  })
})
