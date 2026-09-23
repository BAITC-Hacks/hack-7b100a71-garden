import { createMockApi, type MockOptions } from '../mocks/mockApi'
import { scenarioOptions } from '../mocks/scenarios'
import { ApiError, type CareerApi } from '../types/api'

export function createApi(mode: string = 'mock', mockOptions: MockOptions = {}): CareerApi {
  if (mode === 'mock') return createMockApi(mockOptions)

  // Fail explicitly until the real contract is available; never silently fall back to fixtures.
  const unavailable = () => Promise.reject(new ApiError('CONFIGURATION', 'The live API is not connected. Please use mock mode for this preview.'))
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
