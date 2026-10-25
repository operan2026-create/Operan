import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Users, Search, ShieldCheck, MapPin, Phone, Lock, Award, CheckCircle2 } from 'lucide-react'
import api from '../api/client'
import { Card } from '../components/ui/Card'
import type { Professional } from '../types'

export function NetworkPage() {
  const [search, setSearch] = useState('')

  const { data: professionals, isLoading } = useQuery({
    queryKey: ['professionals'],
    queryFn: () => api.get<Professional[]>('/professionals').then(r => r.data),
  })

  const filtered = professionals?.filter(p =>
    p.full_name.toLowerCase().includes(search.toLowerCase()) ||
    p.city.toLowerCase().includes(search.toLowerCase())
  ) || []

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <Users className="w-7 h-7 text-violet-400" />
            Rede de Profissionais & Colaboradores
          </h1>
          <p className="text-gray-400 mt-1">
            Colaboradores cadastrados via link público, com dados criptografados e pontuação no Passaporte Operacional
          </p>
        </div>
      </div>

      <Card className="mb-6">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input
            className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-10 pr-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-violet-500 text-sm"
            placeholder="Buscar colaboradores por nome ou cidade..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
      </Card>

      <Card>
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <div className="animate-spin w-8 h-8 border-2 border-violet-600 border-t-transparent rounded-full" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <Users className="w-12 h-12 text-gray-700 mb-3" />
            <p className="text-gray-400 font-semibold">Nenhum colaborador registrado ainda</p>
            <p className="text-gray-600 text-xs mt-1 max-w-sm">
              Envie o link público de cadastro (<strong>/cadastro-colaborador</strong>) para fiscais e coordenadores para que eles entrem na rede e façam os cursos da Academy.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-800 text-left text-xs font-semibold text-gray-400">
                  <th className="pb-3">Nome / Profissional</th>
                  <th className="pb-3">Localidade / Raio</th>
                  <th className="pb-3">Proteção de Dados</th>
                  <th className="pb-3">Disponibilidade</th>
                  <th className="pb-3">Score Reputação</th>
                  <th className="pb-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/60 text-sm">
                {filtered.map(p => (
                  <tr key={p.id} className="hover:bg-gray-800/40 transition-colors">
                    <td className="py-3.5">
                      <div className="font-bold text-white">{p.full_name}</div>
                      <div className="text-xs text-gray-500 font-mono">ID: {p.user_id.substring(0, 8)}...</div>
                    </td>
                    <td className="py-3.5">
                      <div className="text-gray-300 flex items-center gap-1">
                        <MapPin className="w-3 h-3 text-violet-400" />
                        {p.city}/{p.state}
                      </div>
                      <div className="text-xs text-gray-500">Raio: {p.radius_km} km</div>
                    </td>
                    <td className="py-3.5">
                      <span className="text-xs text-green-400 bg-green-500/10 border border-green-500/20 px-2 py-0.5 rounded-full inline-flex items-center gap-1">
                        <Lock className="w-3 h-3" />
                        CPF & Telefone AES-256
                      </span>
                    </td>
                    <td className="py-3.5">
                      <span className="text-xs font-semibold text-green-400 flex items-center gap-1">
                        <span className="w-1.5 h-1.5 bg-green-400 rounded-full" />
                        Disponível p/ Operações
                      </span>
                    </td>
                    <td className="py-3.5">
                      <span className="font-bold text-violet-400">100%</span>
                    </td>
                    <td className="py-3.5">
                      <span className="text-xs font-bold bg-violet-600/20 text-violet-300 border border-violet-600/30 px-2 py-0.5 rounded-full">
                        Ativo na Rede
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
