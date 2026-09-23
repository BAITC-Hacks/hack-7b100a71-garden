import { useCallback, useSyncExternalStore } from 'react'
import { notifyManager, useQueryClient, type QueryClient } from '@tanstack/react-query'

export function useOperationGuard(isBlocked: (client: QueryClient) => boolean) {
  const client = useQueryClient()
  // Query entries may be created while another hook renders. Match Query's own
  // scheduled notifications instead of triggering React updates during render.
  const subscribe = useCallback((listener: () => void) => client.getQueryCache().subscribe(notifyManager.batchCalls(listener)), [client])
  const snapshot = useCallback(() => isBlocked(client), [client, isBlocked])
  return useSyncExternalStore(subscribe, snapshot, snapshot)
}
