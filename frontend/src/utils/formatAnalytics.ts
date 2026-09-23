const numberFormat = new Intl.NumberFormat('en', { maximumSignificantDigits: 21 })
const rateFormat = new Intl.NumberFormat('en', { style: 'percent', maximumSignificantDigits: 21 })

export function isAggregateValue(value: number | null | undefined): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0
}

export function isParticipationRate(value: number | null | undefined): value is number {
  return isAggregateValue(value) && value <= 1
}

export function formatAggregate(value: number) { return numberFormat.format(value) }
export function formatParticipation(value: number) { return rateFormat.format(value) }
