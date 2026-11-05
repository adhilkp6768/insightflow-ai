import { type FormEvent, type ReactNode, useState } from "react"
import { Link } from "react-router-dom"

import { Logo } from "@/components/common/Logo"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { APP_TAGLINE } from "@/lib/constants"
import { formatApiError } from "@/services/api"

export function AuthScreen({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle: string
  children: ReactNode
}) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4 py-12">
      <div className="w-full max-w-[400px]">
        <Logo />
        <p className="mt-3 text-sm text-muted-foreground">{APP_TAGLINE}</p>
        <h1 className="mt-8 text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="mt-2 text-sm text-muted-foreground">{subtitle}</p>
        <div className="mt-8">{children}</div>
      </div>
    </main>
  )
}

export function FormError({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <p role="alert" className="rounded-md border border-destructive/30 px-3 py-2 text-sm text-destructive">
      {message}
    </p>
  )
}

export function useSubmitState() {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(event: FormEvent<HTMLFormElement>, action: (form: FormData) => Promise<void>) {
    event.preventDefault()
    setError(null)
    setPending(true)
    try {
      await action(new FormData(event.currentTarget))
    } catch (caught) {
      setError(formatApiError(caught))
    } finally {
      setPending(false)
    }
  }

  return { pending, error, submit }
}

export function AuthField({
  id,
  label,
  type,
  autoComplete,
  minLength,
}: {
  id: string
  label: string
  type: string
  autoComplete: string
  minLength?: number
}) {
  return (
    <label htmlFor={id} className="grid gap-2 text-sm font-medium">
      {label}
      <Input id={id} name={id} type={type} autoComplete={autoComplete} required minLength={minLength} />
    </label>
  )
}

export function AuthSwitch({ prompt, to, label }: { prompt: string; to: string; label: string }) {
  return (
    <p className="text-sm text-muted-foreground">
      {prompt}{" "}
      <Link to={to} className="font-medium text-foreground underline-offset-4 hover:underline">
        {label}
      </Link>
    </p>
  )
}

export function SubmitButton({ pending, idle, busy }: { pending: boolean; idle: string; busy: string }) {
  return (
    <Button type="submit" disabled={pending} className="w-full">
      {pending ? busy : idle}
    </Button>
  )
}
