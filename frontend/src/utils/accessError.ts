import { ApiError } from '../types/api'
import { accessCopy } from '../i18n/access'

export type AccessScope = 'directory' | 'employee' | 'career' | 'hr'
// Access comes only from the server's response; opaque tokens are never decoded
// or used to infer a role. Repeating a denied request cannot change access.
export function getAccessIssue(error: unknown, scope: AccessScope) {
  if (!(error instanceof ApiError)) return undefined
  if (error.code === 'AUTHENTICATION') return { title: accessCopy.authenticationTitle, description: accessCopy.authenticationDescription,
    selectorLabel: accessCopy.selectorAuthentication, selectorNote: accessCopy.selectorAuthenticationNote }
  if (error.code === 'FORBIDDEN') return { title: accessCopy.forbiddenTitle, description: accessCopy[scope],
    selectorLabel: accessCopy.selectorForbidden, selectorNote: accessCopy.selectorForbiddenNote }
  return undefined
}
