import { ArrowUp, Sparkles } from "lucide-react"
import { useState, type FormEvent } from "react"

import { BarBreakdown, TrendChart } from "@/components/dashboard/Charts"
import { DatasetGate } from "@/components/dashboard/DatasetGate"
import { PageHeader } from "@/components/common/PageHeader"
import { Button } from "@/components/ui/button"
import { useWorkspace } from "@/contexts/workspace-context"
import { periodParams } from "@/lib/period"
import { api, formatApiError } from "@/services/api"

type AssistantMessage = {
  id: string
  question: string
  answer_kind: "data_backed" | "prediction" | "interpretation" | "error"
  text: string
  chart: { type: string; x: string; y: string; y2?: string; data: Record<string, string | number | null>[] } | null
  limitations: string[]
}

const KIND_LABEL = {
  data_backed: "Data-backed",
  prediction: "Prediction",
  interpretation: "Interpretation",
  error: "Not answered",
}

const EXAMPLES = [
  "What is total revenue?",
  "How many orders are there?",
  "How many customers are there?",
  "What is the average order value?",
  "Which product has the highest revenue?",
  "Revenue by country",
  "Show monthly revenue",
  "What does the churn model say?",
]

export function AssistantPage() {
  const { dataset, datePreset } = useWorkspace()
  const params = periodParams(datePreset, dataset?.min_date ?? null, dataset?.max_date ?? null)
  const [question, setQuestion] = useState("")
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [messages, setMessages] = useState<AssistantMessage[]>([])
  const [pending, setPending] = useState(false)
  const [error, setError] = useState("")

  async function ask(event?: FormEvent, prompt?: string) {
    event?.preventDefault()
    const text = (prompt ?? question).trim()
    if (!dataset || !text) return
    setPending(true)
    setError("")
    try {
      const response = await api<{ conversation_id: string; message: AssistantMessage }>("/api/v1/assistant/messages", {
        method: "POST",
        body: {
          dataset_id: dataset.id,
          question: text,
          conversation_id: conversationId,
          date_from: params.date_from,
          date_to: params.date_to,
        },
      })
      setConversationId(response.conversation_id)
      setMessages((current) => [...current, response.message])
      setQuestion("")
    } catch (reason) {
      setError(formatApiError(reason))
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="mx-auto flex min-h-[calc(100vh-8rem)] max-w-4xl flex-col">
      <PageHeader
        title="AI Analytics Assistant"
        description="Questions are answered from the cleaned dataset or a saved model. Figures are calculated, not invented."
      />
      <DatasetGate>
        <div className="panel flex min-h-[32rem] flex-1 flex-col overflow-hidden">
          <div className="flex-1 space-y-4 overflow-y-auto p-4">
            {messages.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center px-6 py-16 text-center">
                <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/15 text-primary">
                  <Sparkles className="h-5 w-5" aria-hidden="true" />
                </span>
                <p className="text-sm font-medium">Ask about the cleaned dataset</p>
                <p className="mt-1 max-w-md text-sm text-muted-foreground">
                  Revenue, orders, products, regions, and saved predictions. A question outside that list is refused instead of guessed.
                </p>
              </div>
            ) : null}
            {messages.map((message) => (
              <div key={message.id} className="space-y-3">
                <div className="flex justify-end">
                  <p className="max-w-[80%] rounded-2xl rounded-br-md bg-primary px-4 py-2 text-sm text-primary-foreground">
                    {message.question}
                  </p>
                </div>
                <div className="max-w-[92%] rounded-2xl rounded-bl-md border bg-background/60 px-4 py-3">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{KIND_LABEL[message.answer_kind]}</p>
                  <p className="mt-1 text-sm leading-6">{message.text}</p>
                  {message.chart?.type === "line" ? (
                    <TrendChart data={message.chart.data} x={message.chart.x} y={message.chart.y} y2={message.chart.y2} height={220} />
                  ) : null}
                  {message.chart?.type === "bar" ? <BarBreakdown data={message.chart.data} x={message.chart.x} y={message.chart.y} /> : null}
                  {message.limitations.length ? (
                    <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
                      {message.limitations.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
          <div className="border-t p-3">
            <div className="mb-2 flex gap-2 overflow-x-auto pb-1">
              {EXAMPLES.map((example) => (
                <button
                  key={example}
                  type="button"
                  className="shrink-0 rounded-full border bg-card px-3 py-1 text-xs text-muted-foreground hover:border-primary hover:text-foreground disabled:opacity-50"
                  disabled={pending}
                  onClick={() => {
                    setQuestion(example)
                    void ask(undefined, example)
                  }}
                >
                  {example}
                </button>
              ))}
            </div>
            <form onSubmit={(event) => void ask(event)} className="flex items-center gap-2 rounded-full border bg-card px-2 py-1">
              <label className="sr-only" htmlFor="question">
                Question
              </label>
              <input
                id="question"
                className="h-9 flex-1 bg-transparent px-2 text-sm outline-none"
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="Type a question about this dataset"
              />
              <Button type="submit" size="icon" className="rounded-full" disabled={pending || !question.trim()} aria-label="Ask">
                <ArrowUp className="h-4 w-4" />
              </Button>
            </form>
            {error ? <p className="mt-2 text-sm text-destructive">{error}</p> : null}
          </div>
        </div>
      </DatasetGate>
    </div>
  )
}
