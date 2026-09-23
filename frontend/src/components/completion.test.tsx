// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, useLocation } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from '../App'
import { api } from '../services/api'
import { queryKeys } from '../services/queryClient'
import { createMockApi, type MockOptions } from '../mocks/mockApi'
import type { CompletionState } from '../types/completion'
import type { CareerOverview, Employee } from '../types/domain'
import { useActivityCompletion } from '../hooks/useActivityCompletion'

vi.mock('../services/api', () => ({ apiMode: 'mock', api: {
  getEmployees: vi.fn(), getEmployee: vi.fn(), getRecommendations: vi.fn(), getEmployeeHistory: vi.fn(), completeActivity: vi.fn(),
} }))

let client: QueryClient
function Location() { return <output aria-label="Current route">{useLocation().pathname}</output> }
function mount(options: MockOptions = {}) {
  const adapter = createMockApi({ latencyMs: 0, completionLatencyMs: 5, ...options })
  vi.mocked(api.getEmployees).mockImplementation(adapter.getEmployees)
  vi.mocked(api.getEmployee).mockImplementation(adapter.getEmployee)
  vi.mocked(api.getRecommendations).mockImplementation(adapter.getRecommendations)
  vi.mocked(api.getEmployeeHistory).mockImplementation(adapter.getEmployeeHistory)
  vi.mocked(api.completeActivity).mockImplementation(adapter.completeActivity)
  client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 30_000 }, mutations: { retry: false } } })
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/employees/demo-aigerim']}><App /><Location /></MemoryRouter></QueryClientProvider>)
  return adapter
}
const firstCard = () => screen.findByRole('article', { name: 'Designing High-Load Systems' })
async function clickFirst() { const card = await firstCard(); fireEvent.click(within(card).getByRole('button', { name: 'Complete development step' })) }
async function expectSynced() {
  await waitFor(() => expect(screen.getByRole('meter', { name: 'Career readiness' }).getAttribute('aria-valuenow')).toBe('0.79'))
  expect(screen.queryByRole('article', { name: 'Designing High-Load Systems' })).toBeNull()
  expect(screen.getAllByRole('article').map((card) => within(card).getByRole('heading', { level: 3 }).textContent)).toEqual(['Build APIs That Scale', 'Communicating Technical Decisions'])
}
beforeEach(() => { vi.clearAllMocks(); vi.stubGlobal('scrollTo', vi.fn()) })
afterEach(() => { cleanup(); client?.clear(); vi.unstubAllGlobals() })

