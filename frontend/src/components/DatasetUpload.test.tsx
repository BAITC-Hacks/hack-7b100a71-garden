// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DatasetUpload } from './DatasetUpload'
import { ApiError } from '../types/api'
import type { DatasetValidationResult } from '../types/domain'

const mocked = vi.hoisted(() => ({ validateDataset: vi.fn(), uploadDataset: vi.fn() }))
vi.mock('../services/api', () => ({ api: mocked }))
const valid: DatasetValidationResult = { valid: true, mode: 'append', version: 4, counts: { employees: 201, skills: 60, role_profiles: 32, events: 40, history: 2743 }, errors: [] }
function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const invalidation = vi.spyOn(client, 'invalidateQueries')
  render(<QueryClientProvider client={client}><DatasetUpload /></QueryClientProvider>)
  return { client, invalidation }
}
function selectFile(label: string, name: string) {
  const file = new File(['uploaded file content'], name)
  fireEvent.change(screen.getByLabelText(new RegExp(label.replace('.', '\\.'))), { target: { files: [file] } })
  return file
}
const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement

beforeEach(() => { vi.resetAllMocks(); mocked.validateDataset.mockResolvedValue(valid); mocked.uploadDataset.mockResolvedValue({ uploaded: true, mode: 'append', counts: valid.counts, version: 5 }) })
afterEach(cleanup)

describe('dataset validation and upload interactions', () => {
  it('validates selected append sections, uploads the same files and refreshes all snapshot queries', async () => {
    const { invalidation } = setup()
    expect(button('Validate files').disabled).toBe(true)
    expect(button('Upload validated files').disabled).toBe(true)
    const employees = selectFile('employees.json', 'jury-profiles.json')
    const history = selectFile('activity_history.csv', 'jury-history.csv')
    fireEvent.click(button('Validate files'))
    await screen.findByText('Validation passed')
    expect(mocked.validateDataset).toHaveBeenCalledWith({ employees_file: employees, activity_history_file: history }, 'append')
    expect(mocked.uploadDataset).not.toHaveBeenCalled()
    expect(screen.getByText('201')).toBeTruthy()
    fireEvent.click(button('Upload validated files'))
    await screen.findByText('Dataset uploaded')
    expect(mocked.uploadDataset).toHaveBeenCalledWith({ employees_file: employees, activity_history_file: history }, 'append')
    await waitFor(() => expect(invalidation).toHaveBeenCalledWith())
    expect(button('Upload validated files').disabled).toBe(true)
  })
  it('clears successful validation when a selected file or import mode changes', async () => {
    setup()
    selectFile('employees.json', 'first.json')
    fireEvent.click(button('Validate files')); await screen.findByText('Validation passed')
    selectFile('employees.json', 'changed.json')
    expect(button('Upload validated files').disabled).toBe(true)
    expect(screen.queryByText('Validation passed')).toBeNull()
    fireEvent.click(button('Validate files')); await screen.findByText('Validation passed')
    fireEvent.click(screen.getByRole('radio', { name: 'Replace complete dataset' }))
    expect(screen.queryByText('Validation passed')).toBeNull()
    expect(button('Upload replacement').disabled).toBe(true)
    expect(button('Validate files').disabled).toBe(true)
  })
  it('requires all four explicit sections before validating a replacement', async () => {
    mocked.validateDataset.mockResolvedValue({ ...valid, mode: 'replace' })
    mocked.uploadDataset.mockResolvedValue({ uploaded: true, mode: 'replace', counts: valid.counts, version: 5 })
    setup()
    fireEvent.click(screen.getByRole('radio', { name: 'Replace complete dataset' }))
    const employees = selectFile('employees.json', 'new-employees.json')
    const skills = selectFile('skills.json', 'new-skills.json')
    const events = selectFile('events.json', 'new-events.json')
    expect(button('Validate files').disabled).toBe(true)
    const history = selectFile('activity_history.csv', 'new-history.csv')
    fireEvent.click(button('Validate files')); await screen.findByText('Validation passed')
    const files = { employees_file: employees, skills_file: skills, events_file: events, activity_history_file: history }
    expect(mocked.validateDataset).toHaveBeenCalledWith(files, 'replace')
    fireEvent.click(button('Upload replacement')); await screen.findByText('Dataset uploaded')
    expect(mocked.uploadDataset).toHaveBeenCalledWith(files, 'replace')
  })
  it('shows structured invalid results without uploading or invalidating the active data', async () => {
    mocked.validateDataset.mockResolvedValue({ ...valid, valid: false, counts: {}, errors: [{ code: 'unknown_role', location: 'employees[0].role', message: 'Role is not in the uploaded catalog' }] })
    const { invalidation } = setup()
    selectFile('employees.json', 'invalid.json')
    fireEvent.click(button('Validate files')); await screen.findByText('Validation failed')
    expect(screen.getByRole('alert').textContent).toContain('employees[0].role')
    expect(screen.getByRole('alert').textContent).toContain('unknown_role')
    expect(button('Upload validated files').disabled).toBe(true)
    expect(mocked.uploadDataset).not.toHaveBeenCalled()
    expect(invalidation).not.toHaveBeenCalled()
  })
  it('preserves upload backend errors and leaves queries untouched after rejection', async () => {
    mocked.uploadDataset.mockRejectedValue(new ApiError('BACKEND', 'Dataset validation failed; no changes were applied', { status: 422, backendCode: 'invalid_dataset', details: [{ code: 'duplicate_id', location: 'employees', message: 'Employee already exists' }] }))
    const { invalidation } = setup()
    selectFile('employees.json', 'duplicate.json')
    fireEvent.click(button('Validate files')); await screen.findByText('Validation passed')
    fireEvent.click(button('Upload validated files'))
    await screen.findByText('invalid_dataset')
    expect(screen.getByRole('alert').textContent).toContain('HTTP 422')
    expect(screen.getByRole('alert').textContent).toContain('duplicate_id')
    expect(screen.queryByText('Dataset uploaded')).toBeNull()
    expect(invalidation).not.toHaveBeenCalled()
  })
  it('disables file changes and repeated uploads while a request is pending', async () => {
    let resolveUpload: (value: unknown) => void = () => undefined
    mocked.uploadDataset.mockReturnValue(new Promise((resolve) => { resolveUpload = resolve }))
    setup()
    selectFile('employees.json', 'new.json')
    fireEvent.click(button('Validate files')); await screen.findByText('Validation passed')
    fireEvent.click(button('Upload validated files'))
    expect(button('Uploading…').disabled).toBe(true)
    expect(screen.getByRole('group', { name: 'Import mode' }).hasAttribute('disabled')).toBe(true)
    fireEvent.click(button('Uploading…'))
    expect(mocked.uploadDataset).toHaveBeenCalledTimes(1)
    resolveUpload({ uploaded: true, mode: 'append', counts: valid.counts, version: 5 })
    await screen.findByText('Dataset uploaded')
  })
})
