import { skipToken, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../services/api'
import { isDatasetSelectionReady, suggestDatasetRole } from '../services/datasetConfig'
import { queryKeys } from '../services/queryClient'
import { refreshDatasetState } from '../services/refreshDatasetState'
import { ApiError } from '../types/api'
import { emptyDatasetUpload, hasImportAuthorization, isDatasetBusy, isDatasetImported, isDatasetUncertain, type DatasetUploadState, type DatasetMode, type DatasetFileRole } from '../types/dataset'
import { datasetCopy } from '../i18n/dataset'
import { isDatasetImportBlocked } from '../services/operationGuards'
import { useOperationGuard } from './useOperationGuard'
import { mutationCopy } from '../i18n/mutations'

export function useDatasetUpload() {
  const client = useQueryClient()
  const importBlocked = useOperationGuard(isDatasetImportBlocked)
  const key = queryKeys.datasetUpload
  // In-memory selection and acknowledgement survive route changes. Never persisted.
  const { data: state = emptyDatasetUpload } = useQuery<DatasetUploadState>({ queryKey: key, queryFn: skipToken,
    initialData: emptyDatasetUpload, staleTime: Infinity, gcTime: Infinity })
  const current = () => client.getQueryData<DatasetUploadState>(key) ?? emptyDatasetUpload
  const update = (patch: Partial<DatasetUploadState>) => client.setQueryData<DatasetUploadState>(key, { ...current(), ...patch })

  function selectFiles(files: File[]) {
    if (isDatasetBusy(current()) || isDatasetImported(current()) || isDatasetUncertain(current())) return
    client.setQueryData(key, { files, mode: current().mode, fileRoles: files.map(suggestDatasetRole), phase: 'idle' } satisfies DatasetUploadState)
  }
  function removeFile(index: number) {
    if (isDatasetBusy(current()) || isDatasetImported(current()) || isDatasetUncertain(current())) return
    const latest = current()
    client.setQueryData(key, { files: latest.files.filter((_, position) => position !== index), mode: latest.mode,
      fileRoles: latest.fileRoles.filter((_, position) => position !== index), phase: 'idle' } satisfies DatasetUploadState)
  }
  function changeSelection(patch: Partial<Pick<DatasetUploadState, 'mode' | 'fileRoles'>>) {
    if (isDatasetBusy(current()) || isDatasetImported(current()) || isDatasetUncertain(current())) return
    update({ ...patch, phase: 'idle', result: undefined, error: undefined })
  }
  function selectMode(mode: DatasetMode) { changeSelection({ mode }) }
  function selectRole(index: number, role: DatasetFileRole | '') {
    changeSelection({ fileRoles: current().fileRoles.map((value, position) => index === position ? role : value) })
  }
  function reset() {
    if (isDatasetBusy(current()) || isDatasetUncertain(current())) return
    client.setQueryData(key, emptyDatasetUpload)
  }

  async function validate() {
    const latest = current()
    if (isDatasetBusy(latest) || isDatasetImported(latest) || isDatasetUncertain(latest) || !isDatasetSelectionReady(latest.files, latest.fileRoles, latest.mode)) return
    // Cache updates are synchronous: repeated clicks cannot dispatch twice.
    update({ phase: 'validating', result: undefined, error: undefined })
    try {
      const result = await api.validateDataset(latest.files, { mode: latest.mode, fileRoles: latest.fileRoles as DatasetFileRole[] })
      update({ result: result ?? {}, phase: hasImportAuthorization(result) ? 'validated' : result?.valid === false ? 'invalid' : 'incomplete' })
    } catch (error) {
      update({ phase: 'validation-error', error: error instanceof ApiError ? error.message : undefined })
    }
  }

  async function refresh() {
    update({ phase: 'refreshing', error: undefined })
    try {
      await refreshDatasetState(api, client, true)
      update({ phase: 'success' })
    } catch {
      update({ phase: 'refresh-error' })
    }
  }
  async function importDataset() {
    if (isDatasetImportBlocked(client)) return
    const latest = current()
    if (latest.phase !== 'validated' || !hasImportAuthorization(latest.result)) return
    update({ phase: 'importing', error: undefined })
    try {
      await api.uploadDataset(latest.files, latest.result!.validationId!, { mode: latest.mode, fileRoles: latest.fileRoles as DatasetFileRole[] })
    } catch (error) {
      // Upload has no idempotency contract. A network/timeout/server failure may
      // follow a committed import: lock mutation retry until an operator checks it.
      const rejected = error instanceof ApiError && ['VALIDATION', 'AUTHENTICATION', 'FORBIDDEN', 'CONFLICT', 'CONFIGURATION'].includes(error.code)
      update({ phase: rejected ? 'import-error' : 'import-uncertain', error: rejected && error instanceof ApiError ? error.message : undefined })
      return
    }
    await refresh()
  }
  async function retryRefresh() { if (!isDatasetImportBlocked(client) && current().phase === 'refresh-error') await refresh() }
  async function checkImport() {
    if (current().phase !== 'import-uncertain') return
    update({ phase: 'checking-import', error: undefined })
    try {
      await refreshDatasetState(api, client)
      update({ phase: 'import-uncertain', error: datasetCopy.checked })
    } catch {
      update({ phase: 'import-uncertain', error: datasetCopy.checkFailed })
    }
  }

  return { state, selectFiles, selectMode, selectRole, removeFile, reset, validate, importDataset, retryRefresh, checkImport,
    importBlockedReason: importBlocked ? mutationCopy.datasetBlocked : undefined }
}
