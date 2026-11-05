import { PageHeader } from "@/components/common/PageHeader"

export function ModuleStatus({
  title,
  description,
  points,
}: {
  title: string
  description: string
  points: string[]
}) {
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title={title} description={description} />
      <div className="rounded-lg border bg-card p-4">
        <h2 className="text-sm font-medium">Not available in this build</h2>
        <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-6 text-muted-foreground">
          {points.map((point) => (
            <li key={point}>{point}</li>
          ))}
        </ul>
      </div>
    </div>
  )
}
