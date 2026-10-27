import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, ShieldCheck, MapPin, Lock, Award, Users } from 'lucide-react'
import api from '../api/client'
import { Card } from '../components/ui/Card'
import { PROFESSIONAL_FUNCTIONS, professionalFunctionLabel } from '../lib/professionalFunctions'
import type { Professional } from '../types'

export function NetworkPage() {
  const [search, setSearch] = useState('')
  const [stateFilter, setStateFilter] = useState('')
  const [cityFilter, setCityFilter] = useState('')
  const [functionFilter, setFunctionFilter] = useState('')

  const { data: professionals, isLoading } = useQuery({
    queryKey: ['professionals', stateFilter, cityFilter, functionFilter],
    queryFn: () =>
      api
        .get<Professional[]>('/professionals', {
          params: {
            state: stateFilter || undefined,
            city: cityFilter || undefined,
            function: functionFilter || undefined,
          },
        })
        .then(r => r.data),
  })

  const filtered = professionals?.filter(p => {
    const term = search.toLowerCase()
    return (
      p.full_name.toLowerCase().includes(term) ||
      p.city.toLowerCase().includes(term) ||
      (p.qualifications || []).some(q => professionalFunctionLabel(q).toLowerCase().includes(term))
    )
  }) || []

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <Users className="w-7 h-7 text-violet-400" />
            Rede de Profissionais & Colaboradores
          </h1>
          <p className="text-gray-400 mt-1">
            Profissionais com jornada ativa, dados protegidos e pontuacao no Passaporte Operacional
          </p>
        </div>
      </div>

      <Card className="mb-6">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div className="relative lg:col-span-2">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input
              className="w-full bg-gray-800 border border-gray-700 rounded-lg pl-10 pr-4 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-violet-500 text-sm"
              placeholder="Buscar por nome, cidade ou certificacao..."
              value={search}
              onChange={e => setSearch(e.target.value)}
            />
          </div>
          <input
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-violet-500 text-sm"
            placeholder="UF (ex: SP)"
            maxLength={2}
            value={stateFilter}
            onChange={e => setStateFilter(e.target.value.toUpperCase())}
          />
          <input
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-violet-500 text-sm"
            placeholder="Cidade"
            value={cityFilter}
            onChange={e => setCityFilter(e.target.value)}
          />
          <select
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-violet-500 text-sm lg:col-span-2"
            value={functionFilter}
            onChange={e => setFunctionFilter(e.target.value)}
          >
            <option value="">Todas as certificacoes/funcoes</option>
            {PROFESSIONAL_FUNCTIONS.map(fn => (
              <option key={fn.value} value={fn.value}>{fn.label}</option>
            ))}
          </select>
          <div className="text-xs text-gray-500 self-center lg:col-span-2">
            {filtered.length} profissional(is) encontrado(s) na base nacional.
          </div>
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
              A entrada na rede ocorre por convite. Emita um convite da jornada de profissionais para que o colaborador aceite e ative a jornada.
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
                      <div className="text-xs text-gray-500">
                        Raio: {p.operational_radius_km ?? p.radius_km ?? '-'} km
                      </div>
                    </td>
                    <td className="py-3.5">
                      <div className="flex flex-wrap gap-1 max-w-56">
                        {(p.qualifications || []).length === 0 ? (
                          <span className="text-xs text-gray-600">Sem certificacao ativa</span>
                        ) : (
                          (p.qualifications || []).map(q => (
                            <span
                              key={q}
                              className="text-[10px] text-violet-300 bg-violet-500/10 border border-violet-500/20 px-2 py-0.5 rounded-full inline-flex items-center gap-1"
                            >
                              <Award className="w-3 h-3" />
                              {professionalFunctionLabel(q)}
                            </span>
                          ))
                        )}
                      </div>
                    </td>
                    <td className="py-3.5">
                      <span className="text-xs text-green-400 bg-green-500/10 border border-green-500/20 px-2 py-0.5 rounded-full inline-flex items-center gap-1">
                        <Lock className="w-3 h-3" />
                        Dados protegidos
                      </span>
                    </td>
                    <td className="py-3.5">
                      <span className={`text-xs font-semibold flex items-center gap-1 ${
                        p.availability_status === 'AVAILABLE' ? 'text-green-400' :
                        p.availability_status === 'IN_MISSION' ? 'text-yellow-400' : 'text-gray-400'
                      }`}>
                        <span className="w-1.5 h-1.5 rounded-full bg-current" />
                        {p.availability_status === 'AVAILABLE' ? 'Disponível' :
                         p.availability_status === 'IN_MISSION' ? 'Em missão' : 'Indisponível'}
                      </span>
                    </td>
                    <td className="py-3.5">
                      <span className="font-bold text-violet-400">
                        {p.reputation_score !== undefined ? `${p.reputation_score.toFixed(1)}%` : '-'}
                      </span>
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
