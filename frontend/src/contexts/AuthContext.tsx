import { createContext, useContext, useState, useEffect } from 'react'
import type { ReactNode } from 'react'
import api from '../lib/api'

interface User {
  id: string
  username: string
  is_admin: boolean
}

interface AuthContextType {
  token: string | null
  user: User | null
  login: (username: string, password: string) => Promise<void>
  register: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextType>(null!)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'))
  const [user, setUser] = useState<User | null>(null)

  useEffect(() => {
    if (token) {
      api.get('/auth/me').then(res => setUser(res.data)).catch(() => {
        setToken(null)
        localStorage.removeItem('token')
      })
    }
  }, [token])

  const login = async (username: string, password: string) => {
    const res = await api.post('/auth/login', { username, password })
    const t = res.data.access_token
    localStorage.setItem('token', t)
    setToken(t)
  }

  const register = async (username: string, password: string) => {
    await api.post('/auth/register', { username, password })
    await login(username, password)
  }

  const logout = () => {
    localStorage.removeItem('token')
    setToken(null)
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ token, user, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
