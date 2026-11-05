import type { JobRecord } from "@/lib/jobs"

export function JobBanner({ job }: { job: JobRecord | null | undefined }) {
  if (!job || job.status === "succeeded" || job.status === "failed") return null
  return (
    <div className="mb-4 rounded-lg border border-primary/20 bg-primary/5 px-4 py-3" role="status">
      <p className="text-sm font-medium">Working in the background</p>
      <p className="mt-1 text-sm text-muted-foreground">{job.message || "This can take a few minutes for a large file."}</p>
    </div>
  )
}
