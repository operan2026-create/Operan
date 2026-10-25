import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Building2, Plus, Search } from 'lucide-react'
import api from '../api/client'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import type { Organization } from '../types'

const statusColors: Record<string, string> = {
  ACTIVE: 'text-green-400 bg-green-400/10 border-green-400/20',
  INACTIVE: 'text-gray-400 bg-gray-400/10 border-gray-400/20',
  SUSPENDED: 'text-red-400 bg-red-400/10 border-red-400/20',
}

const statusLabels: Record<string, string> = {
  ACTIVE: 'Ativa',
  INACTIVE: 'Inativa',
  SUSPENDED: 'Suspensa',
}

export function OrganizationsPage() {
  const [search, setSearch] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['organizations'],
    queryFn: () => api.get<Organization[]>('/organizations').then((r) => r.data),
  })

  const filtered =
    data?.filter((o) => o.name.toLowerCase().includes(search.toLowerCase())) ?? []

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white">Organizadoras</h1>
          <p className="text-gray-400 mt-1">Gerencie os clientes da plataforma</p>
        </div>
        <Button>
          <Plus className="w-4 h-4 mr-2" /> Nova Organizadora
        </Button>
      </div>

      <Card className="mb-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input
            className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-10 pr-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-violet-500"
            placeholder="Buscar organizadoras..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </Card>

      <Card>
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin w-6 h-6 border-2 border-violet-600 border-t-transparent rounded-full" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <Building2 className="w-10 h-10 text-gray-700 mb-3" />
            <p className="text-gray-400 font-medium">Nenhuma organizadora encontrada</p>
            <p className="text-gray-600 text-sm mt-1">Crie a primeira organizadora para começar</p>
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-800">
                <th className="text-left text-gray-400 text-sm font-medium pb-3">ID</th>
                <th className="text-left text-gray-400 text-sm font-medium pb-3">Nome</th>
                <th className="text-left text-gray-400 text-sm font-medium pb-3">Status</th>
                <th className="text-left text-gray-400 text-sm font-medium pb-3">Criado em</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800">
              {filtered.map((org) => (
                <tr key={org.id} className="hover:bg-gray-800/50 transition-colors">
                  <td className="py-3 text-violet-400 font-mono text-sm">{org.public_id}</td>
                  <td className="py-3 text-white font-medium">{org.name}</td>
                  <td className="py-3">
                    <span
                      className={`text-xs font-medium px-2 py-1 rounded-full border ${statusColors[org.status]}`}
                    >
                      {statusLabels[org.status]}
                    </span>
                  </td>
                  <td className="py-3 text-gray-400 text-sm">
                    {new Date(org.created_at).toLocaleDateString('pt-BR')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  )
}
