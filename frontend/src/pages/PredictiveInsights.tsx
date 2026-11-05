import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"

import { TrendChart } from "@/components/dashboard/Charts"
import { DatasetGate } from "@/components/dashboard/DatasetGate"
import { JobBanner } from "@/components/common/JobBanner"
import { PageHeader } from "@/components/common/PageHeader"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useWorkspace } from "@/contexts/workspace-context"
import { formatMetric } from "@/lib/format"
import { useJobWatcher, type JobRecord } from "@/lib/jobs"
import { api, formatApiError } from "@/services/api"

type ModelRun = {
  id: string
  model_type: string
  status: string
  created_at: string
  result: Record<string, unknown>
}

function asList<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : []
}

export function PredictiveInsightsPage() {
  const queryClient = useQueryClient()
  const { dataset, workspaceId } = useWorkspace()
  const [days, setDays] = useState(90)
  const [error, setError] = useState("")
  const [jobId, setJobId] = useState<string | null>(null)
  const trackedJob = useJobWatcher(jobId, (job) => {
    setJobId(null)
    if (job.status === "failed") {
      setError(job.message || "Training failed.")
      return
    }
    setError("")
    void queryClient.invalidateQueries({ queryKey: ["models", dataset?.id] })
    void queryClient.invalidateQueries({ queryKey: ["notifications", workspaceId] })
  })
  const models = useQuery({
    queryKey: ["models", dataset?.id],
    queryFn: () => api<ModelRun[]>(`/api/v1/datasets/${dataset?.id}/models`),
    enabled: Boolean(dataset?.has_processed),
  })
  const train = useMutation({
    mutationFn: (modelType: string) =>
      api<ModelRun | { job: JobRecord }>(`/api/v1/datasets/${dataset?.id}/models/${modelType}`, {
        method: "POST",
        body: { inactivity_days: days },
      }),
    onSuccess: (payload) => {
      if ("job" in payload && payload.job.status !== "succeeded") {
        setJobId(payload.job.id)
        setError("")
        return
      }
      setError("")
      void queryClient.invalidateQueries({ queryKey: ["models", dataset?.id] })
      void queryClient.invalidateQueries({ queryKey: ["notifications", workspaceId] })
    },
    onError: (reason) => setError(formatApiError(reason)),
  })

  const latest = (type: string) => models.data?.find((item) => item.model_type === type)

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="Predictive Insights"
        description="Segmentation, inferred churn, and a revenue forecast trained on the cleaned dataset."
      />
      <DatasetGate>
        <JobBanner job={trackedJob.data} />
        {error ? <p className="mb-3 text-sm text-destructive">{error}</p> : null}
        <div className="mb-4 flex flex-wrap items-end gap-2">
          <label className="text-sm">
            Churn inactivity days
            <Input
              aria-label="Churn inactivity days"
              className="mt-1 w-28"
              type="number"
              min={14}
              max={365}
              value={days}
              onChange={(event) => setDays(Number(event.target.value))}
            />
          </label>
          <Button type="button" disabled={train.isPending || Boolean(jobId)} onClick={() => train.mutate("segments")}>
            Train segments
          </Button>
          <Button type="button" variant="outline" disabled={train.isPending || Boolean(jobId)} onClick={() => train.mutate("churn")}>
            Train churn
          </Button>
          <Button type="button" variant="outline" disabled={train.isPending || Boolean(jobId)} onClick={() => train.mutate("forecast")}>
            Train forecast
          </Button>
        </div>
        {train.isPending ? <p className="mb-4 text-sm text-muted-foreground">Starting training.</p> : null}
        <div className="space-y-4">
          <ModelCard title="Segments" run={latest("segments")} />
          <ModelCard title="Churn" run={latest("churn")} />
          <ModelCard title="Forecast" run={latest("forecast")} />
        </div>
      </DatasetGate>
    </div>
  )
}

