// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from '../App'
import { api } from '../services/api'
import { ApiError } from '../types/api'
import { createMockApi } from '../mocks/mockApi'
import { queryKeys } from '../services/queryClient'
import { hrAnalytics } from '../mocks/hrFixtures'

vi.mock('../services/api', () => ({ apiMode: 'mock', api: {
  getEmployees: vi.fn(), getEmployee: vi.fn(), getRecommendations: vi.fn(), getEmployeeHistory: vi.fn(),
  getHRAnalytics: vi.fn(), completeActivity: vi.fn(),
} }))

let client: QueryClient
function mount(route = '/', seedHR = false) {
  client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: seedHR ? 0 : 30_000 } } })
  if (seedHR) client.setQueryData(queryKeys.hr, hrAnalytics)
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[route]}><App /></MemoryRouter></QueryClientProvider>)
}
const denied = () => new ApiError('FORBIDDEN', 'Forbidden', { backendCode: 'forbidden', status: 403 })
beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal('scrollTo', vi.fn())
  const adapter = createMockApi({ latencyMs: 0 })
  vi.mocked(api.getEmployees).mockImplementation(adapter.getEmployees)
  vi.mocked(api.getEmployee).mockImplementation(adapter.getEmployee)
  vi.mocked(api.getRecommendations).mockImplementation(adapter.getRecommendations)
  vi.mocked(api.getEmployeeHistory).mockImplementation(adapter.getEmployeeHistory)
  vi.mocked(api.getHRAnalytics).mockImplementation(adapter.getHRAnalytics)
})
afterEach(() => { cleanup(); client?.clear(); vi.unstubAllGlobals() })

describe('server-confirmed access failures', () => {
  it('explains invalid authentication without presenting retries that cannot change the token', async () => {
    vi.mocked(api.getEmployees).mockRejectedValue(new ApiError('AUTHENTICATION', 'Expired token', { status: 401 }))
    mount()
    expect(await screen.findByRole('heading', { name: 'Access token needs attention' })).toBeTruthy()
    expect(screen.getByText(/Your token is missing or no longer valid/)).toBeTruthy()
    expect(screen.getByRole('option', { name: 'Access token required' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: /try again|retry|reload/i })).toBeNull()
    expect(api.getEmployees).toHaveBeenCalledTimes(1)
  })

  it('explains the HR-only directory and keeps assigned-link navigation available', async () => {
    vi.mocked(api.getEmployees).mockRejectedValue(denied())
    mount()
    expect(await screen.findByText(/The employee directory requires HR access/)).toBeTruthy()
    expect(screen.getByRole('option', { name: 'HR access required' })).toBeTruthy()
    expect((screen.getByRole('combobox') as HTMLSelectElement).disabled).toBe(true)
    expect(screen.queryByRole('button', { name: /try again|retry|reload/i })).toBeNull()
  })

  it('loads an assigned direct employee route even when employee-list access is denied', async () => {
    vi.mocked(api.getEmployees).mockRejectedValue(denied())
    mount('/employees/demo-aigerim')
    expect(await screen.findByRole('heading', { name: 'Aigerim Sapar' })).toBeTruthy()
    expect(await screen.findByRole('meter', { name: 'Career readiness' })).toBeTruthy()
    expect(api.getEmployee).toHaveBeenCalledWith('demo-aigerim', { signal: expect.any(AbortSignal) })
    expect(api.getRecommendations).toHaveBeenCalledWith('demo-aigerim', { signal: expect.any(AbortSignal) })
    expect(screen.getByRole('option', { name: 'HR access required' })).toBeTruthy()
  })

  it('does not request a career assessment after profile access is denied', async () => {
    vi.mocked(api.getEmployee).mockRejectedValue(denied())
    mount('/employees/another-person')
    expect(await screen.findByText(/This token cannot access the requested employee/)).toBeTruthy()
    expect(api.getRecommendations).not.toHaveBeenCalled()
    expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull()
  })

  it('keeps the allowed profile visible when only the career assessment is denied', async () => {
    vi.mocked(api.getRecommendations).mockRejectedValue(denied())
    mount('/employees/demo-aigerim')
    expect(await screen.findByText(/This token cannot access this career assessment/)).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Aigerim Sapar' })).toBeTruthy()
    expect(screen.queryByRole('meter')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull()
  })

  it('replaces denied HR data with access guidance and removes refresh/import actions', async () => {
    vi.mocked(api.getHRAnalytics).mockRejectedValue(denied())
    mount('/hr', true)
    expect(await screen.findByText(/Organizational insights require HR access/)).toBeTruthy()
    expect(screen.queryByLabelText('Development overview')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Refresh analytics' })).toBeNull()
    expect(screen.queryByRole('link', { name: 'Manage dataset' })).toBeNull()
  })

  it('retains manual retries for transient network failures', async () => {
    vi.mocked(api.getEmployees).mockRejectedValueOnce(new ApiError('NETWORK', 'Temporarily offline'))
    mount()
    fireEvent.click(await screen.findByRole('button', { name: 'Try again' }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Aigerim Sapar' })).toBeTruthy())
    expect(api.getEmployees).toHaveBeenCalledTimes(2)
  })
})
