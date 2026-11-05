import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"

import { DatasetGate } from "@/components/dashboard/DatasetGate"
import { PageHeader } from "@/components/common/PageHeader"
import { Button } from "@/components/ui/button"
import { useWorkspace } from "@/contexts/workspace-context"
import { api, downloadAuthenticated, formatApiError } from "@/services/api"

const REPORTS = [
  { id: "monthly_sales", label: "Monthly sales" },
  { id: "quarterly", label: "Quarterly performance" },
  { id: "customer", label: "Customer analytics" },
  { id: "product", label: "Product analytics" },
  { id: "predictive", label: "Predictive summary" },
  { id: "executive", label: "Executive summary" },
]

type ReportItem = {
  id: string
  title: string
  report_type: string
  created_at: string
  summary: {
    findings?: string[]
    risks?: string[]
    recommendations?: string[]
    kpis?: { label: string; value: string }[]
  }
}

export function ReportsPage() {
  const queryClient = useQueryClient()
  const { workspaceId, dataset } = useWorkspace()
  const [reportType, setReportType] = useState("executive")
  const [error, setError] = useState("")
  const reports = useQuery({
    queryKey: ["reports", workspaceId],
    queryFn: () => api<ReportItem[]>(`/api/v1/workspaces/${workspaceId}/reports`),
    enabled: Boolean(workspaceId),
  })
  const generate = useMutation({
    mutationFn: () =>
      api<ReportItem>("/api/v1/reports", {
        method: "POST",
        body: { dataset_id: dataset?.id, report_type: reportType },
      }),
    onSuccess: () => {
      setError("")
      void queryClient.invalidateQueries({ queryKey: ["reports", workspaceId] })
      void queryClient.invalidateQueries({ queryKey: ["notifications", workspaceId] })
    },
    onError: (reason) => setError(formatApiError(reason)),
  })

  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        title="Reports"
        description="Reports use the same calculations as the dashboards and can be downloaded as PDF, Excel, or CSV."
      />
      <DatasetGate>
        <div className="flex flex-wrap items-end gap-2">
          <label className="text-sm">
            Report
            <select
              aria-label="Report type"
              className="mt-1 block h-9 rounded-md border border-input bg-card px-2"
              value={reportType}
              onChange={(event) => setReportType(event.target.value)}
            >
              {REPORTS.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
          <Button type="button" disabled={generate.isPending} onClick={() => generate.mutate()}>
            {generate.isPending ? "Building" : "Generate report"}
          </Button>
        </div>
        {error ? <p className="mt-3 text-sm text-destructive">{error}</p> : null}
        <div className="mt-4 space-y-3">
          {reports.data?.map((report) => (
            <article key={report.id} className="rounded-lg border bg-card p-4">
              <h2 className="text-sm font-medium">{report.title}</h2>
              <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
                {(report.summary.findings ?? []).slice(0, 3).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
              <div className="mt-3 flex gap-2">
                {(["pdf", "xlsx", "csv"] as const).map((format) => (
                  <Button
                    key={format}
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      void downloadAuthenticated(
                        `/api/v1/reports/${report.id}/download?file_format=${format}`,
                        `${report.report_type}.${format}`,
                      ).catch((reason) => setError(formatApiError(reason)))
                    }}
                  >
                    {format.toUpperCase()}
                  </Button>
                ))}
              </div>
            </article>
          ))}
          {reports.data && !reports.data.length ? (
            <p className="text-sm text-muted-foreground">No reports yet.</p>
          ) : null}
        </div>
      </DatasetGate>
    </div>
  )
}
