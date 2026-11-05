import { useQuery } from "@tanstack/react-query"
import { useEffect, useRef } from "react"

import { api } from "@/services/api"

export type JobRecord = {
  id: string
  workspace_id: string
  dataset_id: string | null
  job_type: string
  status: "queued" | "running" | "succeeded" | "failed"
  message: string | null
}

export function useJobWatcher(jobId: string | null, onDone: (job: JobRecord) => void) {
  const handled = useRef("")
  const callback = useRef(onDone)
  callback.current = onDone
  const query = useQuery({
    queryKey: ["job", jobId],
    queryFn: () => api<JobRecord>(`/api/v1/jobs/${jobId}`),
    enabled: Boolean(jobId),
    refetchInterval: (current) => {
      const status = current.state.data?.status
      if (!status || status === "succeeded" || status === "failed") return false
      return 1500
    },
  })
  useEffect(() => {
    const current = query.data
    if (!current || (current.status !== "succeeded" && current.status !== "failed")) return
    const token = `${current.id}:${current.status}`
    if (handled.current === token) return
    handled.current = token
    callback.current(current)
  }, [query.data])
  return query
}
