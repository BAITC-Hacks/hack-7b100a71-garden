import type { MockOptions } from './mockApi'
import { skillScaleExamples } from './fixtures'

// Development QA only. Keep failure simulation out of UI components.
export function scenarioOptions(name: string | null): MockOptions {
  switch (name) {
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
    default: return {}
  }
}
