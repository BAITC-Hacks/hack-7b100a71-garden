// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { App } from '../App'
import { api } from '../services/api'
import { queryKeys } from '../services/queryClient'
import { createMockApi, type MockOptions } from '../mocks/mockApi'
import { datasetValidationFailure, datasetValidationLong, datasetValidationPartial } from '../mocks/datasetFixtures'
import type { DatasetValidationResult } from '../types/domain'

vi.mock('../services/api', () => ({ apiMode: 'mock', api: {
  getEmployees: vi.fn(), getEmployee: vi.fn(), getRecommendations: vi.fn(), getEmployeeHistory: vi.fn(),
  getHRAnalytics: vi.fn(), validateDataset: vi.fn(), uploadDataset: vi.fn(), completeActivity: vi.fn(),
} }))

let client: QueryClient
function mount(options: MockOptions = {}, route = '/hr/dataset') {
  const adapter = createMockApi({ latencyMs: 0, datasetLatencyMs: 0, ...options })
  vi.mocked(api.getEmployees).mockImplementation(adapter.getEmployees)
  vi.mocked(api.getEmployee).mockImplementation(adapter.getEmployee)
  vi.mocked(api.getRecommendations).mockImplementation(adapter.getRecommendations)
  vi.mocked(api.getEmployeeHistory).mockImplementation(adapter.getEmployeeHistory)
  vi.mocked(api.getHRAnalytics).mockImplementation(adapter.getHRAnalytics)
  vi.mocked(api.validateDataset).mockImplementation(adapter.validateDataset)
  vi.mocked(api.uploadDataset).mockImplementation(adapter.uploadDataset)
  client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 30_000 } } })
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[route]}><App /></MemoryRouter></QueryClientProvider>)
}
function select(files = [new File(['unparsed dataset content'], 'employees.json', { type: 'application/json' })]) {
  fireEvent.change(screen.getByLabelText('Choose dataset files'), { target: { files } })
  return files
}
async function validate() {
  fireEvent.click(screen.getByRole('button', { name: 'Validate dataset' }))
  await screen.findByRole('heading', { name: 'Dataset validated successfully' })
}
beforeEach(() => { vi.clearAllMocks(); vi.stubGlobal('scrollTo', vi.fn()) })
afterEach(() => { cleanup(); client?.clear(); vi.unstubAllGlobals() })

