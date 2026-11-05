import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react"
import { useNavigate } from "react-router-dom"

import { queryClient } from "@/lib/query-client"
import {
  clearSession,
  fetchCurrentUser,
  getAccessToken,
  getRefreshToken,
  refreshAccessToken,
  revokeSession,
  setSession,
  setSessionExpiredHandler,
} from "@/services/api"
import type { TokenResponse, User } from "@/types/api"

type AuthContextValue = {
  user: User | null
  loading: boolean
  signIn: (session: TokenResponse) => void
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate()
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setSessionExpiredHandler(() => {
      clearSession()
      setUser(null)
      queryClient.clear()
      navigate("/login", { replace: true })
    })
  }, [navigate])

  useEffect(() => {
    let active = true
    async function restore() {
      if (!getRefreshToken()) {
        if (active) setLoading(false)
        return
      }
      const access = await refreshAccessToken()
      if (!active) return
      if (!access) {
        setUser(null)
        setLoading(false)
        return
      }
      try {
        const current = await fetchCurrentUser()
        if (active) setUser(current)
      } catch {
        clearSession()
        if (active) setUser(null)
      } finally {
        if (active) setLoading(false)
      }
    }
    void restore()
    return () => {
      active = false
    }
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      signIn: (session) => {
        setSession(session.access_token, session.refresh_token)
        setUser(session.user)
        navigate("/")
      },
      signOut: async () => {
        const refresh = getRefreshToken()
        const access = getAccessToken()
        await revokeSession(access, refresh)
        clearSession()
        setUser(null)
        queryClient.clear()
        navigate("/login")
      },
    }),
    [loading, navigate, user],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error("useAuth must be used within AuthProvider")
  return context
}