describe('activity completion interaction', () => {
  it('calls the API once, disables actions while pending, refreshes state, and keeps selection and route', async () => {
    mount({ completionLatencyMs: 70 })
    const card = await firstCard()
    const button = within(card).getByRole('button', { name: 'Complete development step' })
    fireEvent.click(button)
    fireEvent.click(button)
    await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(true))
    expect(button.getAttribute('aria-busy')).toBe('true')
    expect(api.completeActivity).toHaveBeenCalledTimes(1)
    expect(api.completeActivity).toHaveBeenCalledWith('demo-aigerim', 'demo-system-design')
    await expectSynced()
    expect(api.getEmployee).toHaveBeenCalledTimes(2)
    expect(api.getRecommendations).toHaveBeenCalledTimes(2)
    expect(client.getQueryData<Employee>(queryKeys.employee('demo-aigerim'))?.skills[0].current).toBe(3)
    expect(within(screen.getByRole('region', { name: 'Skills to develop' })).getAllByText('3').length).toBeGreaterThan(0)
    expect(screen.getByRole('heading', { name: 'Activity completed' })).toBeTruthy()
    expect((screen.getByRole('combobox', { name: 'View employee' }) as HTMLSelectElement).value).toBe('demo-aigerim')
    expect(screen.getByLabelText('Current route').textContent).toBe('/employees/demo-aigerim')
  })

  it('guards simultaneous programmatic submissions before the component re-renders', async () => {
    const adapter = mount({ completionLatencyMs: 20 })
    await firstCard()
    const recommendation = (await adapter.getRecommendations('demo-aigerim')).recommendations[0]
    function DoubleSubmit() {
      const { complete } = useActivityCompletion('demo-aigerim')
      return <button onClick={() => { void complete(recommendation); void complete(recommendation) }}>Two submissions</button>
    }
    render(<QueryClientProvider client={client}><DoubleSubmit /></QueryClientProvider>)
    fireEvent.click(screen.getByRole('button', { name: 'Two submissions' }))
    await expectSynced()
    expect(api.completeActivity).toHaveBeenCalledTimes(1)
  })

  it('shows a completion failure and retries without reloading', async () => {
    mount({ failFirstCompletion: true })
    await clickFirst()
    expect(await screen.findByRole('heading', { name: 'Activity could not be completed' })).toBeTruthy()
    expect(screen.getByRole('meter', { name: 'Career readiness' }).getAttribute('aria-valuenow')).toBe('0.67')
    fireEvent.click(within(screen.getByRole('alert')).getByRole('button', { name: 'Retry completion' }))
    await expectSynced()
    expect(api.completeActivity).toHaveBeenCalledTimes(2)
  })

  it.each(['failure', 'incomplete'] as const)('keeps acknowledgement after refresh %s and only retries reads', async (refreshFault) => {
    mount({ refreshFault })
    await clickFirst()
    const retry = await screen.findByRole('button', { name: 'Retry refresh' })
    expect(screen.getByRole('heading', { name: 'Activity completed' })).toBeTruthy()
    expect(screen.getByRole('meter', { name: 'Career readiness' }).getAttribute('aria-valuenow')).toBe('0.67')
    expect(client.getQueryData<Employee>(queryKeys.employee('demo-aigerim'))?.skills[0].current).toBe(2)
    expect(within(await firstCard()).getByRole('button', { name: 'Activity completed' }).hasAttribute('disabled')).toBe(true)
    fireEvent.click(retry)
    await expectSynced()
    expect(api.completeActivity).toHaveBeenCalledTimes(1)
  })

  it('reconciles a duplicate response without a second completion', async () => {
    mount({ completionConflict: 'duplicate' })
    await clickFirst()
    await expectSynced()
    expect(screen.getByRole('heading', { name: 'Activity already completed' })).toBeTruthy()
    expect(api.completeActivity).toHaveBeenCalledTimes(1)
  })

  it('handles a recommendation that is no longer available using refresh, not resubmission', async () => {
    mount({ completionConflict: 'unavailable' })
    await clickFirst()
    fireEvent.click(await screen.findByRole('button', { name: 'Retry refresh' }))
    expect(await screen.findByRole('heading', { name: 'Dashboard refreshed' })).toBeTruthy()
    expect(api.completeActivity).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('heading', { name: 'Activity completed' })).toBeNull()
    expect(screen.queryByRole('article', { name: 'Designing High-Load Systems' })).toBeNull()
  })

  it('handles an employee removed before completion', async () => {
    mount({ completionConflict: 'missing-employee' })
    await clickFirst()
    expect(await screen.findByText('This employee is no longer available. Choose another profile to continue.')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Retry completion' })).toBeNull()
  })

  it('renders partial recommendation data returned after completion', async () => {
    mount({ partialCompletionData: true })
    await clickFirst()
    await expectSynced()
    expect(screen.getAllByText('Skill impact has not been provided.').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Readiness impact has not been provided.').length).toBeGreaterThan(0)
  })

  it('finishes for the original employee when selection changes during submission', async () => {
    mount({ completionLatencyMs: 120 })
    const user = userEvent.setup()
    await clickFirst()
    await user.selectOptions(screen.getByRole('combobox', { name: 'View employee' }), 'demo-daniyar')
    expect(await screen.findByRole('heading', { name: 'Daniyar Omar' })).toBeTruthy()
    await waitFor(() => expect(client.getQueryData<CompletionState>(queryKeys.completion('demo-aigerim'))?.phase).toBe('success'))
    expect(screen.queryByRole('heading', { name: 'Activity completed' })).toBeNull()
    expect(screen.getByLabelText('Current route').textContent).toBe('/employees/demo-daniyar')
    await user.selectOptions(screen.getByRole('combobox', { name: 'View employee' }), 'demo-aigerim')
    await expectSynced()
    expect(api.completeActivity).toHaveBeenCalledTimes(1)
  })

  it('refreshes history when it is already used by a view', async () => {
    mount()
    await firstCard()
    act(() => { client.setQueryData(queryKeys.history('demo-aigerim'), []) })
    await clickFirst()
    await expectSynced()
    expect(api.getEmployeeHistory).toHaveBeenCalledTimes(1)
    expect(client.getQueryData(queryKeys.history('demo-aigerim'))).toMatchObject([{ eventId: 'demo-system-design', status: 'completed' }])
    expect(client.getQueryData<CareerOverview>(queryKeys.recommendations('demo-aigerim'))?.readiness?.current).toBe(0.79)
  })
})
