import { useState, useEffect } from 'react'
import api from '../api/client'
import type { User, AuthResponse } from '../types'

export function useAuth() {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('operan_token')
    if (token) {
      api.get('/auth/me')
        .then(res => setUser(res.data))
        .catch(() => setUser(null))
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [])

  const login = async (email: string, password: string): Promise<AuthResponse> => {
    const res = await api.post<AuthResponse>('/auth/login', { email, password })
    localStorage.setItem('operan_token', res.data.access_token)
    setUser(res.data.user)
    return res.data
  }

  const logout = () => {
    localStorage.removeItem('operan_token')
    setUser(null)
    window.location.href = '/login'
  }

  return { user, loading, login, logout }
}
