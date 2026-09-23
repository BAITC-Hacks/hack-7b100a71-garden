// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiAccess, ApiSessionControls } from './ApiAccess'
import { getApiToken, setApiToken } from '../services/apiSession'

const runtime = vi.hoisted(() => ({ mode: 'real' }))
vi.mock('../services/api', () => ({ get apiMode() { return runtime.mode } }))
const clients: QueryClient[] = []
function mount() {
  const client = new QueryClient()
  clients.push(client)
  render(<QueryClientProvider client={client}><ApiAccess><p>Connected content</p><ApiSessionControls /></ApiAccess></QueryClientProvider>)
  return client
}
beforeEach(() => { runtime.mode = 'real'; setApiToken(''); vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.test') })
afterEach(() => { cleanup(); clients.forEach((client) => client.clear()); clients.length = 0; setApiToken(''); vi.unstubAllEnvs() })

describe('runtime API access', () => {
  it('keeps mock mode directly usable without credentials', () => {
    runtime.mode = 'mock'; mount()
    expect(screen.getByText('Connected content')).toBeTruthy()
    expect(screen.queryByLabelText('Access token')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Change access token' })).toBeNull()
  })
  it('gates real queries until a token is supplied, without persisting it', () => {
    const write = vi.spyOn(Storage.prototype, 'setItem')
    mount()
    expect(screen.queryByText('Connected content')).toBeNull()
    fireEvent.change(screen.getByLabelText('Access token'), { target: { value: 'test-session-token' } })
    fireEvent.click(screen.getByRole('button', { name: 'Open workspace' }))
    expect(getApiToken()).toBe('test-session-token')
    expect(screen.getByText('Connected content')).toBeTruthy()
    expect(write).not.toHaveBeenCalled()
    write.mockRestore()
  })
  it('explains missing configuration and disables access', () => {
    vi.stubEnv('VITE_API_BASE_URL', ''); mount()
    expect(screen.getByRole('alert').textContent).toContain('backend address is not configured')
    expect((screen.getByRole('button', { name: 'Open workspace' }) as HTMLButtonElement).disabled).toBe(true)
  })
  it('clears the previous identity and cache before another token is entered', async () => {
    setApiToken('old-token'); const client = mount()
    client.setQueryData(['employee', 'old-profile'], { name: 'Old user' })
    fireEvent.click(screen.getByRole('button', { name: 'Change access token' }))
    await waitFor(() => expect(getApiToken()).toBe(''))
    expect(client.getQueryData(['employee', 'old-profile'])).toBeUndefined()
    expect(screen.queryByText('Connected content')).toBeNull()
    expect(screen.getByLabelText('Access token')).toBeTruthy()
  })
  it.each([['activity-completion', 'submitting'], ['dataset-upload', 'checking-import']])('keeps identity stable during %s', async (key, phase) => {
    setApiToken('active-token'); const client = mount()
    client.setQueryData([key], { phase })
    fireEvent.click(screen.getByRole('button', { name: 'Change access token' }))
    await screen.findByRole('status')
    expect(getApiToken()).toBe('active-token')
    expect(screen.getByText('Connected content')).toBeTruthy()
  })
})
