// A backend-issued token is held only for this page session. Never persist it,
// include it in a Vite environment variable, or infer identity from its contents.
let token = ''
export function getApiToken() { return token }
export function setApiToken(value: string) { token = value.trim() }
