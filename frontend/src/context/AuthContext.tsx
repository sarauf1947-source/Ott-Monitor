// frontend/src/context/AuthContext.tsx
import {
  createContext, useContext, useState, useEffect,
  useCallback, type ReactNode,
} from 'react'
import axios from 'axios'

// Types
export interface UserResponse {
  id:         number
  username:   string
  email:      string
  full_name:  string | null
  role:       'admin' | 'operator' | 'viewer'
  is_active:  boolean
  created_at: string
  last_login: string | null
}

interface AuthCtx {
  user:       UserResponse | null
  loading:    boolean
  signIn:     (username: string, password: string) => Promise<void>
  signOut:    () => void
  isAdmin:    boolean
  isOperator: boolean
}

const Ctx = createContext<AuthCtx | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user,    setUser]    = useState<UserResponse | null>(null)
  const [loading, setLoading] = useState(true)

  // Restore session on mount
  useEffect(() => {
    const stored = localStorage.getItem('ott_user')
    const token  = localStorage.getItem('access_token')
    if (stored && token) {
      try { setUser(JSON.parse(stored)) } catch { /* ignore */ }
    }
    setLoading(false)
  }, [])

  // Auto refresh token every 25 minutes
  useEffect(() => {
    const id = setInterval(async () => {
      const refresh = localStorage.getItem('refresh_token')
      if (!refresh) return
      try {
        const res = await axios.post<{ access_token: string }>(
          '/api/v1/auth/refresh',
          { refresh_token: refresh }
        )
        localStorage.setItem('access_token', res.data.access_token)
      } catch {
        signOut()
      }
    }, 25 * 60 * 1000)
    return () => clearInterval(id)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const signIn = useCallback(async (username: string, password: string) => {
    const res = await axios.post<{
      access_token: string
      refresh_token: string
      user: UserResponse
    }>('/api/v1/auth/login', { username, password })
    localStorage.setItem('access_token',  res.data.access_token)
    localStorage.setItem('refresh_token', res.data.refresh_token)
    localStorage.setItem('ott_user',      JSON.stringify(res.data.user))
    setUser(res.data.user)
  }, [])

  const signOut = useCallback(() => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('ott_user')
    setUser(null)
  }, [])

  return (
    <Ctx.Provider value={{
      user, loading, signIn, signOut,
      isAdmin:    user?.role === 'admin',
      isOperator: user?.role === 'admin' || user?.role === 'operator',
    }}>
      {children}
    </Ctx.Provider>
  )
}

export function useAuth(): AuthCtx {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
