import { useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"

import { PageHeader } from "@/components/common/PageHeader"
import { DonutChart, TrendChart } from "@/components/dashboard/Charts"
import { KpiCards } from "@/components/dashboard/KpiCards"
import { buttonVariants } from "@/components/ui/button"
import { useWorkspace } from "@/contexts/workspace-context"
import { formatMetric, formatPercent } from "@/lib/format"
import { periodParams, withQuery } from "@/lib/period"
import { cn } from "@/lib/utils"
import { api, formatApiError } from "@/services/api"
import type { SalesAnalytics } from "@/types/api"

export function OverviewPage() {
  const navigate = useNavigate()
  const { workspace, dataset, datePreset, dateLabel, isLoading } = useWorkspace()
  const params = periodParams(datePreset, dataset?.min_date ?? null, dataset?.max_date ?? null)
  const [grain, setGrain] = useState<"monthly" | "quarterly">("monthly")
  const sales = useQuery({
    queryKey: ["sales", dataset?.id, params],
    queryFn: () => api<SalesAnalytics>(withQuery(`/api/v1/datasets/${dataset?.id}/analytics/sales`, params)),
    enabled: Boolean(dataset?.has_processed),
  })
  const points = grain === "monthly" ? sales.data?.monthly : sales.data?.quarterly
  const mix = sales.data?.categories.length ? sales.data.categories : sales.data?.countries

  return (
    <div className="mx-auto max-w-[1400px]">
      <PageHeader
        title="Overview"
        description={
          dataset
            ? `${dataset.name} · ${dateLabel}${sales.data?.period.date_from ? ` · ${sales.data.period.date_from} to ${sales.data.period.date_to}` : ""}`
            : "Connect a cleaned dataset to see calculated performance."
        }
      />
      {isLoading ? <p className="text-sm text-muted-foreground">Loading workspace</p> : null}
      {!isLoading && !workspace ? <p className="text-sm text-muted-foreground">No workspace is available for this account.</p> : null}
      {!dataset ? (
        <Link to="/data" className={cn(buttonVariants())}>
          Connect a dataset
        </Link>
      ) : null}
      {dataset && !dataset.has_processed ? (
        <p className="panel p-4 text-sm text-muted-foreground">
          Create a cleaned version before KPIs are calculated. The uploaded file stays unchanged.
        </p>
      ) : null}
      {sales.isLoading ? <p className="text-sm text-muted-foreground">Calculating KPIs from the cleaned rows.</p> : null}
      {sales.isError ? <p className="text-sm text-destructive">{formatApiError(sales.error)}</p> : null}
      {sales.data ? (
        <div className="space-y-4">
          <KpiCards
            kpis={sales.data.kpis}
            definitions={sales.data.definitions}
            series={{
              revenue: sales.data.monthly.map((item) => item.revenue),
              orders: sales.data.monthly.map((item) => item.orders),
              customers: sales.data.monthly.map((item) => item.customers),
            }}
          />
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1.6fr)_minmax(280px,0.8fr)]">
            <section className="panel p-4">
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h2 className="text-sm font-medium">Revenue over time</h2>
                  <p className="text-xs text-muted-foreground">Calculated from valid rows in the selected period.</p>
                </div>
                <div className="flex rounded-full border p-0.5" role="group" aria-label="Chart grain">
                  {(["monthly", "quarterly"] as const).map((item) => (
                    <button
                      key={item}
                      type="button"
                      className={cn(
                        "rounded-full px-3 py-1 text-xs capitalize",
                        grain === item ? "bg-primary text-primary-foreground" : "text-muted-foreground",
                      )}
                      aria-pressed={grain === item}
                      onClick={() => setGrain(item)}
                    >
                      {item}
                    </button>
                  ))}
                </div>
              </div>
              <TrendChart data={points ?? []} x="period" y="revenue" />
            </section>
            <section className="panel p-4">
              <h2 className="text-sm font-medium">{sales.data.categories.length ? "Revenue by category" : "Revenue by region"}</h2>
              <p className="mb-2 text-xs text-muted-foreground">Shares use the same revenue total as the KPI.</p>
              <DonutChart data={mix ?? []} onSelect={(key) => navigate(`/sales?country=${encodeURIComponent(key)}`)} />
            </section>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <section className="panel p-4">
              <h2 className="text-sm font-medium">Top products</h2>
              <ul className="mt-4 space-y-3">
                {sales.data.products.slice(0, 6).map((item) => {
                  const top = sales.data?.products[0]?.revenue || 1
                  return (
                    <li key={item.key}>
                      <div className="flex items-center justify-between gap-3 text-sm">
                        <span className="truncate">{item.key}</span>
                        <span className="shrink-0 text-muted-foreground">{formatMetric(item.revenue)}</span>
                      </div>
                      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-muted">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-primary to-[hsl(var(--chart-2))]"
                          style={{ width: `${Math.max((item.revenue / top) * 100, 4)}%` }}
                        />
                      </div>
                    </li>
                  )
                })}
              </ul>
            </section>
            <section className="panel p-4">
              <h2 className="text-sm font-medium">Weekday pattern</h2>
              <TrendChart data={sales.data.weekday} x="weekday" y="revenue" height={220} />
            </section>
          </div>
          {sales.data.limitations.length ? (
            <section className="panel border-primary/30 bg-primary/5 p-4">
              <h2 className="text-sm font-medium">How to read this</h2>
              <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
                {sales.data.limitations.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              <p className="mt-3 text-xs text-muted-foreground">
                Largest region share {formatPercent(sales.data.countries[0]?.share)}. Dataset role {workspace?.role}.
              </p>
            </section>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
