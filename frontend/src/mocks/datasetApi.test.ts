import { describe, expect, it } from 'vitest'
import { createMockApi } from './mockApi'
import { createApi } from '../services/api'
import { scenarioOptions } from './scenarios'
import { datasetValidationSuccess } from './datasetFixtures'
import type { DatasetRequestOptions } from '../types/dataset'

const selection: DatasetRequestOptions = { mode: 'append', fileRoles: ['employees'] }

describe('mock dataset protocol', () => {
  it('returns predetermined responses without reading, parsing, or importing file content', async () => {
    const api = createMockApi({ latencyMs: 0, datasetLatencyMs: 0 })
    const files = [new File(['not valid json'], 'profiles.json')]
    const before = await api.getEmployees()
    const result = await api.validateDataset(files, selection)
    expect(result).toMatchObject({ ...datasetValidationSuccess, validationId: 'demo-validation-1' })
    await expect(api.uploadDataset(files, result.validationId!, selection)).resolves.toBeUndefined()
    await expect(api.uploadDataset(files, result.validationId!, selection)).rejects.toMatchObject({ code: 'VALIDATION' })
    expect(await api.getEmployees()).toEqual(before)
  })

  it('rejects a changed batch or stale token and isolates returned validation details', async () => {
    const api = createMockApi({ datasetLatencyMs: 0 })
    const original = [new File(['sample'], 'profiles.json')]
    const first = await api.validateDataset(original, selection)
    first.summary!.employees = 999
    const changed = [new File(['changed'], 'profiles.json')]
    await expect(api.uploadDataset(changed, first.validationId!, selection)).rejects.toMatchObject({ code: 'VALIDATION' })
    const second = await api.validateDataset(changed, selection)
    expect(second.summary?.employees).toBe(3)
    await expect(api.uploadDataset(original, first.validationId!, selection)).rejects.toMatchObject({ code: 'VALIDATION' })
    await expect(api.uploadDataset(changed, second.validationId!, selection)).resolves.toBeUndefined()
  })

  it('returns fixed validation errors without issuing an import token', async () => {
    const api = createMockApi({ ...scenarioOptions('dataset-invalid'), datasetLatencyMs: 0 })
    const files = [new File(['{}'], 'profiles.json')]
    expect(await api.validateDataset(files, selection)).toMatchObject({ valid: false, validationId: null })
    await expect(api.uploadDataset(files, 'any-token', selection)).rejects.toMatchObject({ code: 'VALIDATION' })
  })

  it('requires configured HTTP access and a checked local selection in real mode', async () => {
    const api = createApi('real')
    const files = [new File(['unparsed'], 'employees.json')]
    await expect(api.validateDataset(files, selection)).rejects.toMatchObject({ code: 'CONFIGURATION' })
    await expect(api.uploadDataset(files, 'token', selection)).rejects.toMatchObject({ code: 'VALIDATION' })
  })
})
