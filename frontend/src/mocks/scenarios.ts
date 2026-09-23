import type { MockOptions } from './mockApi'
import { skillScaleExamples } from './fixtures'
import { emptyHRAnalytics, partialHRAnalytics, zeroHRAnalytics } from './hrFixtures'
import { datasetValidationEmpty, datasetValidationFailure, datasetValidationIncomplete, datasetValidationLong, datasetValidationPartial } from './datasetFixtures'
import { longExplanationRecommendations, missingExplanationRecommendations, partialRecommendations, singleRecommendation, unorderedScoreRecommendations } from './recommendationFixtures'

// Development QA only. Keep failure simulation out of UI components.
export function scenarioOptions(name: string | null): MockOptions {
  switch (name) {
    case 'dataset-invalid': return { datasetResponse: datasetValidationFailure }
    case 'dataset-long-errors': return { datasetResponse: datasetValidationLong }
    case 'dataset-partial': return { datasetResponse: datasetValidationPartial }
    case 'dataset-incomplete': return { datasetResponse: datasetValidationIncomplete }
    case 'dataset-empty': return { datasetResponse: datasetValidationEmpty }
    case 'dataset-validation-error': return { failFirstValidation: true }
    case 'dataset-import-error': return { failFirstImport: true }
    case 'dataset-refresh-error': return { failDatasetRefresh: true }
    case 'dataset-slow': return { datasetLatencyMs: 3000 }
    case 'hr-empty': return { hrResponse: emptyHRAnalytics }
    case 'hr-partial': return { hrResponse: partialHRAnalytics }
    case 'hr-zero': return { hrResponse: zeroHRAnalytics }
    case 'hr-error': return { failHR: true }
    case 'hr-retry': return { failFirstHR: true }
    case 'hr-slow': return { hrLatencyMs: 3000 }
    case 'empty': return { emptyEmployees: true }
    case 'error': return { failReads: true }
    case 'retry': return { failFirstRead: true }
    case 'career-error': return { failFirstOverview: true }
    case 'slow': return { latencyMs: 3000 }
    case 'slow-career': return { overviewLatencyMs: 3000 }
    case 'missing-trajectory': return { overviewPatch: { trajectory: null } }
    case 'empty-trajectory': return { overviewPatch: { trajectory: { kind: 'promotion', positions: [] } } }
    case 'missing-readiness': return { overviewPatch: { readiness: null } }
    case 'precision': return { overviewPatch: { readiness: { current: 0.675 } } }
    case 'no-gaps': return { overviewPatch: { skillGaps: [] } }
    case 'skill-scales': return { overviewPatch: { skillGaps: skillScaleExamples } }
    case 'recommendations-one': return { overviewPatch: { recommendations: singleRecommendation } }
    case 'recommendations-empty': return { overviewPatch: { recommendations: [] } }
    case 'recommendations-order': return { overviewPatch: { recommendations: unorderedScoreRecommendations } }
    case 'recommendations-partial': return { overviewPatch: { recommendations: partialRecommendations } }
    case 'recommendations-no-explanation': return { overviewPatch: { recommendations: missingExplanationRecommendations } }
    case 'recommendations-long': return { overviewPatch: { recommendations: longExplanationRecommendations } }
    case 'completion-error': return { failFirstCompletion: true }
    case 'completion-refresh-error': return { refreshFault: 'failure' }
    case 'completion-refresh-timeout': return { refreshFault: 'timeout' }
    case 'completion-incomplete': return { refreshFault: 'incomplete' }
    case 'completion-missing-employee': return { completionConflict: 'missing-employee' }
    case 'completion-unavailable': return { completionConflict: 'unavailable' }
    case 'completion-duplicate': return { completionConflict: 'duplicate' }
    case 'completion-partial': return { partialCompletionData: true }
    case 'completion-slow': return { completionLatencyMs: 2500, overviewLatencyMs: 1200 }
    default: return {}
  }
}
