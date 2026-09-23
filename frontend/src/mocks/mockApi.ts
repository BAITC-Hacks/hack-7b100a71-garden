import { ApiError, type CareerApi, type RequestOptions } from '../types/api'
import type { ActivityHistory, CareerOverview, DatasetValidationResult, HRAnalytics } from '../types/domain'
import { activities, careerOverviews, employeeHistories, employees } from './fixtures'
import { completionSnapshots, unavailableActivityResponses } from './completionFixtures'
import { hrAnalytics } from './hrFixtures'
import { datasetValidationSuccess } from './datasetFixtures'
import { isDatasetSelectionReady } from '../services/datasetConfig'
import type { DatasetFileRole, DatasetMode } from '../types/dataset'

export type MockOptions = {
  latencyMs?: number
  failReads?: boolean
  emptyEmployees?: boolean
  failFirstRead?: boolean
  failFirstOverview?: boolean
  overviewLatencyMs?: number
  overviewPatch?: Partial<Pick<CareerOverview, 'trajectory' | 'readiness' | 'skillGaps' | 'recommendations'>>
  completionLatencyMs?: number
  failFirstCompletion?: boolean
  completionConflict?: 'missing-employee' | 'unavailable' | 'duplicate'
  refreshFault?: 'failure' | 'timeout' | 'incomplete'
  partialCompletionData?: boolean
  hrResponse?: HRAnalytics
  hrLatencyMs?: number
  failHR?: boolean
  failFirstHR?: boolean
  datasetResponse?: DatasetValidationResult
  datasetLatencyMs?: number
  failFirstValidation?: boolean
  failFirstImport?: boolean
  failDatasetRefresh?: boolean
}

