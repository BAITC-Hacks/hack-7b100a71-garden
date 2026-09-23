import { createMockApi, type MockOptions } from '../mocks/mockApi'
import { scenarioOptions } from '../mocks/scenarios'
import { ApiError, type CareerApi } from '../types/api'
import { createHttpApi } from './httpApi'

export function createApi(mode: string = 'real', mockOptions: MockOptions = {}): CareerApi {
  if (mode === 'mock') return createMockApi(mockOptions)
  if (mode === 'real') return createHttpApi({ baseUrl: import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000' })

  const unavailable = () => Promise.reject(new ApiError('CONFIGURATION', 'VITE_API_MODE must be real or mock.'))
  return {
    getEmployees: unavailable, getEmployee: unavailable, getEmployeeHistory: unavailable,
    getEvents: unavailable, getRecommendations: unavailable, getHRAnalytics: unavailable,
    completeActivity: unavailable, validateDataset: unavailable, uploadDataset: unavailable,
  }
}

export const apiMode = import.meta.env.VITE_API_MODE || 'real'
const scenario = import.meta.env.DEV && typeof window !== 'undefined'
  ? new URLSearchParams(window.location.search).get('mockScenario') : null
export const api = createApi(apiMode, scenarioOptions(scenario))
