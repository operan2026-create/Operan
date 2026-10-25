import { useState, useEffect, useMemo } from 'react'
import api from '../api/client'
import type { User, AuthResponse } from '../types'

export function useAuth() {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchCurrentUser = async () => {
    const token = localStorage.getItem('operan_token')
    if (token) {
      try {
        const res = await api.get<User>('/auth/me')
        setUser(res.data)
      } catch {
        localStorage.removeItem('operan_token')
        setUser(null)
      } finally {
        setLoading(false)
      }
    } else {
      setUser(null)
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchCurrentUser()
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

  const primaryRole = user?.primary_role || 'PARTICIPANT'
  const isAdmin = primaryRole === 'ADMIN'
  const isClient = primaryRole === 'CLIENT'
  const isParticipant = primaryRole === 'PARTICIPANT'

  return {
    user,
    loading,
    login,
    logout,
    primaryRole,
    isAdmin,
    isClient,
    isParticipant,
    refetchUser: fetchCurrentUser,
  }
}

