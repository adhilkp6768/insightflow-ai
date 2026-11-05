import { AuthField, AuthScreen, AuthSwitch, FormError, SubmitButton, useSubmitState } from "@/pages/auth-form"
import { useAuth } from "@/contexts/auth-context"
import { login } from "@/services/api"

export function LoginPage() {
  const { signIn } = useAuth()
  const { pending, error, submit } = useSubmitState()

  return (
    <AuthScreen title="Sign in" subtitle="Use your InsightFlow workspace account.">
      <form
        className="grid gap-4"
        onSubmit={(event) =>
          void submit(event, async (form) => {
            const session = await login({
              email: String(form.get("email") ?? ""),
              password: String(form.get("password") ?? ""),
            })
            signIn(session)
          })
        }
      >
        <FormError message={error} />
        <AuthField id="email" label="Email" type="email" autoComplete="email" />
        <AuthField id="password" label="Password" type="password" autoComplete="current-password" />
        <SubmitButton pending={pending} idle="Sign in" busy="Signing in" />
        <AuthSwitch prompt="No account yet?" to="/register" label="Create one" />
      </form>
    </AuthScreen>
  )
}
