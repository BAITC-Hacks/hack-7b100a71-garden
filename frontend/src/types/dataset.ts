import type { DatasetValidationResult } from './domain'

export interface DatasetUploadState {
  files: File[]
  phase: 'idle' | 'validating' | 'validated' | 'invalid' | 'incomplete' | 'validation-error' | 'importing' | 'import-error' | 'refreshing' | 'refresh-error' | 'success'
  result?: DatasetValidationResult
  error?: string
}

export const emptyDatasetUpload: DatasetUploadState = { files: [], phase: 'idle' }
export const isDatasetBusy = ({ phase }: DatasetUploadState) => phase === 'validating' || phase === 'importing' || phase === 'refreshing'
export const isDatasetImported = ({ phase }: DatasetUploadState) => phase === 'refreshing' || phase === 'refresh-error' || phase === 'success'
export function hasImportAuthorization(result?: DatasetValidationResult) {
  return result?.valid === true && typeof result.validationId === 'string' && result.validationId.trim().length > 0 && !result.errors?.length
}