export function createMockApi({ latencyMs = 240, failReads = false, emptyEmployees = false, failFirstRead = false, failFirstOverview = false, overviewLatencyMs = latencyMs, overviewPatch = {}, completionLatencyMs = 900, failFirstCompletion = false, completionConflict, refreshFault, partialCompletionData = false, hrResponse = hrAnalytics, hrLatencyMs = latencyMs, failHR = false, failFirstHR = false, datasetResponse = datasetValidationSuccess, datasetLatencyMs = 800, failFirstValidation = false, failFirstImport = false, failDatasetRefresh = false }: MockOptions = {}): CareerApi {
  let pendingReadFailure = failFirstRead
  let pendingOverviewFailure = failFirstOverview
  let pendingCompletionFailure = failFirstCompletion
  let pendingRefreshFault = refreshFault
  let pendingHRFailure = failFirstHR
  let pendingValidationFailure = failFirstValidation
  let pendingImportFailure = failFirstImport
  let pendingDatasetRefreshFailure = false
  let validationSequence = 0
  let validatedBatch: { id: string; files: File[]; fileRoles: DatasetFileRole[]; mode: DatasetMode } | undefined
  let demoState: keyof typeof completionSnapshots = 'initial'
  let unavailableEvent: string | undefined
  const history: ActivityHistory[] = []
  const demoEmployeeId = completionSnapshots.initial.employee.id
  async function read<T>(resolve: () => T, options?: RequestOptions, delay = latencyMs): Promise<T> {
    const signal = options?.signal
    signal?.throwIfAborted()
    await new Promise<void>((done, reject) => {
      const onAbort = () => {
        clearTimeout(timer)
        signal?.removeEventListener('abort', onAbort)
        reject(signal?.reason ?? new DOMException('Request aborted', 'AbortError'))
      }
      const timer = setTimeout(() => {
        signal?.removeEventListener('abort', onAbort)
        done()
      }, delay)
      signal?.addEventListener('abort', onAbort, { once: true })
    })
    signal?.throwIfAborted()
    if (failReads || pendingReadFailure) {
      pendingReadFailure = false
      throw new ApiError('NETWORK', 'The demo request could not be completed.')
    }
    return structuredClone(resolve())
  }

  function requireEmployee(id: string) {
    const employee = emptyEmployees ? undefined : employees.find((item) => item.id === id)
    if (!employee) throw new ApiError('NOT_FOUND', 'This employee could not be found.')
    return id === demoEmployeeId ? completionSnapshots[demoState].employee : employee
  }

  return {
    getEmployees: (options) => read(() => emptyEmployees ? [] : employees.map((employee) => requireEmployee(employee.id)), options),
    getEmployee: (id, options) => read(() => requireEmployee(id), options),
    getEmployeeHistory: (id, options) => read(() => { requireEmployee(id); return id === demoEmployeeId ? history : employeeHistories[id] }, options),
    getEvents: (options) => read(() => activities, options),
    getRecommendations: (id, options) => {
      const fault = id === demoEmployeeId && demoState !== 'initial' ? pendingRefreshFault : undefined
      if (fault) pendingRefreshFault = undefined
      return read(() => {
        requireEmployee(id)
        if (fault === 'failure') throw new ApiError('NETWORK', 'The updated assessment could not be loaded.')
        if (fault === 'incomplete') throw new ApiError('INVALID_RESPONSE', 'The updated assessment is incomplete.')
        if (pendingOverviewFailure) {
          pendingOverviewFailure = false
          throw new ApiError('NETWORK', 'The career assessment could not be loaded.')
        }
        if (id === demoEmployeeId && demoState !== 'initial') {
          const result = completionSnapshots[demoState].overview
          return partialCompletionData ? { ...result, recommendations: result.recommendations.map(({ eventId, title }) => ({ eventId, title })) } : result
        }
        if (id === demoEmployeeId && unavailableEvent && unavailableActivityResponses[unavailableEvent]) return unavailableActivityResponses[unavailableEvent]
        return { ...careerOverviews[id], ...overviewPatch }
      }, options, fault === 'timeout' ? 30_000 : overviewLatencyMs)
    },
    getHRAnalytics: (options) => read(() => {
      if (pendingDatasetRefreshFailure) {
        pendingDatasetRefreshFailure = false
        throw new ApiError('NETWORK', 'Analytics could not be refreshed after import.')
      }
      if (failHR || pendingHRFailure) {
        pendingHRFailure = false
        throw new ApiError('NETWORK', 'Organizational analytics could not be loaded.')
      }
      return hrResponse
    }, options, hrLatencyMs),
    completeActivity: (id, eventId) => read(() => {
      requireEmployee(id)
      if (completionConflict === 'missing-employee') throw new ApiError('NOT_FOUND', 'This employee could not be found.')
      if (pendingCompletionFailure) {
        pendingCompletionFailure = false
        throw new ApiError('NETWORK', 'The activity could not be completed.')
      }
      if (history.some((item) => id === demoEmployeeId && item.eventId === eventId)) throw new ApiError('ALREADY_COMPLETED', 'The activity is already completed.')
      const next = id === demoEmployeeId ? completionSnapshots[demoState].next[eventId] : undefined
      if (!next || completionConflict === 'unavailable') {
        unavailableEvent = eventId
        throw new ApiError('RECOMMENDATION_UNAVAILABLE', 'This recommendation is no longer available.')
      }
      demoState = next
      history.push({ id: `${id}-${eventId}`, eventId, status: 'completed', updatedAt: new Date().toISOString() })
      if (completionConflict === 'duplicate') throw new ApiError('ALREADY_COMPLETED', 'The activity is already completed.')
    }, undefined, completionLatencyMs),
    validateDataset: (files, options = {}) => read(() => {
      validatedBatch = undefined
      const mode = options.mode ?? 'append'
      const fileRoles = options.fileRoles ?? []
      if (!isDatasetSelectionReady(files, fileRoles, mode)) throw new ApiError('VALIDATION', 'Choose the required file roles before validating the dataset.')
      if (pendingValidationFailure) {
        pendingValidationFailure = false
        throw new ApiError('NETWORK', 'Validation is temporarily unavailable. Please try again.')
      }
      const result = structuredClone(datasetResponse)
      if (result.valid === true && result.validationId && !result.errors?.length) {
        result.validationId = `${result.validationId}-${++validationSequence}`
        validatedBatch = { id: result.validationId, files: [...files], fileRoles: [...fileRoles], mode }
      }
      return result
    }, options, datasetLatencyMs),
    uploadDataset: (files, validationId, options = {}) => read(() => {
      // Local receipt bookkeeping only. No contents are parsed, saved, or imported.
      const batch = validatedBatch
      if (!batch || batch.id !== validationId || batch.mode !== (options.mode ?? 'append') || files.length !== batch.files.length || files.some((file, index) => file !== batch.files[index] || options.fileRoles?.[index] !== batch.fileRoles[index])) {
        throw new ApiError('VALIDATION', 'Validate the selected files again before importing.')
      }
      validatedBatch = undefined
      if (pendingImportFailure) {
        pendingImportFailure = false
        throw new ApiError('NETWORK', 'The import response could not be received.')
      }
      pendingDatasetRefreshFailure = failDatasetRefresh
    }, options, datasetLatencyMs),
  }
}
