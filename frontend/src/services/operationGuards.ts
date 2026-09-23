import type { QueryClient } from '@tanstack/react-query'
import type { CompletionState } from '../types/completion'
import type { DatasetUploadState } from '../types/dataset'
import { queryKeys } from './queryClient'

// Coordinate the existing operation metadata across routes. No separate lock or
// business state is introduced. Call immediately before a mutation as well as
// observing it in the UI: synchronous cache writes protect same-tick actions.
export function isDatasetImportBlocked(client: QueryClient) {
  return client.getQueryCache().findAll({ queryKey: ['activity-completion'] }).some((query) => {
    const phase = (query.state.data as CompletionState | undefined)?.phase
    return phase === 'submitting' || phase === 'refreshing' || phase === 'refresh-error'
  })
}
export function isActivityCompletionBlocked(client: QueryClient) {
  const phase = client.getQueryData<DatasetUploadState>(queryKeys.datasetUpload)?.phase
  return phase === 'importing' || phase === 'refreshing' || phase === 'refresh-error' || phase === 'import-uncertain' || phase === 'checking-import'
}
