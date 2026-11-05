export function formatMetric(value: number | null | undefined, digits = 2) {
  if (value == null || Number.isNaN(value)) return "—"
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: digits }).format(value)
}

export function formatPercent(value: number | null | undefined) {
  if (value == null || Number.isNaN(value)) return "—"
  return new Intl.NumberFormat(undefined, { style: "percent", maximumFractionDigits: 1 }).format(value)
}
