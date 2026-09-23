import type { HRAnalytics } from '../types/domain'

// Fixed synthetic organizational responses, independent of the three sample profiles.
// No aggregates are derived from employee records, history, or completion snapshots.
export const hrAnalytics: HRAnalytics = {
  totalEmployees: 24,
  employeesInDevelopment: 18,
  withoutNextStep: 6,
  participationRate: 0.75,
  commonSkillGaps: [
    { skillId: 'system-design', name: 'System Design', employeeCount: 9 },
    { skillId: 'mentoring', name: 'Mentoring', employeeCount: 7 },
    { skillId: 'leadership', name: 'Leadership', employeeCount: 6 },
    { skillId: 'api-design', name: 'API Design', employeeCount: 5 },
    { skillId: 'technical-communication', name: 'Technical Communication', employeeCount: 3 },
  ],
  activityParticipation: [
    { activityId: 'demo-system-design', title: 'System Design Workshop', participantCount: 12 },
    { activityId: 'demo-api-design', title: 'API Design in Practice', participantCount: 9 },
    { activityId: 'demo-communication', title: 'Technical Communication Lab', participantCount: 7 },
  ],
  activityStatuses: [
    { status: 'completed', count: 14 },
    { status: 'in_progress', count: 10 },
    { status: 'no_show', count: 2 },
    { status: 'dropped', count: 1 },
    { status: 'declined', count: 3 },
    { status: 'overdue', count: 2 },
  ],
}

export const emptyHRAnalytics: HRAnalytics = {}
export const zeroHRAnalytics: HRAnalytics = {
  totalEmployees: 0, employeesInDevelopment: 0, withoutNextStep: 0, participationRate: 0,
  commonSkillGaps: [], activityParticipation: [], activityStatuses: [{ status: 'completed', count: 0 }],
}
export const partialHRAnalytics: HRAnalytics = {
  totalEmployees: 24, withoutNextStep: 0, participationRate: null,
  commonSkillGaps: [
    { skillId: 'mentoring', name: 'Mentoring', employeeCount: 7 },
    { skillId: 'leadership', name: 'Leadership', employeeCount: null },
  ],
  activityParticipation: [], activityStatuses: null,
}
