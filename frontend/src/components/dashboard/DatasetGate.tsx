import type { ReactNode } from "react"
import { Link } from "react-router-dom"

import { useWorkspace } from "@/contexts/workspace-context"
import { buttonVariants } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export function DatasetGate({ children }: { children: ReactNode }) {
  const { dataset, datasetsLoading } = useWorkspace()
  if (datasetsLoading) return <p className="text-sm text-muted-foreground">Loading datasets</p>
  if (!dataset) {
    return (
      <div className="rounded-lg border bg-card p-4 text-sm">
        <p>Choose a dataset in the header, or upload one in Data Management.</p>
        <Link to="/data" className={cn(buttonVariants({ variant: "outline", size: "sm" }), "mt-3")}>
          Data Management
        </Link>
      </div>
    )
  }
  if (!dataset.has_processed) {
    return (
      <div className="rounded-lg border bg-card p-4 text-sm">
        <p>
          {dataset.name} does not have a cleaned version yet. Analytics use that copy so the uploaded file stays
          unchanged.
        </p>
        <Link to="/data" className={cn(buttonVariants({ variant: "outline", size: "sm" }), "mt-3")}>
          Create cleaned version
        </Link>
      </div>
    )
  }
  return children
}
