import { useQuery } from "@tanstack/react-query"
import { useState, type FormEvent } from "react"

import { DatasetGate } from "@/components/dashboard/DatasetGate"
import { PageHeader } from "@/components/common/PageHeader"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useWorkspace } from "@/contexts/workspace-context"
import { formatMetric, formatPercent } from "@/lib/format"
import { periodParams, withQuery } from "@/lib/period"
import { api, formatApiError } from "@/services/api"

type CustomerRow = {
  customer_id: string
  country: string | null
  frequency: number
  historical_value: number
  recency_days: number
  projected_12_month_value: number
}

type CustomerAnalytics = {
  available: boolean
  reason?: string
  customer_count?: number
  repeat_rate?: number
  retention_rate?: number | null
  retention_definition?: string
  value_definition?: string
  average_historical_value?: number
  high_value?: CustomerRow[]
  inactive?: CustomerRow[]
  customers?: CustomerRow[]
  cohorts?: { cohort: string; customers: number; retention: Array<number | null> }[]
  limitations?: string[]
}

type CustomerDetail = CustomerRow & {
  recent_invoices: {
    invoice_id: string | null
    invoice_date: string
    description: string | null
    quantity: number | null
    revenue: number | null
    transaction_type: string
  }[]
  note: string
}

function CustomerTable({ rows }: { rows: CustomerRow[] }) {
  if (!rows.length) return <p className="text-sm text-muted-foreground">No customers in this group.</p>
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="text-muted-foreground">
            <th className="py-1 pr-3 font-medium">Customer</th>
            <th className="py-1 pr-3 font-medium">Country</th>
            <th className="py-1 pr-3 font-medium">Orders</th>
            <th className="py-1 pr-3 font-medium">Value</th>
            <th className="py-1 font-medium">Days since purchase</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.customer_id} className="border-t">
              <td className="py-1 pr-3">{row.customer_id}</td>
              <td className="py-1 pr-3">{row.country ?? "—"}</td>
              <td className="py-1 pr-3">{row.frequency}</td>
              <td className="py-1 pr-3">{formatMetric(row.historical_value)}</td>
              <td className="py-1">{row.recency_days}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function CustomerAnalyticsPage() {
  const { dataset, datePreset } = useWorkspace()
  const params = periodParams(datePreset, dataset?.min_date ?? null, dataset?.max_date ?? null)
  const [customerId, setCustomerId] = useState("")
  const [selectedId, setSelectedId] = useState("")
  const summary = useQuery({
    queryKey: ["customers", dataset?.id, params],
    queryFn: () =>
      api<CustomerAnalytics>(withQuery(`/api/v1/datasets/${dataset?.id}/analytics/customers`, params)),
    enabled: Boolean(dataset?.has_processed),
  })
  const detail = useQuery({
    queryKey: ["customer", dataset?.id, selectedId],
    queryFn: () =>
      api<CustomerDetail>(
        withQuery(`/api/v1/datasets/${dataset?.id}/analytics/customers`, { customer_id: selectedId }),
      ),
    enabled: Boolean(dataset?.has_processed && selectedId),
  })

  function lookup(event: FormEvent) {
    event.preventDefault()
    setSelectedId(customerId.trim())
  }

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="Customer Analytics"
        description="Frequency, spend, retention, and cohorts from customer IDs already in the dataset."
      />
      <DatasetGate>
        {summary.isLoading ? <p className="text-sm text-muted-foreground">Calculating customers</p> : null}
        {summary.isError ? <p className="text-sm text-destructive">{formatApiError(summary.error)}</p> : null}
        {summary.data && !summary.data.available ? <p className="text-sm">{summary.data.reason}</p> : null}
        {summary.data?.available ? (
          <div className="space-y-4">
            <dl className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-lg border bg-card p-4">
                <dt className="text-sm text-muted-foreground">Customers</dt>
                <dd className="mt-1 text-2xl font-semibold">{summary.data.customer_count}</dd>
              </div>
              <div className="rounded-lg border bg-card p-4">
                <dt className="text-sm text-muted-foreground">Repeat rate</dt>
                <dd className="mt-1 text-2xl font-semibold">{formatPercent(summary.data.repeat_rate)}</dd>
              </div>
              <div className="rounded-lg border bg-card p-4">
                <dt className="text-sm text-muted-foreground">Retention</dt>
                <dd className="mt-1 text-2xl font-semibold">{formatPercent(summary.data.retention_rate)}</dd>
                <dd className="mt-1 text-xs text-muted-foreground">{summary.data.retention_definition}</dd>
              </div>
            </dl>
            <p className="text-sm text-muted-foreground">
              Average historical value {formatMetric(summary.data.average_historical_value)}. {summary.data.value_definition}
            </p>
            <section className="rounded-lg border bg-card p-4">
              <h2 className="text-sm font-medium">Highest historical value</h2>
              <div className="mt-3">
                <CustomerTable rows={summary.data.high_value ?? []} />
              </div>
            </section>
            <section className="rounded-lg border bg-card p-4">
              <h2 className="text-sm font-medium">No purchase in 90 days</h2>
              <div className="mt-3">
                <CustomerTable rows={summary.data.inactive ?? []} />
              </div>
            </section>
            <section className="rounded-lg border bg-card p-4">
              <h2 className="text-sm font-medium">Cohorts</h2>
              <p className="mt-1 text-sm text-muted-foreground">Share of the cohort with a purchase in each later month.</p>
              <div className="mt-3 overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr>
                      <th className="py-1 pr-3 font-medium">Cohort</th>
                      <th className="py-1 pr-3 font-medium">Customers</th>
                      {(summary.data.cohorts?.[0]?.retention ?? []).map((_, index) => (
                        <th key={index} className="py-1 pr-3 font-medium">
                          M{index}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {summary.data.cohorts?.map((cohort) => (
                      <tr key={cohort.cohort} className="border-t">
                        <td className="py-1 pr-3">{cohort.cohort}</td>
                        <td className="py-1 pr-3">{cohort.customers}</td>
                        {cohort.retention.map((value, index) => (
                          <td key={index} className="py-1 pr-3">
                            {formatPercent(value)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
            <form onSubmit={lookup} className="flex flex-wrap items-end gap-2">
              <label className="text-sm">
                Look up a customer ID
                <Input className="mt-1 w-48" value={customerId} onChange={(event) => setCustomerId(event.target.value)} />
              </label>
              <Button type="submit" variant="outline" disabled={!customerId.trim()}>
                Show summary
              </Button>
            </form>
            {detail.isError ? <p className="text-sm text-destructive">{formatApiError(detail.error)}</p> : null}
            {detail.data ? (
              <section className="rounded-lg border bg-card p-4 text-sm">
                <h2 className="font-medium">{detail.data.customer_id}</h2>
                <p className="mt-1 text-muted-foreground">{detail.data.note}</p>
                <p className="mt-2">
                  {detail.data.country ?? "No country"} · {detail.data.frequency} invoices · value{" "}
                  {formatMetric(detail.data.historical_value)} · {detail.data.recency_days} days since the last purchase
                </p>
                <ul className="mt-3 space-y-1">
                  {detail.data.recent_invoices.map((invoice) => (
                    <li key={`${invoice.invoice_id}-${invoice.invoice_date}-${invoice.revenue}`}>
                      {invoice.invoice_date} · {invoice.transaction_type} · {invoice.description ?? "No description"} ·{" "}
                      {formatMetric(invoice.revenue)}
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
            <ul className="space-y-1 text-sm text-muted-foreground">
              {summary.data.limitations?.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </DatasetGate>
    </div>
  )
}
