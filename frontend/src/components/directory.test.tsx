// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { EmployeeDirectory } from '../pages/EmployeeDirectory'

const runtime = vi.hoisted(() => ({ mode: 'mock' }))
vi.mock('../services/api', () => ({ get apiMode() { return runtime.mode } }))
vi.mock('../hooks/useEmployees', () => ({ useEmployees: () => ({
  data: [{ id: 'directory-profile', name: 'Directory Employee', role: 'Developer', grade: 'Middle', department: 'Engineering' }],
  isPending: false, isError: false,
}) }))

beforeEach(() => { runtime.mode = 'mock' })
afterEach(cleanup)

describe('employee directory data-source wording', () => {
  it('identifies mock profiles as sample data', () => {
    render(<MemoryRouter><EmployeeDirectory /></MemoryRouter>)
    expect(screen.getByText('Demo workspace')).toBeTruthy()
    expect(screen.getByText('You’re exploring with sample profiles.')).toBeTruthy()
  })

  it('does not describe live employees as sample or demo profiles', () => {
    runtime.mode = 'real'
    const { container } = render(<MemoryRouter><EmployeeDirectory /></MemoryRouter>)
    expect(screen.getByText('EMPLOYEE PROFILES')).toBeTruthy()
    expect(container.textContent).not.toMatch(/sample|demo workspace/i)
    expect(screen.getByRole('link', { name: /Directory Employee/ }).getAttribute('href')).toBe('/employees/directory-profile')
  })
})
