import { useQuery } from "@tanstack/react-query"
import { Bell, Menu, Moon, Sun, UserRound } from "lucide-react"
import { useState } from "react"
import { Outlet } from "react-router-dom"

import { Logo } from "@/components/common/Logo"
import { SidebarNav } from "@/components/layout/SidebarNav"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useAuth } from "@/contexts/auth-context"
import { useTheme } from "@/contexts/theme-context"
import { DATE_PRESETS, useWorkspace } from "@/contexts/workspace-context"
import { api, formatApiError } from "@/services/api"
import type { NotificationItem } from "@/types/api"

export function AppShell() {
  const { user, signOut } = useAuth()
  const { theme, setTheme } = useTheme()
  const {
    workspaces,
    workspaceId,
    setWorkspaceId,
    datePreset,
    setDatePreset,
    datasets,
    datasetId,
    setDatasetId,
    isLoading,
    isError,
    error,
    refetch,
  } = useWorkspace()
  const notifications = useQuery({
    queryKey: ["notifications", workspaceId],
    queryFn: () => api<NotificationItem[]>(`/api/v1/workspaces/${workspaceId}/notifications`),
    enabled: Boolean(workspaceId),
  })
  const [navOpen, setNavOpen] = useState(false)
  const [signingOut, setSigningOut] = useState(false)
  const nextTheme = theme === "dark" ? "light" : "dark"

  return (
    <div className="flex min-h-screen bg-background">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-card focus:px-3 focus:py-2 focus:shadow-sm"
      >
        Skip to content
      </a>
      <aside className="hidden w-60 shrink-0 border-r border-sidebar-border bg-sidebar md:flex md:flex-col">
        <div className="px-4 py-4">
          <Logo />
        </div>
        <div className="min-h-0 flex-1 px-3 pb-4">
          <SidebarNav />
        </div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex min-h-16 flex-wrap items-center gap-2 border-b bg-background/80 px-4 py-2 backdrop-blur">
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            aria-label="Open navigation"
            onClick={() => setNavOpen(true)}
          >
            <Menu className="h-4 w-4" />
          </Button>
          <label className="min-w-0">
            <span className="sr-only">Workspace</span>
            <select
              aria-label="Workspace"
              className="control max-w-[14rem]"
              value={workspaceId}
              disabled={isLoading || workspaces.length === 0}
              onChange={(event) => setWorkspaceId(event.target.value)}
            >
              {workspaces.length === 0 ? <option value="">{isLoading ? "Loading" : "No workspace"}</option> : null}
              {workspaces.map((workspace) => (
                <option key={workspace.id} value={workspace.id}>
                  {workspace.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="sr-only">Reporting period</span>
            <select
              aria-label="Reporting period"
              className="control"
              value={datePreset}
              onChange={(event) => setDatePreset(event.target.value as typeof datePreset)}
            >
              {DATE_PRESETS.map((preset) => (
                <option key={preset.value} value={preset.value}>
                  {preset.label}
                </option>
              ))}
            </select>
          </label>
          <div className="ml-auto flex items-center gap-1">
            <label>
              <span className="sr-only">Dataset</span>
              <select
                aria-label="Dataset"
                className="control max-w-52"
                value={datasetId}
                onChange={(event) => setDatasetId(event.target.value)}
              >
                <option value="">No dataset</option>
                {datasets.map((dataset) => (
                  <option key={dataset.id} value={dataset.id}>
                    {dataset.name}
                  </option>
                ))}
              </select>
            </label>
            <Button
              variant="ghost"
              size="icon"
              aria-label={nextTheme === "dark" ? "Switch to dark theme" : "Switch to light theme"}
              onClick={() => setTheme(nextTheme)}
            >
              {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" aria-label="Notifications">
                  <Bell className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel className="font-medium">Notifications</DropdownMenuLabel>
                {notifications.data?.length ? (
                  <ul className="max-w-72 px-2 py-1 text-sm">
                    {notifications.data.map((item) => (
                      <li key={item.id} className="border-t py-2 first:border-t-0">
                        {item.message}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="px-2 py-3 text-sm text-muted-foreground">No notifications</p>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" aria-label="Account menu">
                  <UserRound className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>
                  <span className="block font-medium">{user?.full_name}</span>
                  <span className="block text-muted-foreground">{user?.email}</span>
                </DropdownMenuLabel>
                <DropdownMenuItem
                  disabled={signingOut}
                  onSelect={() => {
                    setSigningOut(true)
                    void signOut()
                  }}
                >
                  Log out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>
        <main id="main" tabIndex={-1} className="flex-1 px-4 py-6 outline-none md:px-6">
          {isError ? (
            <div
              role="alert"
              className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-md border border-destructive/30 px-3 py-2 text-sm"
            >
              <p>{formatApiError(error)}</p>
              <Button variant="outline" size="sm" onClick={refetch}>
                Try again
              </Button>
            </div>
          ) : null}
          <Outlet />
        </main>
      </div>
      <Dialog open={navOpen} onOpenChange={setNavOpen}>
        <DialogContent aria-describedby={undefined}>
          <DialogTitle className="sr-only">Navigation</DialogTitle>
          <div className="mb-4">
            <Logo />
          </div>
          <SidebarNav onNavigate={() => setNavOpen(false)} />
        </DialogContent>
      </Dialog>
    </div>
  )
}
