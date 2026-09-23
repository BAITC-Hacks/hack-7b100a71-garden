const percentage = new Intl.NumberFormat('en', {
  style: 'percent', maximumSignificantDigits: 21, useGrouping: false,
})
const scientificPercentage = new Intl.NumberFormat('en', {
  style: 'percent', notation: 'scientific', maximumSignificantDigits: 21,
})

// Presentation validity only; do not repair or infer assessments.
export function isReadinessValue(value: number | null | undefined): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= 1
}

// Presentation only: retain the supplied number's precision, including fractional
// percentages. Scientific notation keeps extremely small values readable, not zero.
export function formatReadiness(value: number): string {
  const formatted = percentage.format(value)
  return formatted.length > 24 ? scientificPercentage.format(value) : formatted
}
