import { Link } from "react-router-dom"

import { buttonVariants } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export function NotFoundPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="max-w-md">
        <h1 className="text-2xl font-semibold tracking-tight">Page not found</h1>
        <p className="mt-2 text-sm text-muted-foreground">That address is not part of InsightFlow.</p>
        <Link to="/" className={cn(buttonVariants(), "mt-6")}>
          Back to overview
        </Link>
      </div>
    </main>
  )
}
