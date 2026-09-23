import type {
  Activity, ActivityHistory, CareerOverview, DatasetValidationResult, Employee, HRAnalytics,
} from './domain'
import type { DatasetRequestOptions } from './dataset'

export type RequestOptions = { signal?: AbortSignal }
export interface CareerApi {
  getEmployees(options?: RequestOptions): Promise<Employee[]>
  getEmployee(id: string, options?: RequestOptions): Promise<Employee>
  getEmployeeHistory(id: string, options?: RequestOptions): Promise<ActivityHistory[]>
  getEvents(options?: RequestOptions): Promise<Activity[]>
  getRecommendations(id: string, options?: RequestOptions): Promise<CareerOverview>
  getHRAnalytics(options?: RequestOptions): Promise<HRAnalytics>
  completeActivity(employeeId: string, eventId: string): Promise<void>
  validateDataset(files: File[], options?: RequestOptions & DatasetRequestOptions): Promise<DatasetValidationResult>
  uploadDataset(files: File[], validationId: string, options?: RequestOptions & DatasetRequestOptions): Promise<void>
}

export type ApiErrorCode = 'NOT_FOUND' | 'UNAVAILABLE' | 'CONFIGURATION' | 'NETWORK' | 'TIMEOUT' | 'INVALID_RESPONSE' | 'RECOMMENDATION_UNAVAILABLE' | 'ALREADY_COMPLETED' | 'AUTHENTICATION' | 'FORBIDDEN' | 'CONFLICT' | 'VALIDATION'
export class ApiError extends Error {
  readonly code: ApiErrorCode
  readonly backendCode?: string
  readonly status?: number
  readonly details?: unknown[]
  constructor(code: ApiErrorCode, message: string, context: { backendCode?: string; status?: number; details?: unknown[] } = {}) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.backendCode = context.backendCode
    this.status = context.status
    this.details = context.details
  }
}
