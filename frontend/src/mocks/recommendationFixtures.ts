import type { Recommendation } from '../types/domain'
import { careerOverviews } from './fixtures'

// Fixed, isolated QA responses. No recommendations or impact values are generated.
const existing = careerOverviews['demo-aigerim'].recommendations
export const singleRecommendation: Recommendation[] = [existing[0]]
export const unorderedScoreRecommendations: Recommendation[] = [existing[2], existing[0], existing[1]]
export const missingExplanationRecommendations: Recommendation[] = [{ ...existing[0], explanation: null }]
export const partialRecommendations: Recommendation[] = [
  { eventId: 'demo-minimal', title: 'Development activity with details pending' },
  {
    eventId: 'demo-partial', title: 'Activity with a partial assessment', durationMinutes: 0,
    skillImpact: [{ skillId: 'partial-skill', name: 'System Design', current: 0, required: 4, critical: true, gain: 1.5 }],
    readinessBefore: 0,
    explanation: { factors: [
      { id: 'provided-zero', label: 'History compatibility', value: 0 },
      { id: 'missing-value', label: 'Career relevance' },
    ] },
  },
]
export const longExplanationRecommendations: Recommendation[] = [{
  ...existing[0],
  explanation: {
    factors: existing[0].explanation?.factors,
    text: 'This workshop addresses the System Design gap for the Senior Backend Engineer target. The supplied assessment identifies System Design as critical, and the activity includes practical work on the design of high-load systems.\n\nThe current, expected, and required skill levels are separate parts of the assessment. The expected level describes the projected outcome of this particular activity. It is not a record of completed development, and the target requirement remains visible so that the employee can understand the broader career context.\n\nThe readiness comparison describes the projection supplied for this activity. It does not imply that every skill requirement will be met after attending the workshop. Other development opportunities can address different capabilities, and their effects should be considered using the evidence provided for each individual activity.\n\nThe factor breakdown provides additional context for this recommendation. Each label and value belongs to the supplied assessment, while the written explanation brings those details together for the employee. The activity can be discussed with a manager alongside the employee’s interests, availability, and current development plans.',
  },
}]
