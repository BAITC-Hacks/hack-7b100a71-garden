// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from '../App'
import { api } from '../services/api'
import { createMockApi, type MockOptions } from '../mocks/mockApi'
import { hrAnalytics, partialHRAnalytics, zeroHRAnalytics } from '../mocks/hrFixtures'

vi.mock('../services/api', () => ({ apiMode: 'mock', api: {
  getEmployees: vi.fn(), getEmployee: vi.fn(), getRecommendations: vi.fn(), getEmployeeHistory: vi.fn(),
  getHRAnalytics: vi.fn(), completeActivity: vi.fn(),
} }))

let client: QueryClient
function mount(options: MockOptions = {}, route = '/hr') {
  const adapter = createMockApi({ latencyMs: 0, ...options })
  vi.mocked(api.getEmployees).mockImplementation(adapter.getEmployees)
  vi.mocked(api.getEmployee).mockImplementation(adapter.getEmployee)
  vi.mocked(api.getRecommendations).mockImplementation(adapter.getRecommendations)
  vi.mocked(api.getEmployeeHistory).mockImplementation(adapter.getEmployeeHistory)
  vi.mocked(api.getHRAnalytics).mockImplementation(adapter.getHRAnalytics)
  client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 30_000 } } })
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[route]}><App /></MemoryRouter></QueryClientProvider>)
}
const ready = () => screen.findByRole('region', { name: 'Common skill gaps' })
function metric(label: string) {
  return within(within(screen.getByLabelText('Development overview')).getByText(label).closest('.hr-metric') as HTMLElement)
}

beforeEach(() => { vi.clearAllMocks(); vi.stubGlobal('scrollTo', vi.fn()) })
afterEach(() => { cleanup(); client?.clear(); vi.unstubAllGlobals() })

