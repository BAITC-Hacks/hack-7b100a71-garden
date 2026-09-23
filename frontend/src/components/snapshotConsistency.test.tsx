// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { EmployeeWorkspace } from '../pages/EmployeeWorkspace'
import { api } from '../services/api'
import { queryKeys } from '../services/queryClient'
import { ApiError } from '../types/api'
import type { CareerOverview, Employee } from '../types/domain'

vi.mock('../services/api', () => ({ api: {
  getEmployee: vi.fn(), getRecommendations: vi.fn(), getEmployeeHistory: vi.fn(), completeActivity: vi.fn(),
} }))

const profile: Employee = { id: 'snapshot-person', name: 'Snapshot Employee', role: 'Engineer', grade: 'Middle', department: 'Technology',
  preferredLanguage: 'en', skills: [], snapshotVersion: 1 }
const assessment: CareerOverview = { employeeId: profile.id, target: { role: 'Target Architect', grade: 'Lead' },
  trajectory: null, readiness: { current: 0.63 }, skillGaps: [], recommendations: [], snapshotVersion: 2 }
let client: QueryClient

function mount() {
  client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 30_000 } } })
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[`/employees/${profile.id}`]}>
    <Routes><Route path="/employees/:employeeId" element={<EmployeeWorkspace />} /></Routes>
  </MemoryRouter></QueryClientProvider>)
}
const refreshButton = () => screen.getByRole('button', { name: 'Refresh profile and assessment' })
const mismatch = () => screen.findByRole('heading', { name: 'Your profile and assessment need to be synchronized' })
function expectHidden() {
  expect(screen.queryByText('Target Architect')).toBeNull()
  expect(screen.queryByRole('meter')).toBeNull()
  expect(screen.queryByRole('heading', { name: 'Recommended next steps' })).toBeNull()
}

beforeEach(() => {
  vi.resetAllMocks()
  vi.mocked(api.getEmployee).mockResolvedValue(profile)
  vi.mocked(api.getRecommendations).mockResolvedValue(assessment)
})
afterEach(() => { cleanup(); client?.clear() })

describe('employee snapshot consistency', () => {
  it('withholds a mismatched target and assessment without retrying automatically', async () => {
    mount()
    await mismatch()
    expect(screen.getByRole('heading', { name: 'Snapshot Employee' })).toBeTruthy()
    expectHidden()
    expect(api.getEmployee).toHaveBeenCalledTimes(1)
    expect(api.getRecommendations).toHaveBeenCalledTimes(1)
  })

  it('publishes a coherent manual refresh and deduplicates repeated refresh clicks', async () => {
    mount()
    await mismatch()
    vi.mocked(api.getEmployee).mockResolvedValue({ ...profile, snapshotVersion: 3 })
    vi.mocked(api.getRecommendations).mockResolvedValue({ ...assessment, snapshotVersion: 3 })
    const button = refreshButton()
    fireEvent.click(button)
    fireEvent.click(button)
    await screen.findByRole('meter', { name: 'Career readiness' })
    expect(screen.getAllByText('Target Architect').length).toBeGreaterThan(0)
    expect(api.getEmployee).toHaveBeenCalledTimes(2)
    expect(api.getRecommendations).toHaveBeenCalledTimes(2)
    expect(api.completeActivity).not.toHaveBeenCalled()
    expect(client.getQueryData<Employee>(queryKeys.employee(profile.id))?.snapshotVersion).toBe(3)
  })

  it('keeps conflicting snapshots hidden after a read failure and offers another read-only attempt', async () => {
    mount()
    await mismatch()
    vi.mocked(api.getEmployee).mockRejectedValue(new ApiError('NETWORK', 'Unavailable'))
    fireEvent.click(refreshButton())
    await screen.findByText(/Your target and career insights remain hidden/)
    expectHidden()
    expect(client.getQueryData<Employee>(queryKeys.employee(profile.id))).toEqual(profile)
    expect(client.getQueryData<CareerOverview>(queryKeys.recommendations(profile.id))).toEqual(assessment)
    vi.mocked(api.getEmployee).mockResolvedValue({ ...profile, snapshotVersion: 4 })
    vi.mocked(api.getRecommendations).mockResolvedValue({ ...assessment, snapshotVersion: 4 })
    fireEvent.click(refreshButton())
    await screen.findByRole('meter', { name: 'Career readiness' })
    expect(api.completeActivity).not.toHaveBeenCalled()
  })

  it('does not invent a mismatch when a snapshot version is unavailable', async () => {
    vi.mocked(api.getEmployee).mockResolvedValue({ ...profile, snapshotVersion: undefined })
    mount()
    await screen.findByRole('meter', { name: 'Career readiness' })
    expect(screen.queryByRole('button', { name: 'Refresh profile and assessment' })).toBeNull()
    await waitFor(() => expect(api.getEmployee).toHaveBeenCalledTimes(1))
  })
})
