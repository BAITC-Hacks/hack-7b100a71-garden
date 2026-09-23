// @vitest-environment jsdom
import { QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, useParams } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from './App'
import { useEmployee, useEmployees } from './hooks/useEmployees'
import { api } from './services/api'
import { queryClient } from './services/queryClient'
import { getSession, setSession } from './services/session'
import { ApiError } from './types/api'
import type { Employee } from './types/domain'

vi.mock('./services/api', () => ({ apiMode: 'real', api: { getEmployees: vi.fn(), getEmployee: vi.fn() } }))
vi.mock('./pages/EmployeeWorkspace', () => ({ EmployeeWorkspace: function EmployeeWorkspace() {
  const { employeeId = '' } = useParams()
  const profile = useEmployee(employeeId)
  return <div>Own profile: {profile.data?.name ?? 'loading'}</div>
} }))
vi.mock('./pages/HRWorkspace', () => ({ HRWorkspace: () => <div>HR analytics workspace</div> }))

const employee: Employee = { id: 'jury-new-id', name: 'Jury Profile', role: 'Engineer', grade: 'Middle', department: 'Platform', preferredLanguage: 'ru', skills: [] }
const directory = vi.mocked(api.getEmployees)
const profile = vi.mocked(api.getEmployee)

function mount(path = '/') {
  return render(<QueryClientProvider client={queryClient}><MemoryRouter initialEntries={[path]}><App /></MemoryRouter></QueryClientProvider>)
}

beforeEach(() => {
  setSession(null)
  vi.clearAllMocks()
  vi.spyOn(window, 'scrollTo').mockImplementation(() => undefined)
  directory.mockResolvedValue([employee])
  profile.mockResolvedValue(employee)
})
afterEach(() => { cleanup(); setSession(null); vi.restoreAllMocks() })

