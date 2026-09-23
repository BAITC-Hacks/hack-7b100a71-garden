import { ApiError, type CareerApi, type RequestOptions } from '../types/api'
import type { DatasetFileRole, DatasetMode, DatasetRequestOptions } from '../types/dataset'
import type { DatasetIssue, DatasetValidationResult } from '../types/domain'
import { isDatasetSelectionReady } from './datasetConfig'
import type { HttpClient } from './httpClient'

const formFields: Record<DatasetFileRole, string> = {
  employees: 'employees_file', activityHistory: 'activity_history_file', events: 'events_file', skills: 'skills_file',
}
type DatasetOptions = RequestOptions & DatasetRequestOptions
interface CheckedSelection { id: string; files: File[]; fileRoles: DatasetFileRole[]; mode: DatasetMode }
type RawRecord = Record<string, unknown>
const record = (value: unknown): RawRecord => value && typeof value === 'object' && !Array.isArray(value) ? value as RawRecord : {}

function mapIssues(value: unknown): DatasetIssue[] | undefined {
  if (!Array.isArray(value)) return undefined
  return value.map((issue) => {
    const raw = record(issue)
    return { code: typeof raw.code === 'string' ? raw.code : undefined,
      location: typeof raw.location === 'string' ? raw.location : undefined,
      message: typeof raw.message === 'string' ? raw.message : undefined }
  })
}
function mapValidation(value: unknown): DatasetValidationResult {
  const raw = record(value)
  const counts = record(raw.counts)
  const result: DatasetValidationResult = {
    valid: typeof raw.valid === 'boolean' ? raw.valid : undefined,
    mode: raw.mode === 'append' || raw.mode === 'replace' ? raw.mode : undefined,
    version: typeof raw.version === 'number' ? raw.version : undefined,
    errors: mapIssues(raw.errors),
  }
  const fields = { employees: 'employees', skills: 'skills', role_profiles: 'roleProfiles', events: 'events', history: 'activityHistory' } as const
  for (const [source, target] of Object.entries(fields)) {
    if (counts[source] == null || typeof counts[source] === 'number') {
      if (source in counts) { result.summary ??= {}; result.summary[target] = counts[source] as number | null }
    }
  }
  return result
}
function formFor(files: File[], fileRoles: DatasetFileRole[]) {
  const form = new FormData()
  files.forEach((file, index) => form.append(formFields[fileRoles[index]], file, file.name))
  return form
}

// The server returns no validation token and revalidates on upload. This local
// receipt only binds the UI's checked files/mode/roles; it is never transmitted.
// An upload consumes the receipt before dispatch and is never replayed here.
export function createHttpDatasetApi(client: HttpClient, onImported?: () => void): Pick<CareerApi, 'validateDataset' | 'uploadDataset'> {
  let checked: CheckedSelection | undefined
  let sequence = 0
  function selection(files: File[], options: DatasetOptions = {}) {
    const mode = options.mode ?? 'append'
    const fileRoles = options.fileRoles ?? []
    if (!isDatasetSelectionReady(files, fileRoles, mode)) throw new ApiError('VALIDATION', 'Choose the required file roles before validating the dataset.')
    return { mode, fileRoles }
  }
  return {
    async validateDataset(files, options = {}) {
      checked = undefined
      const { mode, fileRoles } = selection(files, options)
      let result: DatasetValidationResult
      try {
        result = mapValidation(await client.request<unknown>(`/datasets/validate?mode=${mode}`, { method: 'POST', body: formFor(files, fileRoles), signal: options.signal }))
      } catch (error) {
        if (!(error instanceof ApiError) || error.code !== 'VALIDATION' || !error.details?.length) throw error
        return { valid: false, errors: mapIssues(error.details) }
      }
      if (result.mode && result.mode !== mode) throw new ApiError('INVALID_RESPONSE', 'The validation response does not match the selected import mode.')
      if (result.valid === true && Array.isArray(result.errors) && !result.errors.length) {
        result.validationId = `local-selection-${++sequence}`
        checked = { id: result.validationId, files: [...files], fileRoles: [...fileRoles], mode }
      }
      return result
    },
    async uploadDataset(files, validationId, options = {}) {
      const { mode, fileRoles } = selection(files, options)
      const batch = checked
      if (!batch || batch.id !== validationId || batch.mode !== mode || files.length !== batch.files.length || files.some((file, index) => file !== batch.files[index] || fileRoles[index] !== batch.fileRoles[index])) {
        throw new ApiError('VALIDATION', 'Validate the selected files and import mode again before importing.')
      }
      checked = undefined
      const result = record(await client.request<unknown>(`/datasets/upload?mode=${mode}`, { method: 'POST', body: formFor(files, fileRoles), signal: options.signal }))
      if (result.uploaded !== true || (result.mode !== undefined && result.mode !== mode)) throw new ApiError('INVALID_RESPONSE', 'The server did not confirm the import outcome. Check the dataset before submitting it again.')
      onImported?.()
    },
  }
}
