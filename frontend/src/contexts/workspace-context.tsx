import { useQuery } from "@tanstack/react-query"
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react"

import { useAuth } from "@/contexts/auth-context"
import { api } from "@/services/api"
import type { DatasetSummary, DatePreset, Workspace } from "@/types/api"

const WORKSPACE_KEY = "insightflow-workspace-id"
const DATE_KEY = "insightflow-date-range"
const DATASET_KEY = "insightflow-dataset-id"

export const DATE_PRESETS: { value: DatePreset; label: string }[] = [
  { value: "30d", label: "Last 30 days" },
  { value: "90d", label: "Last 90 days" },
  { value: "12m", label: "Last 12 months" },
  { value: "all", label: "All dates" },
]

function storedDatePreset(): DatePreset {
  const value = localStorage.getItem(DATE_KEY)
  return DATE_PRESETS.some((item) => item.value === value) ? (value as DatePreset) : "30d"
}

type WorkspaceContextValue = {
  workspaces: Workspace[]
  workspace: Workspace | null
  workspaceId: string
  setWorkspaceId: (id: string) => void
  datasets: DatasetSummary[]
  dataset: DatasetSummary | null
  datasetId: string
  setDatasetId: (id: string) => void
  datasetsLoading: boolean
  datePreset: DatePreset
  dateLabel: string
  setDatePreset: (preset: DatePreset) => void
  isLoading: boolean
  isError: boolean
  error: unknown
  refetch: () => void
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null)

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const [workspaceId, setWorkspaceIdState] = useState(() => localStorage.getItem(WORKSPACE_KEY) ?? "")
  const [datasetId, setDatasetIdState] = useState(() => localStorage.getItem(DATASET_KEY) ?? "")
  const [datePreset, setDatePresetState] = useState<DatePreset>(storedDatePreset)

  const query = useQuery({
    queryKey: ["workspaces", user?.id],
    queryFn: () => api<Workspace[]>("/api/v1/workspaces"),
    enabled: Boolean(user),
  })
  const datasetsQuery = useQuery({
    queryKey: ["datasets", workspaceId],
    queryFn: () => api<DatasetSummary[]>(`/api/v1/workspaces/${workspaceId}/datasets`),
    enabled: Boolean(user && workspaceId),
  })

  useEffect(() => {
    const workspaces = query.data
    if (!workspaces?.length) return
    setWorkspaceIdState((current) => {
      if (current && workspaces.some((item) => item.id === current)) return current
      return workspaces[0].id
    })
  }, [query.data])

  useEffect(() => {
    if (workspaceId) localStorage.setItem(WORKSPACE_KEY, workspaceId)
  }, [workspaceId])

  useEffect(() => {
    const datasets = datasetsQuery.data
    if (!datasets) return
    setDatasetIdState((current) => {
      if (current && datasets.some((item) => item.id === current)) return current
      return datasets[0]?.id ?? ""
    })
  }, [datasetsQuery.data])

  useEffect(() => {
    localStorage.setItem(DATASET_KEY, datasetId)
  }, [datasetId])

  const value = useMemo<WorkspaceContextValue>(() => {
    const workspaces = query.data ?? []
    const datasets = datasetsQuery.data ?? []
    const dateLabel = DATE_PRESETS.find((item) => item.value === datePreset)?.label ?? "Last 30 days"
    return {
      workspaces,
      workspace: workspaces.find((item) => item.id === workspaceId) ?? null,
      workspaceId,
      setWorkspaceId: setWorkspaceIdState,
      datasets,
      dataset: datasets.find((item) => item.id === datasetId) ?? null,
      datasetId,
      setDatasetId: setDatasetIdState,
      datasetsLoading: datasetsQuery.isLoading,
      datePreset,
      dateLabel,
      setDatePreset: (preset) => {
        setDatePresetState(preset)
        localStorage.setItem(DATE_KEY, preset)
      },
      isLoading: query.isLoading,
      isError: query.isError || datasetsQuery.isError,
      error: query.error ?? datasetsQuery.error,
      refetch: () => {
        void query.refetch()
        void datasetsQuery.refetch()
      },
    }
  }, [datasetId, datasetsQuery, datePreset, query, workspaceId])

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>
}

export function useWorkspace() {
  const context = useContext(WorkspaceContext)
  if (!context) throw new Error("useWorkspace must be used within WorkspaceProvider")
  return context
}
