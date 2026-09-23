// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../services/api'
import { queryKeys } from '../services/queryClient'
import { createMockApi } from '../mocks/mockApi'
import { idleCompletion, type CompletionState } from '../types/completion'
import { emptyDatasetUpload, type DatasetUploadState } from '../types/dataset'
import { useActivityCompletion } from '../hooks/useActivityCompletion'
import { useDatasetUpload } from '../hooks/useDatasetUpload'
import { DatasetUpload } from './dataset/DatasetUpload'
import { RecommendationList } from './RecommendationList'
import { mutationCopy } from '../i18n/mutations'

vi.mock('../services/api', () => ({ apiMode: 'mock', api: {
  getEmployees: vi.fn(), getEmployee: vi.fn(), getRecommendations: vi.fn(), getEmployeeHistory: vi.fn(),
  getHRAnalytics: vi.fn(), completeActivity: vi.fn(), validateDataset: vi.fn(), uploadDataset: vi.fn(),
} }))
let client: QueryClient
const recommendation = { eventId: 'demo-system-design', title: 'Designing High-Load Systems' }
function Actions() {
  const completion = useActivityCompletion('demo-aigerim')
  const upload = useDatasetUpload()
  return <>
    <RecommendationList recommendations={[recommendation]} completion={completion.state} blockedReason={completion.blockedReason}
      onStart={(item) => void completion.complete(item)} onRetry={() => void completion.retryCompletion()} onRefresh={() => void completion.retryRefresh()} />
    <DatasetUpload />
    <button onClick={() => { void completion.complete(recommendation); void upload.importDataset() }}>Complete then import</button>
    <button onClick={() => { void upload.importDataset(); void completion.complete(recommendation) }}>Import then complete</button>
    <button onClick={() => void upload.importDataset()}>Invoke import</button>
    <button onClick={() => void completion.complete(recommendation)}>Invoke completion</button>
  </>
}
function mount() {
  client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } })
  client.setQueryData(queryKeys.datasetUpload, { ...emptyDatasetUpload, phase: 'validated',
    files: [new File(['{}'], 'employees.json')], fileRoles: ['employees'], result: { valid: true, validationId: 'local-receipt' },
  } satisfies DatasetUploadState)
  render(<QueryClientProvider client={client}><Actions /></QueryClientProvider>)
}
beforeEach(() => {
  vi.clearAllMocks()
  const adapter = createMockApi({ latencyMs: 0, completionLatencyMs: 0 })
  vi.mocked(api.getEmployees).mockImplementation(adapter.getEmployees)
  vi.mocked(api.getEmployee).mockImplementation(adapter.getEmployee)
  vi.mocked(api.getRecommendations).mockImplementation(adapter.getRecommendations)
  vi.mocked(api.getEmployeeHistory).mockImplementation(adapter.getEmployeeHistory)
  vi.mocked(api.getHRAnalytics).mockImplementation(adapter.getHRAnalytics)
  vi.mocked(api.completeActivity).mockImplementation(adapter.completeActivity)
  vi.mocked(api.uploadDataset).mockResolvedValue()
})
afterEach(() => { cleanup(); client?.clear() })

describe('cross-route mutation coordination', () => {
  it('blocks import synchronously when an employee completion starts and unlocks after refresh', async () => {
    let finish!: () => void
    vi.mocked(api.completeActivity).mockImplementation(() => new Promise<void>((resolve) => { finish = resolve }))
    mount()
    fireEvent.click(screen.getByRole('button', { name: 'Complete then import' }))
    expect(api.completeActivity).toHaveBeenCalledTimes(1)
    expect(api.uploadDataset).not.toHaveBeenCalled()
    await waitFor(() => expect((screen.getByRole('button', { name: 'Import dataset' }) as HTMLButtonElement).disabled).toBe(true))
    expect(screen.getByText(mutationCopy.datasetBlocked)).toBeTruthy()
    await act(async () => finish())
    await waitFor(() => expect((screen.getByRole('button', { name: 'Import dataset' }) as HTMLButtonElement).disabled).toBe(false))
    expect(screen.queryByText(mutationCopy.datasetBlocked)).toBeNull()
  })

  it('blocks completion synchronously when dataset import starts and unlocks after refresh', async () => {
    let finish!: () => void
    vi.mocked(api.uploadDataset).mockImplementation(() => new Promise<void>((resolve) => { finish = resolve }))
    mount()
    fireEvent.click(screen.getByRole('button', { name: 'Import then complete' }))
    expect(api.uploadDataset).toHaveBeenCalledTimes(1)
    expect(api.completeActivity).not.toHaveBeenCalled()
    await waitFor(() => expect(screen.getByRole('button', { name: 'Complete development step' }).matches(':disabled')).toBe(true))
    expect(screen.getByText(mutationCopy.completionBlocked)).toBeTruthy()
    await act(async () => finish())
    await waitFor(() => expect(screen.getByRole('button', { name: 'Complete development step' }).matches(':disabled')).toBe(false))
    expect(screen.queryByText(mutationCopy.completionBlocked)).toBeNull()
  })

  it.each(['submitting', 'refreshing', 'refresh-error'] as const)('observes another employee’s %s state and prevents programmatic import', async (phase) => {
    mount()
    act(() => client.setQueryData(queryKeys.completion('another-employee'), { ...idleCompletion, phase } satisfies CompletionState))
    await waitFor(() => expect((screen.getByRole('button', { name: 'Import dataset' }) as HTMLButtonElement).disabled).toBe(true))
    fireEvent.click(screen.getByRole('button', { name: 'Invoke import' }))
    expect(api.uploadDataset).not.toHaveBeenCalled()
    act(() => client.setQueryData(queryKeys.completion('another-employee'), { ...idleCompletion, phase: 'success' } satisfies CompletionState))
    await waitFor(() => expect((screen.getByRole('button', { name: 'Import dataset' }) as HTMLButtonElement).disabled).toBe(false))
  })

  it.each(['importing', 'refreshing', 'refresh-error', 'import-uncertain', 'checking-import'] as const)('observes dataset %s and prevents programmatic completion', async (phase) => {
    mount()
    act(() => client.setQueryData<DatasetUploadState>(queryKeys.datasetUpload, (previous) => ({ ...previous!, phase })))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Complete development step' }).matches(':disabled')).toBe(true))
    fireEvent.click(screen.getByRole('button', { name: 'Invoke completion' }))
    expect(api.completeActivity).not.toHaveBeenCalled()
    expect(screen.getByText(mutationCopy.completionBlocked)).toBeTruthy()
  })
})
