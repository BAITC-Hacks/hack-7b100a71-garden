import type { DatasetValidationResult } from './domain'

export type DatasetMode = 'append' | 'replace'
export type DatasetFileRole = 'employees' | 'activityHistory' | 'events' | 'skills'
export interface DatasetRequestOptions { mode?: DatasetMode; fileRoles?: DatasetFileRole[] }

export interface DatasetUploadState {
  files: File[]
  mode: DatasetMode
  fileRoles: Array<DatasetFileRole | ''>
  phase: 'idle' | 'validating' | 'validated' | 'invalid' | 'incomplete' | 'validation-error' | 'importing' | 'import-error' | 'import-uncertain' | 'checking-import' | 'refreshing' | 'refresh-error' | 'success'
  result?: DatasetValidationResult
  error?: string
}

export const emptyDatasetUpload: DatasetUploadState = { files: [], mode: 'append', fileRoles: [], phase: 'idle' }
export const isDatasetBusy = ({ phase }: DatasetUploadState) => phase === 'validating' || phase === 'importing' || phase === 'refreshing' || phase === 'checking-import'
export const isDatasetImported = ({ phase }: DatasetUploadState) => phase === 'refreshing' || phase === 'refresh-error' || phase === 'success'
export const isDatasetUncertain = ({ phase }: DatasetUploadState) => phase === 'import-uncertain' || phase === 'checking-import'
export function hasImportAuthorization(result?: DatasetValidationResult) {
  return result?.valid === true && typeof result.validationId === 'string' && result.validationId.trim().length > 0 && !result.errors?.length
}
