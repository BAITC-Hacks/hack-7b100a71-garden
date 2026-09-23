import type { CareerOverview, Employee, Recommendation, SkillGap } from '../types/domain'
import { careerOverviews, employees } from './fixtures'

// Scripted responses, not a scoring model. Every assessment value and recommendation
// sequence below is fixed. The transition table supports the three activities in any order.
const employee = employees[0]
const overview = careerOverviews[employee.id]
const [systemBefore, apiBefore, communicationBefore] = overview.skillGaps
const systemAfter: SkillGap = { ...systemBefore, current: 3, gap: 1 }
const apiAfter: SkillGap = { ...apiBefore, current: 4, gap: 0 }
const communicationAfter: SkillGap = { ...communicationBefore, current: 4, gap: 0 }
const [systemActivity, apiActivity, communicationActivity] = overview.recommendations
export const unavailableActivityResponses: Record<string, CareerOverview> = {
  'demo-system-design': { ...overview, recommendations: [apiActivity, communicationActivity] },
  'demo-api-design': { ...overview, recommendations: [systemActivity, communicationActivity] },
  'demo-communication': { ...overview, recommendations: [systemActivity, apiActivity] },
}

function snapshot(skills: SkillGap[], readiness: number, recommendations: Recommendation[]) {
  return {
    employee: { ...employee, skills: skills.map((skill) => {
      if (typeof skill.current !== 'number') throw new Error('Completion fixtures require supplied current skill levels.')
      return { ...skill, current: skill.current }
    }) },
    overview: { ...overview, skillGaps: skills, readiness: { current: readiness }, recommendations },
  }
}
type DemoState = 'initial' | 'system' | 'api' | 'communication' | 'system-api' | 'system-communication' | 'api-communication' | 'all'
interface CompletionSnapshot { employee: Employee; overview: CareerOverview; next: Partial<Record<string, DemoState>> }
export const completionSnapshots: Record<DemoState, CompletionSnapshot> = {
  initial: { employee, overview, next: { 'demo-system-design': 'system', 'demo-api-design': 'api', 'demo-communication': 'communication' } },
  system: { ...snapshot([systemAfter, apiBefore, communicationBefore], 0.79, [
    { ...apiActivity, readinessBefore: 0.79, readinessAfter: 0.85 },
    { ...communicationActivity, readinessBefore: 0.79, readinessAfter: 0.82 },
  ]), next: { 'demo-api-design': 'system-api', 'demo-communication': 'system-communication' } },
  api: { ...snapshot([systemBefore, apiAfter, communicationBefore], 0.73, [
    { ...systemActivity, readinessBefore: 0.73, readinessAfter: 0.85 },
    { ...communicationActivity, readinessBefore: 0.73, readinessAfter: 0.78 },
  ]), next: { 'demo-system-design': 'system-api', 'demo-communication': 'api-communication' } },
  communication: { ...snapshot([systemBefore, apiBefore, communicationAfter], 0.71, [
    { ...systemActivity, readinessBefore: 0.71, readinessAfter: 0.82 },
    { ...apiActivity, readinessBefore: 0.71, readinessAfter: 0.78 },
  ]), next: { 'demo-system-design': 'system-communication', 'demo-api-design': 'api-communication' } },
  'system-api': { ...snapshot([systemAfter, apiAfter, communicationBefore], 0.85, [
    { ...communicationActivity, readinessBefore: 0.85, readinessAfter: 0.9 },
  ]), next: { 'demo-communication': 'all' } },
  'system-communication': { ...snapshot([systemAfter, apiBefore, communicationAfter], 0.82, [
    { ...apiActivity, readinessBefore: 0.82, readinessAfter: 0.9 },
  ]), next: { 'demo-api-design': 'all' } },
  'api-communication': { ...snapshot([systemBefore, apiAfter, communicationAfter], 0.78, [
    { ...systemActivity, readinessBefore: 0.78, readinessAfter: 0.9 },
  ]), next: { 'demo-system-design': 'all' } },
  all: { ...snapshot([systemAfter, apiAfter, communicationAfter], 0.9, []), next: {} },
}
