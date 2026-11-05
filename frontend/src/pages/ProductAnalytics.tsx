import { useQuery } from "@tanstack/react-query"

import { BarBreakdown, TrendChart } from "@/components/dashboard/Charts"
import { DatasetGate } from "@/components/dashboard/DatasetGate"
import { PageHeader } from "@/components/common/PageHeader"
import { useWorkspace } from "@/contexts/workspace-context"
import { formatMetric, formatPercent } from "@/lib/format"
import { periodParams, withQuery } from "@/lib/period"
import { api, formatApiError } from "@/services/api"

type ProductRow = {
  stock_code: string
  description: string | null
  revenue: number
  units_sold: number
  units_returned: number
  share: number | null
}

type ProductAnalytics = {
  products: ProductRow[]
  categories: { key: string; revenue: number }[]
  category_available: boolean
  category_reason: string | null
  monthly: { period: string; revenue: number }[]
}

export function ProductAnalyticsPage() {
  const { dataset, datePreset } = useWorkspace()
  const params = periodParams(datePreset, dataset?.min_date ?? null, dataset?.max_date ?? null)
  const products = useQuery({
    queryKey: ["products", dataset?.id, params],
    queryFn: () => api<ProductAnalytics>(withQuery(`/api/v1/datasets/${dataset?.id}/analytics/products`, params)),
    enabled: Boolean(dataset?.has_processed),
  })

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader title="Product Analytics" description="Revenue, units, and returns by product." />
      <DatasetGate>
        {products.isLoading ? <p className="text-sm text-muted-foreground">Calculating products</p> : null}
        {products.isError ? <p className="text-sm text-destructive">{formatApiError(products.error)}</p> : null}
        {products.data ? (
          <div className="space-y-4">
            <section className="rounded-lg border bg-card p-4">
              <h2 className="text-sm font-medium">Top products</h2>
              <p className="mt-1 text-sm text-muted-foreground">Bars use the product code so the same description is not mixed together.</p>
              <BarBreakdown
                data={products.data.products.slice(0, 8).map((item) => ({
                  key: item.stock_code,
                  revenue: item.revenue,
                }))}
                x="key"
                y="revenue"
              />
            </section>
            <section className="overflow-x-auto rounded-lg border bg-card p-4">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="text-muted-foreground">
                    <th className="py-1 pr-3 font-medium">Product</th>
                    <th className="py-1 pr-3 font-medium">Revenue</th>
                    <th className="py-1 pr-3 font-medium">Share</th>
                    <th className="py-1 pr-3 font-medium">Units sold</th>
                    <th className="py-1 font-medium">Units returned</th>
                  </tr>
                </thead>
                <tbody>
                  {products.data.products.map((item) => (
                    <tr key={`${item.stock_code}-${item.description}`} className="border-t">
                      <td className="py-1 pr-3">
                        <span className="block">{item.description || "No description"}</span>
                        <span className="text-muted-foreground">{item.stock_code}</span>
                      </td>
                      <td className="py-1 pr-3">{formatMetric(item.revenue)}</td>
                      <td className="py-1 pr-3">{formatPercent(item.share)}</td>
                      <td className="py-1 pr-3">{formatMetric(item.units_sold, 0)}</td>
                      <td className="py-1">{formatMetric(item.units_returned, 0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
            <section className="rounded-lg border bg-card p-4">
              <h2 className="text-sm font-medium">Categories</h2>
              {products.data.category_available ? (
                <BarBreakdown data={products.data.categories} x="key" y="revenue" />
              ) : (
                <p className="mt-2 text-sm text-muted-foreground">{products.data.category_reason}</p>
              )}
            </section>
            <section className="rounded-lg border bg-card p-4">
              <h2 className="text-sm font-medium">Monthly revenue</h2>
              <TrendChart data={products.data.monthly} x="period" y="revenue" />
            </section>
          </div>
        ) : null}
      </DatasetGate>
    </div>
  )
}
