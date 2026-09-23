import { queryClient } from './queryClient'

// Identity is navigation context supplied with the opaque token. The backend
// independently authorizes every request; choosing HR here grants no access.
export type Session = Readonly<
  { role: 'hr'; token: string } |
  { role: 'employee'; employeeId: string; token: string }
>

let currentSession: Session | null = null
const listeners = new Set<() => void>()

export function getSession(): Session | null { return currentSession }

export function subscribeSession(listener: () => void) {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}

export function setSession(session: Session | null) {
  if (session) {
    if (!session.token || /\s/.test(session.token)) throw new Error('Enter a token without spaces.')
    if (session.role === 'employee' && !session.employeeId.trim()) throw new Error('Enter your employee ID.')
  }
  currentSession = session ? Object.freeze({ ...session }) : null
  // An identity must never inherit another identity's cached profile or HR data.
  void queryClient.cancelQueries()
  queryClient.clear()
  listeners.forEach((listener) => listener())
}

export function sessionHome(session: Session): string {
  return session.role === 'hr' ? '/' : `/employees/${encodeURIComponent(session.employeeId)}`
}

export function canAccessEmployee(session: Session | null, employeeId: string): boolean {
  return session?.role === 'hr' || (session?.role === 'employee' && session.employeeId === employeeId)
}
