export type User = {
  id: string
  email: string
  full_name: string
}

export type Workspace = {
  id: string
  name: string
  slug: string
  role: "owner" | "admin" | "analyst" | "viewer"
}

export type TokenResponse = {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: User
}

export type DatePreset = "30d" | "90d" | "12m" | "all"

export type DatasetSummary = {
  id: string
  workspace_id: string
  name: string
  status: string
  source_type: "upload" | "sample" | "uci"
  original_filename: string
  row_count: number
  column_count: number
  quality_score: number | null
  mapping: Record<string, string | null>
  missing_roles: string[]
  customer_ready: boolean
  has_processed: boolean
  processed_rows: number | null
  min_date: string | null
  max_date: string | null
  error_message: string | null
  created_at: string | null
  role_labels: Record<string, string>
}

export type DatasetColumnProfile = {
  name: string
  inferred_type: string
  semantic_role: string | null
  null_count: number
  distinct_count: number
}

export type DatasetDetail = DatasetSummary & {
  profile: {
    score: number
    formula: string
    completeness: number
    uniqueness: number
    validity: number
    consistency: number
    duplicate_rows: number
    missing_values: number
    columns: DatasetColumnProfile[]
    outliers: Record<string, { count?: number; note?: string; low?: number; high?: number }>
    notes: string[]
  } | null
  cleaning: {
    rules?: string[]
    invalid_rows?: number
    sales?: number
    returns?: number
    cancellations?: number
    exact_duplicates_removed?: number
  } | null
}

export type NotificationItem = {
  id: string
  action: string
  message: string
  created_at: string
}

export type KpiValue = {
  value: number | null
  previous: number | null
  growth: number | null
  reason?: string
}

export type SalesAnalytics = {
  period: { date_from: string | null; date_to: string | null }
  definitions: Record<string, string>
  kpis: Record<string, KpiValue>
  monthly: { period: string; revenue: number; orders: number; customers: number }[]
  quarterly: { period: string; revenue: number; orders: number; customers: number }[]
  weekday: { weekday: string; revenue: number }[]
  distribution: { from: number; to: number; count: number }[]
  countries: { key: string; revenue: number; share: number | null }[]
  products: { key: string; revenue: number; share: number | null }[]
  categories: { key: string; revenue: number; share: number | null }[]
  limitations: string[]
}
