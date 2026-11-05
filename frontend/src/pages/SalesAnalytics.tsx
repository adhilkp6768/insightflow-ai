import { useQuery } from "@tanstack/react-query"
import { useEffect, useState, type FormEvent } from "react"
import { useSearchParams } from "react-router-dom"

import { BarBreakdown, TrendChart } from "@/components/dashboard/Charts"
import { DatasetGate } from "@/components/dashboard/DatasetGate"
import { KpiCards } from "@/components/dashboard/KpiCards"
import { PageHeader } from "@/components/common/PageHeader"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useWorkspace } from "@/contexts/workspace-context"
import { periodParams, withQuery } from "@/lib/period"
import { api, formatApiError } from "@/services/api"
import type { SalesAnalytics } from "@/types/api"

type Filters = {
  countries: string[]
  products: { stock_code: string; revenue: number }[]
}

export function SalesAnalyticsPage() {
  const { dataset, datePreset } = useWorkspace()
  const [searchParams] = useSearchParams()
  const params = periodParams(datePreset, dataset?.min_date ?? null, dataset?.max_date ?? null)
  const [country, setCountry] = useState(() => searchParams.get("country") ?? "")
  const [product, setProduct] = useState("")
  const [customer, setCustomer] = useState("")
  const [customerInput, setCustomerInput] = useState("")

  useEffect(() => {
    setCountry(searchParams.get("country") ?? "")
    setProduct("")
    setCustomer("")
    setCustomerInput("")
  }, [dataset?.id, searchParams])

  const filters = useQuery({
    queryKey: ["filters", dataset?.id],
    queryFn: () => api<Filters>(`/api/v1/datasets/${dataset?.id}/analytics/filters`),
    enabled: Boolean(dataset?.has_processed),
  })
  const sales = useQuery({
    queryKey: ["sales", dataset?.id, params, country, product, customer],
    queryFn: () =>
      api<SalesAnalytics>(
        withQuery(`/api/v1/datasets/${dataset?.id}/analytics/sales`, {
          ...params,
          country: country || undefined,
          product: product || undefined,
          customer: customer || undefined,
        }),
      ),
    enabled: Boolean(dataset?.has_processed),
  })

  function applyCustomer(event: FormEvent) {
    event.preventDefault()
    setCustomer(customerInput.trim())
  }

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader title="Sales Analytics" description="Revenue, orders, and mix for the selected period." />
      <DatasetGate>
        <div className="mb-4 flex flex-wrap items-end gap-3">
          <label className="text-sm">
            Region
            <select
              aria-label="Region"
              className="mt-1 block h-9 rounded-md border border-input bg-card px-2"
              value={country}
              onChange={(event) => setCountry(event.target.value)}
            >
              <option value="">All regions</option>
              {filters.data?.countries.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm">
            Product
            <select
              aria-label="Product"
              className="mt-1 block h-9 max-w-48 rounded-md border border-input bg-card px-2"
              value={product}
              onChange={(event) => setProduct(event.target.value)}
            >
              <option value="">All products</option>
              {filters.data?.products.map((item) => (
                <option key={item.stock_code} value={item.stock_code}>
                  {item.stock_code}
                </option>
              ))}
            </select>
          </label>
          <form onSubmit={applyCustomer} className="flex items-end gap-2">
            <label className="text-sm">
              Customer ID
              <Input
                aria-label="Customer ID"
                className="mt-1 w-36"
                value={customerInput}
                onChange={(event) => setCustomerInput(event.target.value)}
              />
            </label>
            <Button type="submit" variant="outline">
              Apply
            </Button>
          </form>
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              setCountry("")
              setProduct("")
              setCustomer("")
              setCustomerInput("")
            }}
          >
            Clear filters
          </Button>
        </div>
        {sales.isLoading ? <p className="text-sm text-muted-foreground">Calculating sales</p> : null}
        {sales.isError ? <p className="text-sm text-destructive">{formatApiError(sales.error)}</p> : null}
        {sales.data ? (
          <div className="space-y-4">
            <KpiCards kpis={sales.data.kpis} definitions={sales.data.definitions} />
            <section className="rounded-lg border bg-card p-4">
              <h2 className="text-sm font-medium">Monthly revenue</h2>
              <TrendChart data={sales.data.monthly} x="period" y="revenue" />
            </section>
            <section className="rounded-lg border bg-card p-4">
              <h2 className="text-sm font-medium">Quarterly revenue</h2>
              <BarBreakdown data={sales.data.quarterly} x="period" y="revenue" />
            </section>
            <div className="grid gap-4 lg:grid-cols-2">
              <section className="rounded-lg border bg-card p-4">
                <h2 className="text-sm font-medium">Region</h2>
                <p className="mt-1 text-sm text-muted-foreground">Select a bar to filter the page to that region.</p>
                <BarBreakdown data={sales.data.countries} x="key" y="revenue" onSelect={setCountry} />
              </section>
              <section className="rounded-lg border bg-card p-4">
                <h2 className="text-sm font-medium">Products</h2>
                <BarBreakdown data={sales.data.products} x="key" y="revenue" />
              </section>
            </div>
            <div className="grid gap-4 lg:grid-cols-2">
              <section className="rounded-lg border bg-card p-4">
                <h2 className="text-sm font-medium">Purchasing by weekday</h2>
                <BarBreakdown data={sales.data.weekday} x="weekday" y="revenue" />
              </section>
              <section className="rounded-lg border bg-card p-4">
                <h2 className="text-sm font-medium">Sale value distribution</h2>
                <BarBreakdown
                  data={sales.data.distribution.map((item) => ({
                    bucket: `${item.from}–${item.to}`,
                    count: item.count,
                  }))}
                  x="bucket"
                  y="count"
                />
              </section>
            </div>
            {sales.data.categories.length ? (
              <section className="rounded-lg border bg-card p-4">
                <h2 className="text-sm font-medium">Categories</h2>
                <BarBreakdown data={sales.data.categories} x="key" y="revenue" />
              </section>
            ) : null}
            <ul className="space-y-1 text-sm text-muted-foreground">
              {sales.data.limitations.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </DatasetGate>
    </div>
  )
}
