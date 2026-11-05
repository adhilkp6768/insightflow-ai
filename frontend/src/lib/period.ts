import type { DatePreset } from "@/types/api"

export function periodParams(preset: DatePreset, minDate: string | null, maxDate: string | null) {
  if (!minDate || !maxDate) return {}
  if (preset === "all") return { date_from: minDate, date_to: maxDate }
  const end = new Date(`${maxDate}T00:00:00Z`)
  const days = preset === "30d" ? 30 : preset === "90d" ? 90 : 365
  const start = new Date(end)
  start.setUTCDate(start.getUTCDate() - days)
  const from = start.toISOString().slice(0, 10)
  return { date_from: from < minDate ? minDate : from, date_to: maxDate }
}

export function withQuery(path: string, params: Record<string, string | undefined>) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value) search.set(key, value)
  }
  const text = search.toString()
  return text ? `${path}?${text}` : path
}
