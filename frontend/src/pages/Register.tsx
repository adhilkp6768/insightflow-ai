import { useAuth } from "@/contexts/auth-context"
import { AuthField, AuthScreen, AuthSwitch, FormError, SubmitButton, useSubmitState } from "@/pages/auth-form"
import { register } from "@/services/api"

export function RegisterPage() {
  const { signIn } = useAuth()
  const { pending, error, submit } = useSubmitState()

  return (
    <AuthScreen title="Create account" subtitle="This creates your user and a private workspace.">
      <form
        className="grid gap-4"
        onSubmit={(event) =>
          void submit(event, async (form) => {
            const session = await register({
              full_name: String(form.get("full_name") ?? ""),
              email: String(form.get("email") ?? ""),
              password: String(form.get("password") ?? ""),
            })
            signIn(session)
          })
        }
      >
        <FormError message={error} />
        <AuthField id="full_name" label="Full name" type="text" autoComplete="name" />
        <AuthField id="email" label="Email" type="email" autoComplete="email" />
        <AuthField id="password" label="Password" type="password" autoComplete="new-password" minLength={8} />
        <p className="text-sm text-muted-foreground">Use at least 8 characters.</p>
        <SubmitButton pending={pending} idle="Create account" busy="Creating account" />
        <AuthSwitch prompt="Already have an account?" to="/login" label="Sign in" />
      </form>
    </AuthScreen>
  )
}