describe('HR dashboard integration', () => {
  it('opens the direct HR route and displays all supplied overview values', async () => {
    mount({ hrResponse: { totalEmployees: 103, employeesInDevelopment: 27, withoutNextStep: 19, participationRate: 0.675 } })
    await ready()
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Development, in perspective.')
    expect(metric('Total employees').getByText('103')).toBeTruthy()
    expect(metric('Employees in development').getByText('27')).toBeTruthy()
    expect(metric('Without next step').getByText('19')).toBeTruthy()
    expect(metric('Participation rate').getByText('67.5%')).toBeTruthy()
    const next = screen.getByRole('region', { name: 'A clear next step for everyone.' })
    expect(within(next).getByText('19')).toBeTruthy()
    const meter = screen.getByRole('meter', { name: 'Participation rate' })
    expect(meter.getAttribute('aria-valuenow')).toBe('0.675')
    expect(meter.getAttribute('aria-valuetext')).toBe('67.5%')
    expect(api.getHRAnalytics).toHaveBeenCalledTimes(1)
    expect(api.getHRAnalytics).toHaveBeenCalledWith({ signal: expect.any(AbortSignal) })
  })

  it('preserves skill-gap and activity order/counts even when counts are not descending', async () => {
    mount({ hrResponse: {
      commonSkillGaps: [{ skillId: 'small', name: 'Mentoring', employeeCount: 2 }, { skillId: 'large', name: 'Leadership', employeeCount: 11 }],
      activityParticipation: [{ activityId: 'a', title: 'Workshop A', participantCount: 3 }, { activityId: 'b', title: 'Workshop B', participantCount: 17 }],
    } })
    await ready()
    const gaps = within(screen.getByRole('list', { name: 'Common skill gaps' })).getAllByRole('listitem')
    expect(gaps.map((item) => item.textContent)).toEqual(['Mentoring2 employees', 'Leadership11 employees'])
    const activities = within(screen.getByRole('list', { name: 'Activity participation' })).getAllByRole('listitem')
    expect(activities.map((item) => item.textContent)).toEqual(['Workshop A3 participants', 'Workshop B17 participants'])
    expect(metric('Participation rate').getByText('Unavailable')).toBeTruthy()
    expect(screen.queryByRole('meter')).toBeNull()
  })

  it('displays all six status aggregates without generating percentages or totals', async () => {
    mount()
    await ready()
    const rows = within(screen.getByRole('list', { name: 'Activity status distribution' })).getAllByRole('listitem')
    expect(rows.map((item) => item.textContent)).toEqual([
      'Completed14 records', 'In progress10 records', 'No show2 records', 'Dropped1 record', 'Declined3 records', 'Overdue2 records',
    ])
    expect(screen.getByRole('region', { name: 'Activity status distribution' }).textContent).not.toContain('%')
  })

  it('keeps supplied zero metrics and zero status counts visible', async () => {
    mount({ hrResponse: zeroHRAnalytics })
    await ready()
    for (const label of ['Total employees', 'Employees in development', 'Without next step']) expect(metric(label).getByText('0')).toBeTruthy()
    expect(metric('Participation rate').getByText('0%')).toBeTruthy()
    expect(screen.getByRole('meter').getAttribute('aria-valuenow')).toBe('0')
    expect(screen.getByRole('list', { name: 'Activity status distribution' }).textContent).toBe('Completed0 records')
    expect(screen.queryByText('No organizational analytics yet')).toBeNull()
  })

  it.each([{}, { commonSkillGaps: [], activityParticipation: null, activityStatuses: [] }, { totalEmployees: null, participationRate: null }])('handles empty analytics %j', async (hrResponse) => {
    mount({ hrResponse })
    expect(await screen.findByRole('heading', { name: 'No organizational analytics yet' })).toBeTruthy()
    expect(screen.queryByLabelText('Development overview')).toBeNull()
    expect(screen.queryByRole('meter')).toBeNull()
    expect(screen.getByRole('button', { name: 'Refresh analytics' })).toBeTruthy()
  })

  it('keeps partial metrics and individual missing row counts distinct from zero', async () => {
    mount({ hrResponse: partialHRAnalytics })
    await ready()
    expect(metric('Total employees').getByText('24')).toBeTruthy()
    expect(metric('Without next step').getByText('0')).toBeTruthy()
    expect(metric('Employees in development').getByText('Unavailable')).toBeTruthy()
    expect(metric('Participation rate').getByText('Unavailable')).toBeTruthy()
    expect(screen.getByText('No participation data available')).toBeTruthy()
    expect(screen.getByText('No activity status data available')).toBeTruthy()
    expect(screen.getByRole('list', { name: 'Common skill gaps' }).textContent).toContain('LeadershipUnavailable')
  })

  it('does not infer missing coverage, status categories, or participation from other counts', async () => {
    mount({ hrResponse: { totalEmployees: 50, employeesInDevelopment: 8, activityStatuses: [{ status: 'overdue', count: 4 }] } })
    await ready()
    expect(metric('Without next step').getByText('Unavailable')).toBeTruthy()
    expect(screen.getByText('Next-step coverage is unavailable.')).toBeTruthy()
    expect(metric('Participation rate').getByText('Unavailable')).toBeTruthy()
    expect(screen.getByText('No skill-gap data available')).toBeTruthy()
    expect(within(screen.getByRole('list', { name: 'Activity status distribution' })).getAllByRole('listitem')).toHaveLength(1)
    expect(screen.queryByText('Completed')).toBeNull()
  })

  it('shows invalid metric values as unavailable without clamping them to zero or 100%', async () => {
    mount({ hrResponse: { totalEmployees: 50, withoutNextStep: -1, participationRate: 75, employeesInDevelopment: Number.NaN } })
    await ready()
    for (const label of ['Without next step', 'Participation rate', 'Employees in development']) expect(metric(label).getByText('Unavailable')).toBeTruthy()
    expect(screen.queryByRole('meter')).toBeNull()
  })

  it('announces loading before showing metrics', async () => {
    mount({ hrLatencyMs: 100 })
    expect(screen.getByRole('status').textContent).toContain('Loading organizational analytics')
    expect(screen.queryByLabelText('Development overview')).toBeNull()
    await ready()
  })

  it('recovers from an isolated HR API error through manual retry', async () => {
    mount({ failFirstHR: true })
    expect((await screen.findByRole('alert')).textContent).toContain('Organizational insights couldn’t be loaded')
    expect(screen.queryByLabelText('Development overview')).toBeNull()
    expect(await screen.findByRole('option', { name: 'Aigerim Sapar' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    await ready()
    expect(api.getHRAnalytics).toHaveBeenCalledTimes(2)
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('retains the last analytics on refresh failure and refreshes successfully on retry', async () => {
    mount()
    await ready()
    vi.mocked(api.getHRAnalytics).mockRejectedValueOnce(new Error('Network failure'))
    fireEvent.click(screen.getByRole('button', { name: 'Refresh analytics' }))
    expect((await screen.findByRole('alert')).textContent).toContain('The last available data is shown')
    expect(metric('Total employees').getByText('24')).toBeTruthy()
    vi.mocked(api.getHRAnalytics).mockResolvedValueOnce({ ...hrAnalytics, totalEmployees: 28 })
    fireEvent.click(screen.getByRole('button', { name: 'Refresh analytics' }))
    await waitFor(() => expect(metric('Total employees').getByText('28')).toBeTruthy())
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('navigates through the existing HR link and can return to an employee workspace', async () => {
    mount({}, '/')
    fireEvent.click(screen.getByRole('link', { name: 'HR overview' }))
    await ready()
    expect(screen.getByRole('link', { name: 'HR overview' }).getAttribute('aria-current')).toBe('page')
    expect(document.title).toBe('HR overview · Career Quest')
    expect(api.getEmployee).not.toHaveBeenCalled()
    expect(api.getRecommendations).not.toHaveBeenCalled()
    expect(api.getEmployeeHistory).not.toHaveBeenCalled()
    await screen.findByRole('option', { name: 'Aigerim Sapar' })
    fireEvent.change(screen.getByRole('combobox', { name: 'View employee' }), { target: { value: 'demo-aigerim' } })
    expect(await screen.findByRole('heading', { name: 'Aigerim Sapar' })).toBeTruthy()
    expect(await screen.findByRole('heading', { name: 'Recommended next steps' })).toBeTruthy()
  })

  it('keeps the HR main content aggregate-only with no employee details or ranking', async () => {
    mount()
    await ready()
    const main = screen.getByRole('main')
    for (const name of ['Aigerim Sapar', 'Daniyar Omar', 'Madina Serik']) expect(main.textContent).not.toContain(name)
    expect(within(main).queryByRole('table')).toBeNull()
    expect(within(main).getAllByRole('link').map((link) => link.getAttribute('href'))).toEqual(['/hr/dataset'])
    expect(main.textContent).not.toMatch(/leaderboard|top performers|employee ranking/i)
    expect(api.getEmployeeHistory).not.toHaveBeenCalled()
  })
})