function ModelCard({ title, run }: { title: string; run: ModelRun | undefined }) {
  if (!run) {
    return (
      <section className="rounded-lg border bg-card p-4">
        <h2 className="text-sm font-medium">{title}</h2>
        <p className="mt-2 text-sm text-muted-foreground">No saved run yet.</p>
      </section>
    )
  }
  const result = run.result
  const reason = typeof result.reason === "string" ? result.reason : null
  const clusters = asList<{ id: number; label: string; size: number; avg_monetary: number; avg_recency_days: number }>(
    result.clusters,
  )
  const scored = asList<{ algorithm: string; accuracy: number; precision: number; recall: number; f1: number; roc_auc: number | null }>(
    result.models,
  )
  const importance = asList<{ feature: string; importance: number }>(result.feature_importance)
  const comparison = asList<{ date: string; actual: number; model: number | null }>(result.comparison)
  const forward = asList<{ date: string; value: number; lower: number | null; upper: number | null }>(result.forecast)
  const ranked = asList<{ rank: number; customer_id: string; score: number }>(result.at_risk_preview)
  const limitations = asList<string>(result.limitations)
  return (
    <section className="rounded-lg border bg-card p-4">
      <h2 className="text-sm font-medium">
        {title} · {run.status}
      </h2>
      {reason ? <p className="mt-2 text-sm">{reason}</p> : null}
      {typeof result.label_definition === "string" ? <p className="mt-2 text-sm">{result.label_definition}</p> : null}
      {typeof result.silhouette === "number" ? (
        <p className="mt-2 text-sm text-muted-foreground">
          k={String(result.k)} · silhouette {formatMetric(result.silhouette, 3)}
        </p>
      ) : null}
      {clusters.length ? (
        <ul className="mt-3 space-y-1 text-sm">
          {clusters.map((cluster) => (
            <li key={cluster.id}>
              {cluster.label}: {cluster.size} customers, average value {formatMetric(cluster.avg_monetary)}, average recency{" "}
              {formatMetric(cluster.avg_recency_days, 0)} days
            </li>
          ))}
        </ul>
      ) : null}
      {scored.length ? (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="text-muted-foreground">
                <th className="py-1 pr-3 font-medium">Model</th>
                <th className="py-1 pr-3 font-medium">Accuracy</th>
                <th className="py-1 pr-3 font-medium">Precision</th>
                <th className="py-1 pr-3 font-medium">Recall</th>
                <th className="py-1 pr-3 font-medium">F1</th>
                <th className="py-1 font-medium">ROC-AUC</th>
              </tr>
            </thead>
            <tbody>
              {scored.map((model) => (
                <tr key={model.algorithm} className="border-t">
                  <td className="py-1 pr-3">{model.algorithm}</td>
                  <td className="py-1 pr-3">{formatMetric(model.accuracy, 3)}</td>
                  <td className="py-1 pr-3">{formatMetric(model.precision, 3)}</td>
                  <td className="py-1 pr-3">{formatMetric(model.recall, 3)}</td>
                  <td className="py-1 pr-3">{formatMetric(model.f1, 3)}</td>
                  <td className="py-1">{formatMetric(model.roc_auc, 3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {importance.length ? (
        <p className="mt-3 text-sm text-muted-foreground">
          {String(result.importance_method)}:{" "}
          {importance.map((item) => `${item.feature} ${formatMetric(item.importance, 2)}`).join(", ")}
        </p>
      ) : null}
      {typeof result.score_note === "string" ? <p className="mt-2 text-sm">{result.score_note}</p> : null}
      {typeof result.unlabeled_customers === "number" ? (
        <p className="mt-2 text-sm text-muted-foreground">
          {result.unlabeled_customers.toLocaleString()} customers were too new to label, so they are not in this ranking.
        </p>
      ) : null}
      {ranked.length ? (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="text-muted-foreground">
                <th className="py-1 pr-3 font-medium">Rank</th>
                <th className="py-1 pr-3 font-medium">Customer</th>
                <th className="py-1 font-medium">Score</th>
              </tr>
            </thead>
            <tbody>
              {ranked.map((item) => (
                <tr key={item.customer_id} className="border-t">
                  <td className="py-1 pr-3">{item.rank}</td>
                  <td className="py-1 pr-3">{item.customer_id}</td>
                  <td className="py-1">{formatMetric(item.score, 3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {typeof result.reliable === "boolean" ? (
        <p className="mt-2 text-sm">
          {result.reliable
            ? "The forecast meets the reliability rule: at least 180 days and holdout MAPE under 35%."
            : "The forecast is not marked reliable. Treat the forward line as a calculation, not a commitment."}
        </p>
      ) : null}
      {comparison.length ? (
        <div className="mt-3">
          <h3 className="text-sm font-medium">Holdout: actual and model</h3>
          <TrendChart data={comparison} x="date" y="actual" y2="model" />
        </div>
      ) : null}
      {forward.length ? (
        <div className="mt-3">
          <h3 className="text-sm font-medium">Next 30 days</h3>
          <p className="text-sm text-muted-foreground">The band is 1.96 residual standard deviations, not a formal prediction interval.</p>
          <TrendChart
            data={forward.slice(0, 30)}
            x="date"
            y="value"
            series={[
              { key: "value", name: "Forecast" },
              { key: "lower", name: "Lower band" },
              { key: "upper", name: "Upper band" },
            ]}
          />
        </div>
      ) : null}
      <ul className="mt-3 space-y-1 text-sm text-muted-foreground">
        {limitations.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  )
}
