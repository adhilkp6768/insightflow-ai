import { useId } from "react"
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"

import { formatMetric, formatPercent } from "@/lib/format"

type Point = Record<string, string | number | null>

const SERIES = [
  "hsl(var(--chart-1))",
  "hsl(var(--chart-2))",
  "hsl(var(--chart-3))",
  "hsl(var(--chart-4))",
  "hsl(var(--chart-5))",
]

const tooltipStyle = {
  background: "hsl(var(--popover))",
  border: "1px solid hsl(var(--border))",
  borderRadius: 12,
  color: "hsl(var(--popover-foreground))",
  fontSize: 12,
}

const axisTick = { fontSize: 11, fill: "hsl(var(--muted-foreground))" }

function compactAxis(value: number) {
  return new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(value)
}

export function TrendChart({
  data,
  x,
  y,
  y2,
  series,
  height = 280,
}: {
  data: Point[]
  x: string
  y: string
  y2?: string
  series?: { key: string; name: string }[]
  height?: number
}) {
  const chartId = useId().replace(/:/g, "")
  if (!data.length) return <p className="text-sm text-muted-foreground">No points in this period.</p>
  const lines = series ?? [{ key: y, name: y }, ...(y2 ? [{ key: y2, name: y2 }] : [])]
  if (lines.length === 1) {
    const key = lines[0].key
    return (
      <div className="w-full" style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id={`area-${chartId}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="hsl(var(--chart-1))" stopOpacity={0.45} />
                <stop offset="100%" stopColor="hsl(var(--chart-1))" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="hsl(var(--border))" vertical={false} />
            <XAxis dataKey={x} tick={axisTick} tickLine={false} axisLine={false} minTickGap={24} />
            <YAxis tick={axisTick} tickFormatter={compactAxis} tickLine={false} axisLine={false} width={48} />
            <Tooltip contentStyle={tooltipStyle} />
            <Area type="monotone" dataKey={key} name={lines[0].name} stroke="hsl(var(--chart-1))" fill={`url(#area-${chartId})`} strokeWidth={2.5} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    )
  }
  return (
    <div className="w-full" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="hsl(var(--border))" vertical={false} />
          <XAxis dataKey={x} tick={axisTick} tickLine={false} axisLine={false} minTickGap={24} />
          <YAxis tick={axisTick} tickFormatter={compactAxis} tickLine={false} axisLine={false} width={48} />
          <Tooltip contentStyle={tooltipStyle} />
          <Legend />
          {lines.map((line, index) => (
            <Line
              key={line.key}
              type="monotone"
              dataKey={line.key}
              name={line.name}
              stroke={SERIES[index % SERIES.length]}
              strokeWidth={2.5}
              dot={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export function Sparkline({ values, id }: { values: number[]; id: string }) {
  if (values.length < 2) return null
  const data = values.map((value, index) => ({ index, value }))
  const fillId = `spark-${id}`
  return (
    <div className="h-10 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data}>
          <defs>
            <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="hsl(var(--chart-2))" stopOpacity={0.55} />
              <stop offset="100%" stopColor="hsl(var(--chart-2))" stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area type="monotone" dataKey="value" stroke="hsl(var(--chart-2))" fill={`url(#${fillId})`} strokeWidth={1.75} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

export function DonutChart({
  data,
  onSelect,
}: {
  data: { key: string; revenue: number; share: number | null }[]
  onSelect?: (key: string) => void
}) {
  const rows = data.filter((item) => item.revenue > 0).slice(0, 6)
  if (!rows.length) return <p className="text-sm text-muted-foreground">No groups in this period.</p>
  const total = rows.reduce((sum, item) => sum + item.revenue, 0)
  return (
    <div className="grid items-center gap-3 sm:grid-cols-[180px_1fr]">
      <div className="h-44">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={rows}
              dataKey="revenue"
              nameKey="key"
              innerRadius={52}
              outerRadius={74}
              paddingAngle={3}
              stroke="transparent"
              onClick={(item) => {
                const key = (item as { key?: string }).key
                if (key && onSelect) onSelect(key)
              }}
            >
              {rows.map((item, index) => (
                <Cell key={item.key} fill={SERIES[index % SERIES.length]} className="cursor-pointer" />
              ))}
            </Pie>
            <Tooltip contentStyle={tooltipStyle} formatter={(value) => formatMetric(Number(value))} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <ul className="space-y-2">
        {rows.map((item, index) => (
          <li key={item.key}>
            <button
              type="button"
              className="flex w-full items-center gap-2 text-left text-sm"
              onClick={() => onSelect?.(item.key)}
            >
              <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: SERIES[index % SERIES.length] }} />
              <span className="min-w-0 flex-1 truncate">{item.key}</span>
              <span className="text-muted-foreground">{formatPercent(item.share ?? item.revenue / total)}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function BarBreakdown({
  data,
  x,
  y,
  onSelect,
}: {
  data: Point[]
  x: string
  y: string
  onSelect?: (key: string) => void
}) {
  if (!data.length) return <p className="text-sm text-muted-foreground">No groups in this period.</p>
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid stroke="hsl(var(--border))" vertical={false} />
          <XAxis dataKey={x} tick={axisTick} interval={0} angle={-18} height={64} textAnchor="end" tickLine={false} axisLine={false} />
          <YAxis tick={axisTick} tickFormatter={compactAxis} width={48} tickLine={false} axisLine={false} />
          <Tooltip contentStyle={tooltipStyle} />
          <Bar
            dataKey={y}
            radius={[8, 8, 0, 0]}
            onClick={(item) => {
              const payload = item as { payload?: Point }
              const key = payload.payload?.[x]
              if (key != null && onSelect) onSelect(String(key))
            }}
          >
            {data.map((item, index) => (
              <Cell key={String(item[x] ?? index)} fill={SERIES[index % SERIES.length]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
