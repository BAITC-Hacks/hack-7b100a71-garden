import type {
  Activity, ActivityHistory, CareerOverview, CompletionReceipt, DatasetFiles, DatasetMode, DatasetUploadResult, DatasetValidationResult, Employee, HRAnalytics,
} from './domain'

export type RequestOptions = { signal?: AbortSignal }
export type CompletionOptions = RequestOptions & { idempotencyKey: string; recordId?: string; score?: number; feedbackRating?: number }
export interface CareerApi {
  getEmployees(options?: RequestOptions): Promise<Employee[]>
  getEmployee(id: string, options?: RequestOptions): Promise<Employee>
  getEmployeeHistory(id: string, options?: RequestOptions): Promise<ActivityHistory[]>
  getEvents(options?: RequestOptions): Promise<Activity[]>
  getRecommendations(id: string, options?: RequestOptions): Promise<CareerOverview>
  getHRAnalytics(options?: RequestOptions): Promise<HRAnalytics>
  completeActivity(employeeId: string, eventId: string, options: CompletionOptions): Promise<CompletionReceipt>
  validateDataset(files: DatasetFiles, mode?: DatasetMode, options?: RequestOptions): Promise<DatasetValidationResult>
  uploadDataset(files: DatasetFiles, mode?: DatasetMode, options?: RequestOptions): Promise<DatasetUploadResult>
}

export type ApiErrorCode = 'NOT_FOUND' | 'UNAVAILABLE' | 'CONFIGURATION' | 'NETWORK' | 'UNAUTHENTICATED' | 'FORBIDDEN' | 'INVALID_RESPONSE' | 'BACKEND'
export class ApiError extends Error {
  readonly code: ApiErrorCode
  readonly status?: number
  readonly backendCode?: string
  readonly details: unknown[]
  constructor(code: ApiErrorCode, message: string, context: { status?: number; backendCode?: string; details?: unknown[] } = {}) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = context.status
    this.backendCode = context.backendCode
    this.details = context.details ?? []
  }
}
