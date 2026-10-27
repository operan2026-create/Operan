import type { User } from '../types'

export function homePathForUser(user: Pick<User, 'primary_role'> | null | undefined): string {
  if (!user) return '/login'
  if (user.primary_role === 'ADMIN') return '/admin'
  if (user.primary_role === 'CLIENT') return '/cliente'
  if (user.primary_role === 'PARTICIPANT') return '/participante'
  return '/sem-acesso'
}