describe('dataset upload interaction', () => {
  it('opens through HR navigation and exposes an accessible empty file selection', async () => {
    mount({}, '/hr')
    fireEvent.click(screen.getByRole('link', { name: 'Manage dataset' }))
    expect(screen.getByRole('heading', { name: 'Prepare the next dataset.' })).toBeTruthy()
    expect(within(screen.getByRole('navigation', { name: 'Your workspace' })).getByRole('link', { name: 'HR overview' }).getAttribute('aria-current')).toBe('page')
    expect(document.title).toBe('Manage dataset · Career Quest')
    expect(screen.getByText('No files selected')).toBeTruthy()
    const input = screen.getByLabelText('Choose dataset files') as HTMLInputElement
    expect(input.accept).toBe('.json,.csv')
    expect(input.multiple).toBe(true)
    expect((screen.getByRole('button', { name: 'Validate dataset' }) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByText(/preset responses/)).toBeTruthy()
    expect(api.validateDataset).not.toHaveBeenCalled()
  })

  it('lists file names and sizes, removes individual files, and supports reselecting the same filename', () => {
    mount()
    const files = select([new File(['{}'], 'employees.JSON'), new File(['a,b\n1,2'], 'history.csv')])
    const list = screen.getByRole('list', { name: 'Selected dataset files' })
    expect(within(list).getByText('employees.JSON')).toBeTruthy()
    expect(within(list).getByText('2 B')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Remove history.csv' }))
    expect(within(list).queryByText('history.csv')).toBeNull()
    select([files[0]])
    expect(within(screen.getByRole('list', { name: 'Selected dataset files' })).getAllByRole('listitem')).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: 'Clear selection' }))
    expect(screen.getByText('No files selected')).toBeTruthy()
  })

  it('supports drop selection and blocks unsupported formats without reading file contents', () => {
    mount()
    const dropzone = screen.getByText('Drop your dataset files here').parentElement!
    fireEvent.drop(dropzone, { dataTransfer: { files: [new File(['x'], 'dataset.xlsx'), new File(['broken json'], 'employees.json')] } })
    expect(screen.getByRole('alert').textContent).toContain('Remove or replace unsupported files')
    expect((screen.getByRole('button', { name: 'Validate dataset' }) as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(screen.getByRole('button', { name: 'Remove dataset.xlsx' }))
    expect((screen.getByRole('button', { name: 'Validate dataset' }) as HTMLButtonElement).disabled).toBe(false)
    expect(api.validateDataset).not.toHaveBeenCalled()
  })

  it('passes the original files to the adapter, locks selection while validating, and prevents duplicate validation', async () => {
    mount({ datasetLatencyMs: 80 })
    const files = select()
    const button = screen.getByRole('button', { name: 'Validate dataset' })
    fireEvent.click(button)
    fireEvent.click(button)
    expect(screen.getByRole('status').textContent).toContain('Validating dataset…')
    expect((screen.getByLabelText('Choose dataset files') as HTMLInputElement).disabled).toBe(true)
    expect((screen.getByRole('button', { name: 'Remove employees.json' }) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByText('employees.json')).toBeTruthy()
    expect(api.validateDataset).toHaveBeenCalledTimes(1)
    expect(vi.mocked(api.validateDataset).mock.calls[0][0][0]).toBe(files[0])
    await screen.findByRole('heading', { name: 'Dataset validated successfully' })
    expect(screen.getByRole('button', { name: 'Import dataset' })).toBeTruthy()
    expect(screen.getByRole('region', { name: 'Dataset summary' }).textContent).toContain('Activity history0')
    expect(screen.getByRole('list', { name: 'Warnings' })).toBeTruthy()
    expect(api.uploadDataset).not.toHaveBeenCalled()
  })

  it('displays backend-provided file, row, record, field and error messages without enabling import', async () => {
    mount({ datasetResponse: datasetValidationFailure })
    select()
    fireEvent.click(screen.getByRole('button', { name: 'Validate dataset' }))
    await screen.findByRole('heading', { name: 'The dataset needs attention' })
    const errors = screen.getByRole('list', { name: 'Validation errors' })
    expect(errors.textContent).toContain('Row8')
    expect(errors.textContent).toContain('Recordhistory-004')
    expect(errors.textContent).toContain('Fieldemployee_id')
    expect(errors.textContent).toContain('activity_history.csv')
    expect(errors.textContent).toContain('The referenced employee could not be found.')
    expect(screen.queryByRole('button', { name: 'Import dataset' })).toBeNull()
    expect(api.uploadDataset).not.toHaveBeenCalled()
  })

  it('shows long backend error lists in manageable batches', async () => {
    mount({ datasetResponse: datasetValidationLong })
    select()
    fireEvent.click(screen.getByRole('button', { name: 'Validate dataset' }))
    const errors = await screen.findByRole('list', { name: 'Validation errors' })
    expect(within(errors).getAllByRole('listitem')).toHaveLength(10)
    fireEvent.click(screen.getByRole('button', { name: 'Show more validation errors' }))
    expect(within(errors).getAllByRole('listitem')).toHaveLength(20)
  })

  it('invalidates validation authorization whenever files change or are removed', async () => {
    mount()
    select()
    await validate()
    select([new File(['changed'], 'employees.json')])
    expect(screen.queryByRole('button', { name: 'Import dataset' })).toBeNull()
    expect(screen.queryByRole('heading', { name: 'Dataset validated successfully' })).toBeNull()
    await validate()
    fireEvent.click(screen.getByRole('button', { name: 'Remove employees.json' }))
    expect(screen.queryByRole('button', { name: 'Import dataset' })).toBeNull()
    expect(api.uploadDataset).not.toHaveBeenCalled()
  })

  it('retries a validation request failure only on user action', async () => {
    mount({ failFirstValidation: true })
    select()
    fireEvent.click(screen.getByRole('button', { name: 'Validate dataset' }))
    await screen.findByRole('heading', { name: 'Validation could not be completed' })
    expect(api.validateDataset).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole('button', { name: 'Validate again' }))
    await screen.findByRole('heading', { name: 'Dataset validated successfully' })
    expect(api.validateDataset).toHaveBeenCalledTimes(2)
  })

  it('imports once, retains selected files, uses the supplied token, and refreshes relevant queries only', async () => {
    mount({ datasetLatencyMs: 60 })
    const files = select()
    await validate()
    client.setQueryData(queryKeys.employee('old-profile'), { id: 'old-profile' })
    client.setQueryData(queryKeys.recommendations('old-profile'), { employeeId: 'old-profile' })
    client.setQueryData(queryKeys.history('old-profile'), [])
    client.setQueryData(queryKeys.events, [])
    client.setQueryData(['unrelated-preference'], 'preserved')
    const initialReads = vi.mocked(api.getEmployees).mock.calls.length
    const button = screen.getByRole('button', { name: 'Import dataset' })
    fireEvent.click(button)
    fireEvent.click(button)
    expect(screen.getByRole('status').textContent).toContain('Importing dataset…')
    expect((screen.getByRole('button', { name: 'Remove employees.json' }) as HTMLButtonElement).disabled).toBe(true)
    expect(api.uploadDataset).toHaveBeenCalledTimes(1)
    expect(api.uploadDataset).toHaveBeenCalledWith(files, 'demo-validation-1')
    expect(await screen.findByText('Employee profiles and HR insights have been refreshed.')).toBeTruthy()
    expect(api.getEmployees).toHaveBeenCalledTimes(initialReads + 1)
    expect(api.getHRAnalytics).toHaveBeenCalledTimes(1)
    for (const key of [queryKeys.employee('old-profile'), queryKeys.recommendations('old-profile'), queryKeys.history('old-profile'), queryKeys.events]) expect(client.getQueryState(key)?.isInvalidated).toBe(true)
    expect(client.getQueryData(['unrelated-preference'])).toBe('preserved')
    expect(client.getQueryState(['unrelated-preference'])?.isInvalidated).toBe(false)
    expect(screen.getByRole('heading', { name: 'Prepare the next dataset.' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Import dataset' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Select another dataset' }))
    expect(screen.getByText('No files selected')).toBeTruthy()
  })

  it('retains the validated batch after import failure and allows an explicit retry', async () => {
    mount({ failFirstImport: true })
    const files = select()
    await validate()
    fireEvent.click(screen.getByRole('button', { name: 'Import dataset' }))
    await screen.findByRole('heading', { name: 'Import could not be completed' })
    expect(api.uploadDataset).toHaveBeenCalledTimes(1)
    expect(api.getHRAnalytics).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Retry import' }))
    await screen.findByText('Employee profiles and HR insights have been refreshed.')
    expect(api.uploadDataset).toHaveBeenCalledTimes(2)
    expect(api.uploadDataset).toHaveBeenLastCalledWith(files, 'demo-validation-1')
    expect(api.validateDataset).toHaveBeenCalledTimes(1)
  })

  it('keeps import acknowledgement on refresh failure and retries reads without repeating import', async () => {
    mount({ failDatasetRefresh: true })
    select()
    await validate()
    fireEvent.click(screen.getByRole('button', { name: 'Import dataset' }))
    await screen.findByRole('heading', { name: 'Import confirmed. Application data could not be refreshed.' })
    expect(screen.queryByRole('button', { name: 'Retry import' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Retry refresh' }))
    await screen.findByText('Employee profiles and HR insights have been refreshed.')
    expect(api.uploadDataset).toHaveBeenCalledTimes(1)
    expect(api.getHRAnalytics).toHaveBeenCalledTimes(2)
  })

  it.each<DatasetValidationResult>([{}, { valid: true }, { valid: true, validationId: '' }, { valid: true, validationId: 'token', errors: [{ message: 'Unresolved error' }] }])('blocks import for incomplete or conflicting validation responses %j', async (datasetResponse) => {
    mount({ datasetResponse })
    select()
    fireEvent.click(screen.getByRole('button', { name: 'Validate dataset' }))
    expect(await screen.findByRole('heading', { name: 'Validation couldn’t be confirmed' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Import dataset' })).toBeNull()
    expect(api.uploadDataset).not.toHaveBeenCalled()
  })

  it('handles a null validation response safely without authorizing import', async () => {
    mount()
    vi.mocked(api.validateDataset).mockResolvedValueOnce(null as unknown as DatasetValidationResult)
    select()
    fireEvent.click(screen.getByRole('button', { name: 'Validate dataset' }))
    expect(await screen.findByRole('heading', { name: 'Validation couldn’t be confirmed' })).toBeTruthy()
    expect(api.uploadDataset).not.toHaveBeenCalled()
  })

  it('displays supplied zero and missing summary values distinctly', async () => {
    mount({ datasetResponse: datasetValidationPartial })
    select()
    await validate()
    const summary = screen.getByRole('region', { name: 'Dataset summary' })
    expect(summary.textContent).toContain('Employees0')
    expect(summary.textContent).toContain('SkillsNo data available')
    expect(summary.textContent).not.toContain('Events')
    expect(screen.getByRole('button', { name: 'Import dataset' })).toBeTruthy()
  })

  it('allows a valid token without optional summary or warnings and handles errors without details', async () => {
    mount({ datasetResponse: { valid: true, validationId: 'opaque-token' } })
    select()
    await validate()
    expect(screen.getByText('No data available')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Import dataset' })).toBeTruthy()
    vi.mocked(api.validateDataset).mockResolvedValueOnce({ valid: false })
    fireEvent.click(screen.getByRole('button', { name: 'Validate again' }))
    expect(await screen.findByText('No detailed validation errors were returned.')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Import dataset' })).toBeNull()
  })

  it('preserves selection and an in-flight import across HR navigation without resubmitting', async () => {
    mount({ datasetLatencyMs: 80 })
    select()
    await validate()
    fireEvent.click(screen.getByRole('button', { name: 'Import dataset' }))
    fireEvent.click(within(screen.getByRole('navigation', { name: 'Your workspace' })).getByRole('link', { name: 'HR overview' }))
    await screen.findByRole('link', { name: 'Manage dataset' })
    fireEvent.click(screen.getByRole('link', { name: 'Manage dataset' }))
    await screen.findByText('Employee profiles and HR insights have been refreshed.')
    expect(api.uploadDataset).toHaveBeenCalledTimes(1)
    expect(screen.getByText('employees.json')).toBeTruthy()
  })
})
