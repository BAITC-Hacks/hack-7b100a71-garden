import { describe, expect, it, vi } from 'vitest'
import { ApiError } from '../types/api'
import type { DatasetRequestOptions } from '../types/dataset'
import { createHttpDatasetApi } from './httpDatasetApi'
import type { HttpClient } from './httpClient'

const options: DatasetRequestOptions = { mode: 'append', fileRoles: ['employees'] }
function setup() {
  const request = vi.fn<HttpClient['request']>()
  const adapter = createHttpDatasetApi({ request: request as HttpClient['request'], requestEnvelope: vi.fn() })
  const files = [new File(['not parsed by frontend'], 'employees.json')]
  return { request, adapter, files }
}
describe('real dataset contract', () => {
  it('sends multipart file roles and query mode, maps server counts, and never sends the local receipt', async () => {
    const { request, adapter, files } = setup()
    request.mockResolvedValueOnce({ valid: true, counts: { employees: 4, skills: 0, role_profiles: 3, events: 7, history: 2 }, errors: [], mode: 'append', version: 9 })
      .mockResolvedValueOnce({ uploaded: true, mode: 'append', version: 10 })
    const result = await adapter.validateDataset(files, options)
    expect(result).toMatchObject({ valid: true, mode: 'append', version: 9, summary: { employees: 4, skills: 0, roleProfiles: 3, events: 7, activityHistory: 2 } })
    expect(result.summary).not.toHaveProperty('recordsProcessed')
    expect(request.mock.calls[0][0]).toBe('/datasets/validate?mode=append')
    const form = request.mock.calls[0][1]!.body as FormData
    expect(Array.from(form.keys())).toEqual(['employees_file'])
    expect(await (form.get('employees_file') as File).text()).toBe('not parsed by frontend')
    await adapter.uploadDataset(files, result.validationId!, options)
    expect(request.mock.calls[1][0]).toBe('/datasets/upload?mode=append')
    const upload = request.mock.calls[1][1]!
    expect(Array.from((upload.body as FormData).keys())).toEqual(['employees_file'])
    expect(upload.headers).toBeUndefined()
    await expect(adapter.uploadDataset(files, result.validationId!, options)).rejects.toMatchObject({ code: 'VALIDATION' })
    expect(request).toHaveBeenCalledTimes(2)
  })

  it('requires explicit unique roles and all four files for replacement without reading records', async () => {
    const { request, adapter, files } = setup()
    await expect(adapter.validateDataset(files)).rejects.toMatchObject({ code: 'VALIDATION' })
    await expect(adapter.validateDataset(files, { ...options, mode: 'replace' })).rejects.toMatchObject({ code: 'VALIDATION' })
    await expect(adapter.validateDataset([files[0], files[0]], { fileRoles: ['employees', 'employees'] })).rejects.toMatchObject({ code: 'VALIDATION' })
    await expect(adapter.validateDataset(files, { fileRoles: ['events'] })).rejects.toMatchObject({ code: 'VALIDATION' })
    expect(request).not.toHaveBeenCalled()
    request.mockResolvedValueOnce({ valid: true, errors: [], mode: 'replace' })
    const allFiles = ['employees', 'history', 'events', 'skills'].map((name) => new File(['unparsed'], `${name}.json`))
    await adapter.validateDataset(allFiles, { mode: 'replace', fileRoles: ['employees', 'activityHistory', 'events', 'skills'] })
    expect(request.mock.calls[0][0]).toBe('/datasets/validate?mode=replace')
    expect(Array.from((request.mock.calls[0][1]!.body as FormData).keys())).toEqual(['employees_file', 'activity_history_file', 'events_file', 'skills_file'])
  })

  it('maps validation issues without inventing field, row, or file interpretations', async () => {
    const { request, adapter, files } = setup()
    const errors = [{ code: 'invalid_reference', location: 'employees[0].skill_ids', message: 'Unknown skill.' }]
    request.mockResolvedValueOnce({ valid: false, counts: {}, errors })
    const result = await adapter.validateDataset(files, options)
    expect(result.errors).toEqual(errors)
    expect(result.validationId).toBeUndefined()
    expect(result.summary).toBeUndefined()
    request.mockRejectedValueOnce(new ApiError('VALIDATION', 'Invalid files.', { status: 422, details: errors }))
    expect(await adapter.validateDataset(files, options)).toEqual({ valid: false, errors })
  })

  it('binds the receipt to original file objects, roles and mode and invalidates old validation', async () => {
    const { request, adapter, files } = setup()
    request.mockResolvedValue({ valid: true, errors: [] })
    const first = await adapter.validateDataset(files, options)
    await expect(adapter.uploadDataset([new File(['changed'], 'employees.json')], first.validationId!, options)).rejects.toMatchObject({ code: 'VALIDATION' })
    await expect(adapter.uploadDataset(files, first.validationId!, { fileRoles: ['activityHistory'] })).rejects.toMatchObject({ code: 'VALIDATION' })
    const next = await adapter.validateDataset(files, options)
    expect(next.validationId).not.toBe(first.validationId)
    await expect(adapter.uploadDataset(files, first.validationId!, options)).rejects.toMatchObject({ code: 'VALIDATION' })
    expect(request).toHaveBeenCalledTimes(2)
  })

  it.each(['NETWORK', 'TIMEOUT', 'UNAVAILABLE'] as const)('does not replay ambiguous upload failures: %s', async (code) => {
    const { request, adapter, files } = setup()
    request.mockResolvedValueOnce({ valid: true, errors: [] }).mockRejectedValueOnce(new ApiError(code, 'Response lost.'))
    const result = await adapter.validateDataset(files, options)
    await expect(adapter.uploadDataset(files, result.validationId!, options)).rejects.toMatchObject({ code })
    await expect(adapter.uploadDataset(files, result.validationId!, options)).rejects.toMatchObject({ code: 'VALIDATION' })
    expect(request).toHaveBeenCalledTimes(2)
  })

  it('never confirms malformed validation or import results', async () => {
    const { request, adapter, files } = setup()
    request.mockResolvedValueOnce({}).mockResolvedValueOnce({ valid: true, errors: [{ message: 'Conflict' }] })
    expect((await adapter.validateDataset(files, options)).validationId).toBeUndefined()
    expect((await adapter.validateDataset(files, options)).validationId).toBeUndefined()
    request.mockResolvedValueOnce({ valid: true, errors: [], mode: 'replace' })
    await expect(adapter.validateDataset(files, options)).rejects.toMatchObject({ code: 'INVALID_RESPONSE' })
    request.mockResolvedValueOnce({ valid: true, errors: [] }).mockResolvedValueOnce({})
    const result = await adapter.validateDataset(files, options)
    await expect(adapter.uploadDataset(files, result.validationId!, options)).rejects.toMatchObject({ code: 'INVALID_RESPONSE' })
  })

  it('clears dependent adapter caches only after a confirmed import', async () => {
    const request = vi.fn<HttpClient['request']>()
    const onImported = vi.fn()
    const adapter = createHttpDatasetApi({ request: request as HttpClient['request'], requestEnvelope: vi.fn() }, onImported)
    const files = [new File(['unparsed'], 'employees.json')]
    request.mockResolvedValueOnce({ valid: true, errors: [] }).mockRejectedValueOnce(new ApiError('NETWORK', 'Response lost.'))
    const failed = await adapter.validateDataset(files, options)
    await expect(adapter.uploadDataset(files, failed.validationId!, options)).rejects.toThrow()
    expect(onImported).not.toHaveBeenCalled()
    request.mockResolvedValueOnce({ valid: true, errors: [] }).mockResolvedValueOnce({ uploaded: true })
    const confirmed = await adapter.validateDataset(files, options)
    await adapter.uploadDataset(files, confirmed.validationId!, options)
    expect(onImported).toHaveBeenCalledTimes(1)
  })

  it('does not issue a selection receipt without the validation errors array', async () => {
    const { request, adapter, files } = setup()
    request.mockResolvedValueOnce({ valid: true })
    expect((await adapter.validateDataset(files, options)).validationId).toBeUndefined()
  })
})