describe('identity-aware navigation', () => {
  it('loads no protected data before identity entry', () => {
    mount('/hr')
    expect(screen.getByRole('heading', { name: 'Open your workspace' })).toBeTruthy()
    expect(directory).not.toHaveBeenCalled()
    expect(profile).not.toHaveBeenCalled()
  })

  it('opens an arbitrary employee directly and never requests the HR directory', async () => {
    mount()
    fireEvent.change(screen.getByLabelText('Employee ID'), { target: { value: employee.id } })
    fireEvent.change(screen.getByLabelText('Access token'), { target: { value: 'opaque-test-token' } })
    fireEvent.click(screen.getByRole('button', { name: 'Open workspace' }))
    expect(await screen.findByText('Own profile: Jury Profile')).toBeTruthy()
    expect(profile).toHaveBeenCalledWith(employee.id, expect.objectContaining({ signal: expect.any(AbortSignal) }))
    expect(directory).not.toHaveBeenCalled()
    expect(screen.queryByRole('link', { name: 'HR overview' })).toBeNull()
    expect(screen.queryByLabelText('View employee')).toBeNull()
    expect(getSession()).toEqual({ role: 'employee', employeeId: employee.id, token: 'opaque-test-token' })
  })

  it.each(['/hr', '/employees/someone-else'])('blocks employee navigation to %s before data hooks mount', (path) => {
    setSession({ role: 'employee', employeeId: employee.id, token: 'test-token' })
    mount(path)
    expect(screen.getByRole('heading', { name: 'Access restricted' })).toBeTruthy()
    expect(profile).not.toHaveBeenCalled()
    expect(directory).not.toHaveBeenCalled()
    expect(screen.queryByText('HR analytics workspace')).toBeNull()
  })

  it('lets HR enter without an employee ID, browse directory, and navigate to analytics', async () => {
    mount()
    fireEvent.change(screen.getByLabelText('Workspace'), { target: { value: 'hr' } })
    expect(screen.queryByLabelText('Employee ID')).toBeNull()
    fireEvent.change(screen.getByLabelText('Access token'), { target: { value: 'test-hr-token' } })
    fireEvent.click(screen.getByRole('button', { name: 'Open workspace' }))
    expect(await screen.findByRole('heading', { name: employee.name })).toBeTruthy()
    expect(directory).toHaveBeenCalledTimes(1)
    expect(screen.getByLabelText('View employee')).toBeTruthy()
    fireEvent.click(screen.getByRole('link', { name: 'HR overview' }))
    expect(await screen.findByText('HR analytics workspace')).toBeTruthy()
  })

  it('filters the directory without assuming known employee IDs', async () => {
    setSession({ role: 'hr', token: 'test-hr-token' })
    mount()
    await screen.findByRole('heading', { name: employee.name })
    fireEvent.change(screen.getByLabelText('Find an employee'), { target: { value: 'not-present' } })
    expect(screen.getByText('No matching profiles')).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Find an employee'), { target: { value: employee.id } })
    expect(screen.getByRole('heading', { name: employee.name })).toBeTruthy()
  })

  it('shows a loading state while the HR directory is pending', () => {
    directory.mockImplementation(() => new Promise(() => undefined))
    setSession({ role: 'hr', token: 'test-hr-token' })
    mount()
    expect(screen.getByRole('status').getAttribute('aria-busy')).toBe('true')
    expect(screen.queryByRole('heading', { name: employee.name })).toBeNull()
  })

  it('shows an empty directory without manufacturing profiles', async () => {
    directory.mockResolvedValue([])
    setSession({ role: 'hr', token: 'test-hr-token' })
    mount()
    expect(await screen.findByText('No employee profiles yet')).toBeTruthy()
    expect(screen.getByText('0 employees')).toBeTruthy()
    expect(screen.queryByLabelText('Find an employee')).toBeNull()
  })

  it('shows backend-unavailable errors and retries the real directory request', async () => {
    directory.mockRejectedValueOnce(new ApiError('UNAVAILABLE', 'Backend is unavailable.', { status: 503 }))
    setSession({ role: 'hr', token: 'test-hr-token' })
    mount()
    expect(await screen.findByText('Backend is unavailable.')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByRole('heading', { name: employee.name })).toBeTruthy()
    expect(directory).toHaveBeenCalledTimes(2)
  })

  it('clears the token and previous data when changing identity', async () => {
    setSession({ role: 'hr', token: 'test-hr-token' })
    mount()
    await screen.findByRole('heading', { name: employee.name })
    fireEvent.click(screen.getByRole('button', { name: 'Change identity' }))
    expect(getSession()).toBeNull()
    expect(queryClient.getQueryCache().getAll()).toHaveLength(0)
    expect((screen.getByLabelText('Access token') as HTMLInputElement).value).toBe('')
    expect(screen.queryByRole('heading', { name: employee.name })).toBeNull()
  })

  it('reports invalid token input without requesting protected data', () => {
    mount()
    fireEvent.change(screen.getByLabelText('Employee ID'), { target: { value: employee.id } })
    fireEvent.change(screen.getByLabelText('Access token'), { target: { value: 'invalid test token' } })
    fireEvent.click(screen.getByRole('button', { name: 'Open workspace' }))
    expect(screen.getByRole('alert').textContent).toContain('token without spaces')
    expect(getSession()).toBeNull()
    expect(profile).not.toHaveBeenCalled()
  })

  it.each([
    ['UNAUTHENTICATED', 401, 'Authentication required'],
    ['FORBIDDEN', 403, 'Access restricted'],
  ] as const)('shows backend %s for HR navigation claims that the token does not authorize', async (code, status, title) => {
    directory.mockRejectedValue(new ApiError(code, 'Backend denied access.', { status }))
    setSession({ role: 'hr', token: 'test-untrusted-role-token' })
    mount()
    expect(await screen.findByRole('heading', { name: title })).toBeTruthy()
    expect(screen.getByText('Backend denied access.')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Change identity' })).toBeTruthy()
  })

  it('does not request directory or another profile even if guarded hooks are mounted independently', async () => {
    function Probe() { useEmployees(); useEmployee('another-id'); return <div>Probe</div> }
    setSession({ role: 'employee', employeeId: employee.id, token: 'test-token' })
    render(<QueryClientProvider client={queryClient}><Probe /></QueryClientProvider>)
    await waitFor(() => expect(screen.getByText('Probe')).toBeTruthy())
    expect(profile).not.toHaveBeenCalled()
    expect(directory).not.toHaveBeenCalled()
  })
})
