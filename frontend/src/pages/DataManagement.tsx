import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useEffect, useState, type FormEvent } from "react"

import { JobBanner } from "@/components/common/JobBanner"
import { PageHeader } from "@/components/common/PageHeader"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useWorkspace } from "@/contexts/workspace-context"
import { formatMetric } from "@/lib/format"
import { useJobWatcher, type JobRecord } from "@/lib/jobs"
import { api, apiForm, formatApiError } from "@/services/api"
import type { DatasetDetail } from "@/types/api"

type Preview = {
  columns: string[]
  rows: Record<string, unknown>[]
  total: number
  limit: number
  offset: number
}

export function DataManagementPage() {
  const queryClient = useQueryClient()
  const { workspaceId, datasetId, setDatasetId, datasets } = useWorkspace()
  const [file, setFile] = useState<File | null>(null)
  const [name, setName] = useState("")
  const [message, setMessage] = useState("")
  const [error, setError] = useState("")
  const [mapping, setMapping] = useState<Record<string, string | null>>({})
  const [stage, setStage] = useState<"raw" | "processed">("raw")
  const [dropDuplicates, setDropDuplicates] = useState(false)
  const [jobId, setJobId] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const trackedJob = useJobWatcher(jobId, (job) => {
    setJobId(null)
    if (job.status === "failed") {
      setError(job.message || "The job failed.")
      return
    }
    setError("")
    if (job.dataset_id) setDatasetId(job.dataset_id)
    if (job.job_type === "prepare") {
      setStage("processed")
      setMessage("Cleaned version created. Invalid rows stay in it and are excluded from KPIs.")
    } else if (job.job_type === "uci") {
      setMessage(job.message || "Online Retail II is profiled. The original workbook is unchanged.")
    } else {
      setMessage(job.message || "Finished.")
    }
    refresh()
  })

  const detail = useQuery({
    queryKey: ["dataset", datasetId],
    queryFn: () => api<DatasetDetail>(`/api/v1/datasets/${datasetId}`),
    enabled: Boolean(datasetId),
  })
  const preview = useQuery({
    queryKey: ["preview", datasetId, stage],
    queryFn: () => api<Preview>(`/api/v1/datasets/${datasetId}/preview?stage=${stage}&limit=8`),
    enabled: Boolean(datasetId) && (stage === "raw" || Boolean(detail.data?.has_processed)),
  })

  useEffect(() => {
    if (detail.data) setMapping(detail.data.mapping)
  }, [detail.data])

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: ["datasets"] })
    void queryClient.invalidateQueries({ queryKey: ["dataset"] })
    void queryClient.invalidateQueries({ queryKey: ["preview"] })
    void queryClient.invalidateQueries({ queryKey: ["notifications", workspaceId] })
  }

  const upload = useMutation({
    mutationFn: async () => {
      if (!file || !workspaceId) return null
      const form = new FormData()
      form.set("file", file)
      if (name.trim()) form.set("name", name.trim())
      return apiForm<DatasetDetail>(`/api/v1/workspaces/${workspaceId}/datasets`, form)
    },
    onSuccess: (created) => {
      if (!created) return
      setDatasetId(created.id)
      setFile(null)
      setName("")
      setMessage(`${created.name} is profiled. The original file is stored unchanged.`)
      setError("")
      refresh()
    },
    onError: (reason) => setError(formatApiError(reason)),
  })

  function track(job: JobRecord | null | undefined) {
    if (!job || job.status === "succeeded") return false
    setJobId(job.id)
    setMessage(job.message || "Working in the background.")
    setError("")
    return true
  }

  const sample = useMutation({
    mutationFn: () => api<DatasetDetail>(`/api/v1/workspaces/${workspaceId}/datasets/sample`, { method: "POST" }),
    onSuccess: (created) => {
      setDatasetId(created.id)
      setMessage("Sample transactions are loaded. This is a generated fixture, not the UCI workbook.")
      setError("")
      refresh()
    },
    onError: (reason) => setError(formatApiError(reason)),
  })

  const saveMapping = useMutation({
    mutationFn: () => api<DatasetDetail>(`/api/v1/datasets/${datasetId}/mapping`, { method: "PUT", body: { mapping } }),
    onSuccess: () => {
      setMessage("Column roles saved and the quality score was recalculated.")
      setError("")
      refresh()
    },
    onError: (reason) => setError(formatApiError(reason)),
  })

  const uci = useMutation({
    mutationFn: () =>
      api<{ dataset: DatasetDetail | null; job: JobRecord | null }>(
        `/api/v1/workspaces/${workspaceId}/datasets/uci`,
        { method: "POST" },
      ),
    onSuccess: (payload) => {
      if (track(payload.job)) return
      if (payload.dataset) {
        setDatasetId(payload.dataset.id)
        setMessage("Online Retail II is in this workspace. The original workbook is unchanged.")
        setError("")
        refresh()
      }
    },
    onError: (reason) => setError(formatApiError(reason)),
  })

  const prepare = useMutation({
    mutationFn: () =>
      api<DatasetDetail | { job: JobRecord }>(`/api/v1/datasets/${datasetId}/prepare`, {
        method: "POST",
        body: { drop_exact_duplicates: dropDuplicates },
      }),
    onSuccess: (payload) => {
      if ("job" in payload && track(payload.job)) return
      setStage("processed")
      setMessage("Cleaned version created. Invalid rows stay in it and are excluded from KPIs.")
      setError("")
      refresh()
    },
    onError: (reason) => setError(formatApiError(reason)),
  })

  const remove = useMutation({
    mutationFn: () => api<void>(`/api/v1/datasets/${datasetId}`, { method: "DELETE" }),
    onSuccess: () => {
      setDatasetId("")
      setConfirmDelete(false)
      setMessage("Dataset deleted, including its cleaned table and files.")
      setError("")
      refresh()
    },
    onError: (reason) => setError(formatApiError(reason)),
  })

  function onUpload(event: FormEvent) {
    event.preventDefault()
    upload.mutate()
  }

  const profile = detail.data?.profile
  const columns = profile?.columns.map((column) => column.name) ?? []

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="Data Management"
        description="Upload a CSV or Excel file, review its quality, and create a cleaned copy. The original file is not modified."
      />
      <JobBanner job={trackedJob.data} />
      {message ? <p className="mb-4 rounded-lg border bg-card px-4 py-3 text-sm">{message}</p> : null}
      {error ? (
        <p className="mb-4 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </p>
      ) : null}
      <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
        <section className="rounded-lg border bg-card p-4">
          <h2 className="text-sm font-medium">Datasets</h2>
          <ul className="mt-3 space-y-2">
            {datasets.map((dataset) => (
              <li key={dataset.id}>
                <button
                  type="button"
                  className={`w-full rounded-md border px-3 py-2 text-left text-sm ${dataset.id === datasetId ? "border-primary" : ""}`}
                  onClick={() => setDatasetId(dataset.id)}
                >
                  <span className="block font-medium">{dataset.name}</span>
                  <span className="text-muted-foreground">
                    {dataset.row_count.toLocaleString()} rows
                    {dataset.has_processed ? " · cleaned" : " · raw only"}
                  </span>
                </button>
              </li>
            ))}
            {!datasets.length ? <li className="text-sm text-muted-foreground">No datasets yet.</li> : null}
          </ul>
        </section>
        <div className="space-y-4">
          <form onSubmit={onUpload} className="rounded-lg border bg-card p-4">
            <h2 className="text-sm font-medium">Upload</h2>
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <label className="text-sm">
                File
                <input
                  aria-label="Dataset file"
                  className="mt-1 block w-full text-sm"
                  type="file"
                  accept=".csv,.xlsx"
                  onChange={(event) => setFile(event.target.files?.[0] ?? null)}
                />
              </label>
              <label className="text-sm">
                Name
                <Input className="mt-1" value={name} onChange={(event) => setName(event.target.value)} />
              </label>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button type="submit" disabled={!file || upload.isPending || Boolean(jobId)}>
                {upload.isPending ? "Uploading" : "Upload file"}
              </Button>
              <Button type="button" variant="outline" disabled={sample.isPending || Boolean(jobId)} onClick={() => sample.mutate()}>
                {sample.isPending ? "Loading sample" : "Load sample"}
              </Button>
              <Button type="button" variant="outline" disabled={uci.isPending || Boolean(jobId)} onClick={() => uci.mutate()}>
                {uci.isPending || trackedJob.data?.job_type === "uci" ? "Loading UCI" : "Load Online Retail II"}
              </Button>
            </div>
            <p className="mt-3 text-sm leading-6 text-muted-foreground">
              CSV and XLSX up to 100 MB. The sample is a small generated fixture. Online Retail II is the UCI dataset
              (Chen, Daqing, 2019) and is downloaded, profiled, and kept out of git. Cleaning and training continue
              after you leave this page.
            </p>
          </form>
          {detail.data ? (
            <section className="rounded-lg border bg-card p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="text-sm font-medium">{detail.data.name}</h2>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {detail.data.row_count.toLocaleString()} rows · {detail.data.column_count} columns ·{" "}
                    {detail.data.source_type === "sample"
                      ? "Generated sample"
                      : detail.data.source_type === "uci"
                        ? "UCI Online Retail II"
                        : detail.data.original_filename}
                  </p>
                </div>
                {confirmDelete ? (
                  <div className="flex items-center gap-2">
                    <Button type="button" variant="outline" onClick={() => setConfirmDelete(false)}>
                      Keep
                    </Button>
                    <Button type="button" disabled={remove.isPending} onClick={() => remove.mutate()}>
                      {remove.isPending ? "Deleting" : "Delete permanently"}
                    </Button>
                  </div>
                ) : (
                  <Button type="button" variant="outline" onClick={() => setConfirmDelete(true)}>
                    Delete dataset
                  </Button>
                )}
              </div>
              {detail.data.error_message ? <p className="mt-3 text-sm text-destructive">{detail.data.error_message}</p> : null}
              {profile ? (
                <div className="mt-4">
                  <p className="text-2xl font-semibold">{formatMetric(profile.score, 1)}</p>
                  <p className="text-sm text-muted-foreground">{profile.formula}</p>
                  <dl className="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                    <div>
                      <dt className="text-muted-foreground">Completeness</dt>
                      <dd>{formatMetric(profile.completeness * 100, 1)}%</dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Uniqueness</dt>
                      <dd>{formatMetric(profile.uniqueness * 100, 1)}%</dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Validity</dt>
                      <dd>{formatMetric(profile.validity * 100, 1)}%</dd>
                    </div>
                    <div>
                      <dt className="text-muted-foreground">Consistency</dt>
                      <dd>{formatMetric(profile.consistency * 100, 1)}%</dd>
                    </div>
                  </dl>
                  <p className="mt-3 text-sm text-muted-foreground">
                    {profile.duplicate_rows.toLocaleString()} exact duplicate rows · {profile.missing_values.toLocaleString()} missing values
                  </p>
                  <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
                    {profile.notes.map((note) => (
                      <li key={note}>{note}</li>
                    ))}
                    {Object.entries(profile.outliers).map(([key, value]) => (
                      <li key={key}>
                        {key} outliers: {value.count ?? 0}
                        {value.note ? ` (${value.note})` : ""}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              <h3 className="mt-6 text-sm font-medium">Column roles</h3>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                {Object.entries(detail.data.role_labels).map(([role, label]) => (
                  <label key={role} className="text-sm">
                    {label}
                    {detail.data?.missing_roles.includes(role) ? " (required)" : ""}
                    <select
                      aria-label={label}
                      className="mt-1 h-9 w-full rounded-md border border-input bg-card px-2"
                      value={mapping[role] ?? ""}
                      onChange={(event) =>
                        setMapping((current) => ({ ...current, [role]: event.target.value || null }))
                      }
                    >
                      <option value="">Not mapped</option>
                      {columns.map((column) => (
                        <option key={column} value={column}>
                          {column}
                        </option>
                      ))}
                    </select>
                  </label>
                ))}
              </div>
              <div className="mt-4 flex flex-wrap items-center gap-3">
                <Button type="button" variant="outline" disabled={saveMapping.isPending} onClick={() => saveMapping.mutate()}>
                  Save roles
                </Button>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={dropDuplicates}
                    onChange={(event) => setDropDuplicates(event.target.checked)}
                  />
                  Remove exact duplicates from the cleaned copy
                </label>
                <Button
                  type="button"
                  disabled={prepare.isPending || Boolean(jobId) || detail.data.missing_roles.length > 0}
                  onClick={() => prepare.mutate()}
                >
                  {prepare.isPending || trackedJob.data?.job_type === "prepare" ? "Cleaning" : "Create cleaned version"}
                </Button>
              </div>
              {detail.data.cleaning?.rules ? (
                <ul className="mt-4 space-y-1 text-sm text-muted-foreground">
                  {detail.data.cleaning.rules.map((rule) => (
                    <li key={rule}>{rule}</li>
                  ))}
                </ul>
              ) : null}
            </section>
          ) : null}
          {datasetId ? (
            <section className="rounded-lg border bg-card p-4">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-sm font-medium">Preview</h2>
                <div className="flex gap-2">
                  <Button type="button" variant={stage === "raw" ? "default" : "outline"} size="sm" onClick={() => setStage("raw")}>
                    Original
                  </Button>
                  <Button
                    type="button"
                    variant={stage === "processed" ? "default" : "outline"}
                    size="sm"
                    disabled={!detail.data?.has_processed}
                    onClick={() => setStage("processed")}
                  >
                    Cleaned
                  </Button>
                </div>
              </div>
              {preview.isLoading ? <p className="mt-3 text-sm text-muted-foreground">Loading preview</p> : null}
              {preview.data ? (
                <div className="mt-3 overflow-x-auto">
                  <p className="mb-2 text-sm text-muted-foreground">{preview.data.total.toLocaleString()} rows</p>
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr>
                        {preview.data.columns.map((column) => (
                          <th key={column} className="border-b px-2 py-1 font-medium">
                            {column}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {preview.data.rows.map((row, index) => (
                        <tr key={index}>
                          {preview.data?.columns.map((column) => (
                            <td key={column} className="border-b px-2 py-1">
                              {row[column] == null ? "" : String(row[column])}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </section>
          ) : null}
        </div>
      </div>
    </div>
  )
}
