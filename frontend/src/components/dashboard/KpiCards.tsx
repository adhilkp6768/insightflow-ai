import { DollarSign, ShoppingBag, TrendingUp, Users, Wallet, type LucideIcon } from "lucide-react"

import { Sparkline } from "@/components/dashboard/Charts"
import { formatMetric, formatPercent } from "@/lib/format"
import { cn } from "@/lib/utils"
import type { KpiValue } from "@/types/api"

const LABELS: Record<string, string> = {
  revenue: "Revenue",
  orders: "Orders",
  customers: "Customers",
  average_order_value: "Average order value",
  profit: "Profit",
}

const ICONS: Record<string, LucideIcon> = {
  revenue: DollarSign,
  orders: ShoppingBag,
  customers: Users,
  average_order_value: Wallet,
  profit: TrendingUp,
}

export function KpiCards({
  kpis,
  definitions,
  series,
}: {
  kpis: Record<string, KpiValue>
  definitions: Record<string, string>
  series?: Record<string, number[]>
}) {
  return (
    <dl className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      {Object.entries(kpis).map(([key, metric]) => {
        const Icon = ICONS[key] ?? TrendingUp
        const growth = metric.growth
        const up = growth != null && growth >= 0
        return (
          <div key={key} className="panel p-4">
            <dt className="flex items-center justify-between gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {LABELS[key] ?? key}
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary/15 text-primary">
                <Icon className="h-3.5 w-3.5" aria-hidden="true" />
              </span>
            </dt>
            <dd className="mt-3 text-2xl font-semibold tracking-tight">
              {formatMetric(metric.value, key === "orders" || key === "customers" ? 0 : 2)}
            </dd>
            <dd className="mt-2">
              {metric.value == null ? (
                <span className="text-xs text-muted-foreground">{metric.reason}</span>
              ) : (
                <span
                  className={cn(
                    "inline-flex rounded-full px-2 py-0.5 text-xs font-medium",
                    growth == null && "bg-muted text-muted-foreground",
                    growth != null && up && "bg-positive/15 text-positive",
                    growth != null && !up && "bg-negative/15 text-negative",
                  )}
                >
                  {growth == null ? "No prior window" : `${up ? "+" : ""}${formatPercent(growth)} vs prior`}
                </span>
              )}
            </dd>
            {series?.[key] ? (
              <div className="mt-2">
                <Sparkline id={key} values={series[key]} />
              </div>
            ) : null}
            {definitions[key] ? <dd className="mt-2 text-xs leading-5 text-muted-foreground">{definitions[key]}</dd> : null}
          </div>
        )
      })}
    </dl>
  )
}
