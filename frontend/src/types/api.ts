import type {
  Activity, ActivityHistory, CareerOverview, DatasetValidationResult, Employee, HRAnalytics,
} from './domain'

export type RequestOptions = { signal?: AbortSignal }
export interface CareerApi {
  getEmployees(options?: RequestOptions): Promise<Employee[]>
  getEmployee(id: string, options?: RequestOptions): Promise<Employee>
  getEmployeeHistory(id: string, options?: RequestOptions): Promise<ActivityHistory[]>
  getEvents(options?: RequestOptions): Promise<Activity[]>
  getRecommendations(id: string, options?: RequestOptions): Promise<CareerOverview>
  getHRAnalytics(options?: RequestOptions): Promise<HRAnalytics>
  completeActivity(employeeId: string, eventId: string): Promise<void>
  validateDataset(files: File[]): Promise<DatasetValidationResult>
  uploadDataset(files: File[], validationId: string): Promise<void>
}

export type ApiErrorCode = 'NOT_FOUND' | 'UNAVAILABLE' | 'CONFIGURATION' | 'NETWORK' | 'TIMEOUT' | 'INVALID_RESPONSE' | 'RECOMMENDATION_UNAVAILABLE' | 'ALREADY_COMPLETED'
export class ApiError extends Error {
  readonly code: ApiErrorCode
  constructor(code: ApiErrorCode, message: string) {
    super(message)
    this.name = 'ApiError'
    this.code = code
  }
}
