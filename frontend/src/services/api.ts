import { createMockApi, type MockOptions } from '../mocks/mockApi'
import { scenarioOptions } from '../mocks/scenarios'
import { ApiError, type CareerApi } from '../types/api'
import { createHttpApi } from './httpApi'
import type { HttpClientOptions } from './httpClient'

export function createApi(mode: string = 'mock', mockOptions: MockOptions = {}, httpOptions?: HttpClientOptions): CareerApi {
  if (mode === 'mock') return createMockApi(mockOptions)
  if (mode === 'real') return createHttpApi(httpOptions ?? { baseURL: import.meta.env.VITE_API_BASE_URL ?? '' })

  // Unknown modes fail explicitly and never silently fall back to demo records.
  const unavailable = () => Promise.reject(new ApiError('CONFIGURATION', 'Choose VITE_API_MODE=mock or real.'))
  return {
    getEmployees: unavailable, getEmployee: unavailable, getEmployeeHistory: unavailable,
    getEvents: unavailable, getRecommendations: unavailable, getHRAnalytics: unavailable,
    completeActivity: unavailable, validateDataset: unavailable, uploadDataset: unavailable,
  }
}

export const apiMode = import.meta.env.VITE_API_MODE || 'mock'
const scenario = import.meta.env.DEV && typeof window !== 'undefined'
  ? new URLSearchParams(window.location.search).get('mockScenario') : null
export const api = createApi(apiMode, scenarioOptions(scenario))
