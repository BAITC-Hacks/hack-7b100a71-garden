import { describe, expect, it } from 'vitest'
import { createMockApi } from './mockApi'
import { createApi } from '../services/api'
import { scenarioOptions } from './scenarios'
import { datasetValidationSuccess } from './datasetFixtures'

describe('mock dataset protocol', () => {
  it('returns predetermined responses without reading, parsing, or importing file content', async () => {
    const api = createMockApi({ latencyMs: 0, datasetLatencyMs: 0 })
    const files = [new File(['not valid json'], 'profiles.json')]
    const before = await api.getEmployees()
    const result = await api.validateDataset(files)
    expect(result).toMatchObject({ ...datasetValidationSuccess, validationId: 'demo-validation-1' })
    await expect(api.uploadDataset(files, result.validationId!)).resolves.toBeUndefined()
    await expect(api.uploadDataset(files, result.validationId!)).resolves.toBeUndefined()
    expect(await api.getEmployees()).toEqual(before)
  })

  it('rejects a changed batch or stale token and isolates returned validation details', async () => {
    const api = createMockApi({ datasetLatencyMs: 0 })
    const original = [new File(['sample'], 'profiles.json')]
    const first = await api.validateDataset(original)
    first.summary!.employees = 999
    const changed = [new File(['changed'], 'profiles.json')]
    await expect(api.uploadDataset(changed, first.validationId!)).rejects.toMatchObject({ code: 'INVALID_RESPONSE' })
    const second = await api.validateDataset(changed)
    expect(second.summary?.employees).toBe(3)
    await expect(api.uploadDataset(original, first.validationId!)).rejects.toMatchObject({ code: 'INVALID_RESPONSE' })
    await expect(api.uploadDataset(changed, second.validationId!)).resolves.toBeUndefined()
  })

  it('returns fixed validation errors without issuing an import token', async () => {
    const api = createMockApi({ ...scenarioOptions('dataset-invalid'), datasetLatencyMs: 0 })
    const files = [new File(['{}'], 'profiles.json')]
    expect(await api.validateDataset(files)).toMatchObject({ valid: false, validationId: null })
    await expect(api.uploadDataset(files, 'any-token')).rejects.toMatchObject({ code: 'INVALID_RESPONSE' })
  })

  it('keeps live dataset operations explicitly unconfigured', async () => {
    const api = createApi('real')
    await expect(api.validateDataset([])).rejects.toMatchObject({ code: 'CONFIGURATION' })
    await expect(api.uploadDataset([], 'token')).rejects.toMatchObject({ code: 'CONFIGURATION' })
  })
})
