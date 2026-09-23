import { ApiError, type ApiErrorCode } from '../types/api'
import { getApiToken } from './apiSession'

export interface ResponseMeta { version?: number; total?: number; offset?: number; limit?: number; as_of_date?: string }
export interface ApiEnvelope<T> { data: T; meta?: ResponseMeta }
// Dataset adapters pass FormData unchanged; request() returns the unwrapped data.
// Reads needing snapshot/pagination metadata use requestEnvelope(). No retries or
// mutation replay occurs in this client.
export interface HttpClient {
  request<T>(path: string, init?: RequestInit): Promise<T>
  requestEnvelope<T>(path: string, init?: RequestInit): Promise<ApiEnvelope<T>>
}
export interface HttpClientOptions { baseURL: string; fetcher?: typeof fetch; getToken?: () => string; timeoutMs?: number }

function errorCode(status: number, code?: string): ApiErrorCode {
  if (code === 'already_completed' || code === 'session_already_completed') return 'ALREADY_COMPLETED'
  if (['event_not_eligible', 'event_audience_mismatch', 'prerequisites_not_met', 'event_not_found'].includes(code ?? '')) return 'RECOMMENDATION_UNAVAILABLE'
  if (status === 401) return 'AUTHENTICATION'
  if (status === 403) return 'FORBIDDEN'
  if (status === 404) return 'NOT_FOUND'
  if (status === 409) return 'CONFLICT'
  if (status === 400 || status === 413 || status === 422) return 'VALIDATION'
  if (status === 504) return 'TIMEOUT'
  return 'UNAVAILABLE'
}

export function createHttpClient({ baseURL, fetcher = fetch, getToken = getApiToken, timeoutMs = 15_000 }: HttpClientOptions): HttpClient {
  async function requestEnvelope<T>(path: string, init: RequestInit = {}): Promise<ApiEnvelope<T>> {
    let base: URL
    try { base = new URL(baseURL) } catch { throw new ApiError('CONFIGURATION', 'Set a valid VITE_API_BASE_URL to connect the live API.') }
    if (!['http:', 'https:'].includes(base.protocol) || base.username || base.password || base.search || base.hash) {
      throw new ApiError('CONFIGURATION', 'The API base URL must be an HTTP(S) address without credentials, query, or fragment.')
    }
    if (!path.startsWith('/') || path.startsWith('//')) throw new ApiError('CONFIGURATION', 'The API path must be relative to the configured service.')
    const headers = new Headers(init.headers)
    headers.set('Accept', 'application/json')
    const token = getToken()
    if (token) headers.set('Authorization', `Bearer ${token}`)
    const controller = new AbortController()
    const abort = () => controller.abort(init.signal?.reason)
    if (init.signal?.aborted) abort()
    else init.signal?.addEventListener('abort', abort, { once: true })
    let timedOut = false
    const timer = setTimeout(() => { timedOut = true; controller.abort() }, timeoutMs)
    try {
      const response = await fetcher(`${baseURL.replace(/\/$/, '')}${path}`, { ...init, headers, signal: controller.signal, credentials: 'omit', redirect: 'error' })
      let payload: unknown
      try { payload = await response.json() } catch {
        throw new ApiError(response.ok ? 'INVALID_RESPONSE' : errorCode(response.status), 'The API returned an unreadable response.', { status: response.status })
      }
      if (!response.ok) {
        const error = payload && typeof payload === 'object' && 'error' in payload ? payload.error as Record<string, unknown> : undefined
        const backendCode = typeof error?.code === 'string' ? error.code : undefined
        throw new ApiError(errorCode(response.status, backendCode), typeof error?.message === 'string' ? error.message : 'The API request failed.', {
          backendCode, status: response.status, details: Array.isArray(error?.details) ? error.details : [],
        })
      }
      if (!payload || typeof payload !== 'object' || !('data' in payload)) throw new ApiError('INVALID_RESPONSE', 'The API response is missing its data envelope.')
      return payload as ApiEnvelope<T>
    } catch (error) {
      if (timedOut) throw new ApiError('TIMEOUT', 'The API request timed out. Its result may need to be checked before retrying.')
      if (init.signal?.aborted) throw new DOMException('The request was cancelled.', 'AbortError')
      if (error instanceof ApiError) throw error
      throw new ApiError('NETWORK', 'The API could not be reached. Check the connection and API configuration.')
    } finally {
      clearTimeout(timer)
      init.signal?.removeEventListener('abort', abort)
    }
  }
  return { requestEnvelope, request: async <T>(path: string, init?: RequestInit) => (await requestEnvelope<T>(path, init)).data }
}
