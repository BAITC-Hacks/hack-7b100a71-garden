import { skipToken, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import { isSupportedDatasetFile } from '../services/datasetConfig'
import { queryKeys } from '../services/queryClient'
import { refreshDatasetState } from '../services/refreshDatasetState'
import { ApiError } from '../types/api'
import { emptyDatasetUpload, hasImportAuthorization, isDatasetBusy, isDatasetImported, type DatasetUploadState } from '../types/dataset'

export function useDatasetUpload() {
  const client = useQueryClient()
  const key = queryKeys.datasetUpload
  // In-memory selection and acknowledgement survive route changes. Never persisted.
  const { data: state = emptyDatasetUpload } = useQuery<DatasetUploadState>({ queryKey: key, queryFn: skipToken,
    initialData: emptyDatasetUpload, staleTime: Infinity, gcTime: Infinity })
  const current = () => client.getQueryData<DatasetUploadState>(key) ?? emptyDatasetUpload
  const update = (patch: Partial<DatasetUploadState>) => client.setQueryData<DatasetUploadState>(key, { ...current(), ...patch })

  function selectFiles(files: File[]) {
    if (isDatasetBusy(current()) || isDatasetImported(current())) return
    client.setQueryData(key, { files, phase: 'idle' } satisfies DatasetUploadState)
  }
  function removeFile(index: number) { selectFiles(current().files.filter((_, position) => position !== index)) }
  function reset() {
    if (isDatasetBusy(current())) return
    client.setQueryData(key, emptyDatasetUpload)
  }

  async function validate() {
    const latest = current()
    if (isDatasetBusy(latest) || isDatasetImported(latest) || !latest.files.length || !latest.files.every(isSupportedDatasetFile)) return
    // Cache updates are synchronous: repeated clicks cannot dispatch twice.
    update({ phase: 'validating', result: undefined, error: undefined })
    try {
      const result = await api.validateDataset(latest.files)
      update({ result: result ?? {}, phase: hasImportAuthorization(result) ? 'validated' : result?.valid === false ? 'invalid' : 'incomplete' })
    } catch (error) {
      update({ phase: 'validation-error', error: error instanceof ApiError ? error.message : undefined })
    }
  }

  async function refresh() {
    update({ phase: 'refreshing', error: undefined })
    try {
      await refreshDatasetState(api, client)
      update({ phase: 'success' })
    } catch {
      update({ phase: 'refresh-error' })
    }
  }
  async function importDataset() {
    const latest = current()
    if ((latest.phase !== 'validated' && latest.phase !== 'import-error') || !hasImportAuthorization(latest.result)) return
    update({ phase: 'importing', error: undefined })
    try {
      await api.uploadDataset(latest.files, latest.result!.validationId!)
    } catch (error) {
      update({ phase: 'import-error', error: error instanceof ApiError ? error.message : undefined })
      return
    }
    await refresh()
  }
  async function retryRefresh() { if (current().phase === 'refresh-error') await refresh() }

  return { state, selectFiles, removeFile, reset, validate, importDataset, retryRefresh }
}
