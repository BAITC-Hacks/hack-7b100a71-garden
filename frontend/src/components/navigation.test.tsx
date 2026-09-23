// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AppShell } from './AppShell'

vi.mock('../services/api', () => ({ apiMode: 'mock' }))
vi.mock('./EmployeeSelector', () => ({ EmployeeSelector: () => <div /> }))
vi.mock('./ApiAccess', () => ({ ApiSessionControls: () => null }))

function mount() {
  return render(<MemoryRouter><Routes><Route element={<AppShell />}>
    <Route index element={<h1>Employee page</h1>} />
    <Route path="hr" element={<h1>HR page</h1>} />
  </Route></Routes></MemoryRouter>)
}

beforeEach(() => vi.stubGlobal('scrollTo', vi.fn()))
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('navigation keyboard focus', () => {
  it('focuses the first navigation link on open and returns to the toggle on Escape', async () => {
    mount()
    const user = userEvent.setup()
    const toggle = screen.getByRole('button', { name: 'Toggle navigation' })
    toggle.focus()
    await user.keyboard('{Enter}')
    expect(toggle.getAttribute('aria-expanded')).toBe('true')
    expect(document.activeElement).toBe(screen.getByRole('link', { name: 'Employee workspace' }))
    await user.tab()
    expect(document.activeElement).toBe(screen.getByRole('link', { name: 'HR overview' }))
    await user.keyboard('{Escape}')
    expect(toggle.getAttribute('aria-expanded')).toBe('false')
    expect(document.activeElement).toBe(toggle)
  })

  it('closes navigation and focuses page content after following a link', async () => {
    mount()
    const user = userEvent.setup()
    const toggle = screen.getByRole('button', { name: 'Toggle navigation' })
    await user.click(toggle)
    await user.tab()
    await user.keyboard('{Enter}')
    expect(screen.getByRole('heading', { name: 'HR page' })).toBeTruthy()
    expect(toggle.getAttribute('aria-expanded')).toBe('false')
    expect(document.activeElement).toBe(screen.getByRole('main'))
  })

  it('does not leave focus in hidden navigation when selecting the current page', async () => {
    mount()
    const user = userEvent.setup()
    const toggle = screen.getByRole('button', { name: 'Toggle navigation' })
    await user.click(toggle)
    await user.keyboard('{Enter}')
    expect(screen.getByRole('heading', { name: 'Employee page' })).toBeTruthy()
    expect(toggle.getAttribute('aria-expanded')).toBe('false')
    expect(document.activeElement).toBe(screen.getByRole('main'))
  })
})
