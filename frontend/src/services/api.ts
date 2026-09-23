import { createMockApi } from '../mocks/mockApi'
import { ApiError, type CareerApi } from '../types/api'

export function createApi(mode: string = 'mock'): CareerApi {
  if (mode === 'mock') return createMockApi()

  // Fail explicitly until the real contract is available; never silently fall back to fixtures.
  const unavailable = () => Promise.reject(new ApiError('CONFIGURATION', 'The live API is not connected. Please use mock mode for this preview.'))
  return {
    getEmployees: unavailable, getEmployee: unavailable, getEmployeeHistory: unavailable,
    getEvents: unavailable, getRecommendations: unavailable, getHRAnalytics: unavailable,
    completeActivity: unavailable, validateDataset: unavailable, uploadDataset: unavailable,
  }
}

export const apiMode = import.meta.env.VITE_API_MODE || 'mock'
export const api = createApi(apiMode)
