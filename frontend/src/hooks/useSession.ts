import { useSyncExternalStore } from 'react'
import { getSession, subscribeSession } from '../services/session'

export function useSession() {
  return useSyncExternalStore(subscribeSession, getSession, getSession)
}
