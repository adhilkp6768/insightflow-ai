import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useState, type FormEvent } from "react"

import { PageHeader } from "@/components/common/PageHeader"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useAuth } from "@/contexts/auth-context"
import { useTheme } from "@/contexts/theme-context"
import { useWorkspace } from "@/contexts/workspace-context"
import { api, fetchCurrentUser, formatApiError } from "@/services/api"

type Member = {
  user_id: string
  email: string
  full_name: string
  role: string
  created_at: string
}

type Invite = {
  id: string
  email: string
  role: string
  status: string
}

type Directory = {
  members: Member[]
  invites: Invite[]
}

const ROLES = ["owner", "admin", "analyst", "viewer"] as const

export function SettingsPage() {
  const queryClient = useQueryClient()
  const { user, signOut } = useAuth()
  const { theme, setTheme } = useTheme()
  const { workspace, workspaceId } = useWorkspace()
  const [email, setEmail] = useState("")
  const [role, setRole] = useState("analyst")
  const [notice, setNotice] = useState("")
  const [error, setError] = useState("")
  const profile = useQuery({ queryKey: ["me"], queryFn: fetchCurrentUser })
  const directory = useQuery({
    queryKey: ["members", workspaceId],
    queryFn: () => api<Directory>(`/api/v1/workspaces/${workspaceId}/members`),
    enabled: Boolean(workspaceId),
  })
  const canManage = workspace?.role === "owner" || workspace?.role === "admin"

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: ["members", workspaceId] })
    void queryClient.invalidateQueries({ queryKey: ["workspaces"] })
    void queryClient.invalidateQueries({ queryKey: ["notifications", workspaceId] })
  }

  const invite = useMutation({
    mutationFn: () =>
      api<Directory>(`/api/v1/workspaces/${workspaceId}/members`, {
        method: "POST",
        body: { email, role },
      }),
    onSuccess: () => {
      setEmail("")
      setNotice("Invitation saved. An existing account is added immediately. A new account joins when they register with that email.")
      setError("")
      refresh()
    },
    onError: (reason) => setError(formatApiError(reason)),
  })

  const changeRole = useMutation({
    mutationFn: (payload: { userId: string; role: string }) =>
      api<Directory>(`/api/v1/workspaces/${workspaceId}/members/${payload.userId}`, {
        method: "PATCH",
        body: { role: payload.role },
      }),
    onSuccess: () => {
      setNotice("Role updated.")
      setError("")
      refresh()
    },
    onError: (reason) => setError(formatApiError(reason)),
  })

  const remove = useMutation({
    mutationFn: (userId: string) => api<Directory>(`/api/v1/workspaces/${workspaceId}/members/${userId}`, { method: "DELETE" }),
    onSuccess: () => {
      setNotice("Member removed.")
      setError("")
      refresh()
    },
    onError: (reason) => setError(formatApiError(reason)),
  })

  const revoke = useMutation({
    mutationFn: (inviteId: string) =>
      api<Directory>(`/api/v1/workspaces/${workspaceId}/invites/${inviteId}`, { method: "DELETE" }),
    onSuccess: () => {
      setNotice("Invitation revoked.")
      setError("")
      refresh()
    },
    onError: (reason) => setError(formatApiError(reason)),
  })

  function onInvite(event: FormEvent) {
    event.preventDefault()
    invite.mutate()
  }

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="Settings" description="Account, appearance, and who can use this workspace." />
      {notice ? <p className="mb-4 rounded-lg border bg-card px-4 py-3 text-sm">{notice}</p> : null}
      {error ? <p className="mb-4 text-sm text-destructive">{error}</p> : null}
      <section className="rounded-lg border bg-card p-4">
        <h2 className="text-sm font-medium">Profile</h2>
        {profile.isLoading ? <p className="mt-3 text-sm text-muted-foreground">Loading profile</p> : null}
        {profile.isError ? (
          <p role="alert" className="mt-3 text-sm text-destructive">
            {formatApiError(profile.error)}
          </p>
        ) : null}
        {profile.data ? (
          <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-muted-foreground">Name</dt>
              <dd className="mt-1 font-medium">{profile.data.full_name}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Email</dt>
              <dd className="mt-1 font-medium">{profile.data.email}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Workspace role</dt>
              <dd className="mt-1 font-medium capitalize">{workspace?.role ?? "Unavailable"}</dd>
            </div>
          </dl>
        ) : null}
      </section>
      <section className="mt-4 rounded-lg border bg-card p-4">
        <h2 className="text-sm font-medium">Members</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Viewers can read. Analysts can upload, clean, train, and export. Admins can also invite people.
        </p>
        {directory.isLoading ? <p className="mt-3 text-sm text-muted-foreground">Loading members</p> : null}
        {directory.isError ? <p className="mt-3 text-sm text-destructive">{formatApiError(directory.error)}</p> : null}
        <ul className="mt-3 divide-y">
          {directory.data?.members.map((member) => {
            const manageable =
              canManage &&
              member.user_id !== user?.id &&
              (workspace?.role === "owner" || (member.role !== "owner" && member.role !== "admin"))
            return (
              <li key={member.user_id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                <div>
                  <p className="text-sm font-medium">{member.full_name}</p>
                  <p className="text-sm text-muted-foreground">{member.email}</p>
                </div>
                {manageable ? (
                  <div className="flex items-center gap-2">
                    <label className="sr-only" htmlFor={`role-${member.user_id}`}>
                      Role for {member.full_name}
                    </label>
                    <select
                      id={`role-${member.user_id}`}
                      className="h-9 rounded-md border border-input bg-card px-2 text-sm"
                      value={member.role}
                      onChange={(event) => changeRole.mutate({ userId: member.user_id, role: event.target.value })}
                    >
                      {ROLES.filter((item) => workspace?.role === "owner" || (item !== "owner" && item !== "admin")).map(
                        (item) => (
                          <option key={item} value={item}>
                            {item}
                          </option>
                        ),
                      )}
                    </select>
                    <Button type="button" variant="outline" size="sm" onClick={() => remove.mutate(member.user_id)}>
                      Remove
                    </Button>
                  </div>
                ) : (
                  <span className="text-sm capitalize text-muted-foreground">{member.role}</span>
                )}
              </li>
            )
          })}
        </ul>
        {directory.data?.invites.length ? (
          <div className="mt-2">
            <h3 className="text-sm font-medium">Pending invitations</h3>
            <ul className="mt-2 space-y-2">
              {directory.data.invites.map((item) => (
                <li key={item.id} className="flex items-center justify-between gap-3 text-sm">
                  <span>
                    {item.email} · <span className="capitalize">{item.role}</span>
                  </span>
                  {canManage ? (
                    <Button type="button" variant="outline" size="sm" onClick={() => revoke.mutate(item.id)}>
                      Revoke
                    </Button>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {canManage ? (
          <form onSubmit={onInvite} className="mt-4 grid gap-3 border-t pt-4 sm:grid-cols-[1fr_9rem_auto]">
            <label className="text-sm">
              Email
              <Input
                className="mt-1"
                type="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                aria-label="Invite email"
              />
            </label>
            <label className="text-sm">
              Role
              <select
                aria-label="Invite role"
                className="mt-1 h-9 w-full rounded-md border border-input bg-card px-2 text-sm"
                value={role}
                onChange={(event) => setRole(event.target.value)}
              >
                {workspace?.role === "owner" ? <option value="admin">admin</option> : null}
                <option value="analyst">analyst</option>
                <option value="viewer">viewer</option>
              </select>
            </label>
            <Button className="self-end" type="submit" disabled={invite.isPending || !email.trim()}>
              {invite.isPending ? "Saving" : "Invite"}
            </Button>
          </form>
        ) : (
          <p className="mt-3 text-sm text-muted-foreground">Ask an owner or admin to invite someone.</p>
        )}
      </section>
      <section className="mt-4 rounded-lg border bg-card p-4">
        <h2 className="text-sm font-medium">Appearance</h2>
        <div className="mt-3 flex gap-2" role="group" aria-label="Theme">
          <Button variant={theme === "light" ? "default" : "outline"} aria-pressed={theme === "light"} onClick={() => setTheme("light")}>
            Light
          </Button>
          <Button variant={theme === "dark" ? "default" : "outline"} aria-pressed={theme === "dark"} onClick={() => setTheme("dark")}>
            Dark
          </Button>
        </div>
      </section>
      <section className="mt-4 rounded-lg border bg-card p-4">
        <h2 className="text-sm font-medium">Session</h2>
        <p className="mt-2 text-sm text-muted-foreground">Log out of this browser session.</p>
        <Button className="mt-3" variant="outline" onClick={() => void signOut()}>
          Log out
        </Button>
      </section>
    </div>
  )
}
